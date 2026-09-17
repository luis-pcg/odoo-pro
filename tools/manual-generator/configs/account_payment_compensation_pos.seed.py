# Seed del manual de account_payment_compensation_pos (Compensacion de pagos -
# integracion con el punto de venta). Desde una base LIMPIA arma:
#
#   * Compania "Repuestos del Este" (RD) con plan contable generico y DOP.
#   * Categoria de producto "Repuestos" con porcentaje de compensacion (5%)
#     y de compensacion sobre utilidad (10%).
#   * Una regla de compensacion en Python que paga distinto segun el pago venga
#     del punto de venta o de un pago normal: ahi se usa la variable
#     `pos_payment` que agrega este modulo.
#   * Un perfil de compensacion por pago y el vendedor que lo cobra.
#   * Un punto de venta con metodo de pago en efectivo y sesion abierta.
#   * Una orden del PdV facturada y cobrada (de ahi sale el pago del PdV) y una
#     factura normal cobrada por banco, para que el recibo muestre las dos.
#   * El informe por lotes con el recibo ya calculado.
#
# Se ejecuta dentro de `odoo shell` (el global `env` esta disponible) y termina
# con env.cr.commit().

from dateutil.relativedelta import relativedelta

from odoo import fields

company = env.ref("base.main_company")
do = env.ref("base.do")
admin = env.ref("base.user_admin")

today = fields.Date.context_today(admin)
month_from = today.replace(day=1)
month_to = month_from + relativedelta(months=1, days=-1)


def show(label, value):
    print("   %-30s %s" % (label + ":", value))


# ── 0. Espanol dominicano ────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
company = company.with_env(env)

# ── 1. Permisos del administrador ────────────────────────────────────────────
# En una base sin datos de demostracion el admin no trae los grupos de
# contabilidad ni el de compensaciones, y el recibo no se puede ni leer.
admin.group_ids |= env.ref("account.group_account_manager")
admin.group_ids |= env.ref("account_payment_compensation.account_payment_compensation_user")

# ── 2. Compania y plan contable ──────────────────────────────────────────────
company.write({"name": "Repuestos del Este", "country_id": do.id})
company.partner_id.lang = "es_DO"
if not company.chart_template:
    env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)
dop = env.ref("base.DOP")
dop.active = True
if company.currency_id != dop:
    company.currency_id = dop

# ── 3. Categoria de producto con porcentaje de compensacion ──────────────────
categ = env["product.category"].create(
    {
        "name": "Repuestos",
        "compensation_percentage_sale_base": 5.0,
        "profit_compensation_percentage_sale_base": 10.0,
    }
)
pos_categ = env["pos.category"].create({"name": "Repuestos"})
battery, oil = env["product.product"].create(
    [
        {
            "name": "Batería 12V 75Ah",
            "type": "consu",
            "categ_id": categ.id,
            "list_price": 6500.00,
            "standard_price": 4200.00,
            "available_in_pos": True,
            "pos_categ_ids": [(6, 0, pos_categ.ids)],
            "taxes_id": [(6, 0, [])],
        },
        {
            "name": "Aceite de motor 20W-50",
            "type": "consu",
            "categ_id": categ.id,
            "list_price": 950.00,
            "standard_price": 620.00,
            "available_in_pos": True,
            "pos_categ_ids": [(6, 0, pos_categ.ids)],
            "taxes_id": [(6, 0, [])],
        },
    ]
)

# ── 4. Contactos ─────────────────────────────────────────────────────────────
seller, walk_in, workshop = env["res.partner"].create(
    [
        {"name": "Ramón Vásquez", "lang": "es_DO"},
        {"name": "Ferretería La Confianza", "lang": "es_DO"},
        {"name": "Taller Mecánico Peña", "lang": "es_DO"},
    ]
)

# ── 5. Regla de compensacion que distingue el pago del PdV ───────────────────
rule = env["account.compensation.rule"].create(
    {
        "name": "Comisión sobre el cobro",
        "code": "COM-COBRO",
        "sequence": 10,
        "condition_select": "none",
        "amount_select": "code",
        "amount_python_compute": (
            "# 5% de lo cobrado en el punto de venta, 2% del resto de los cobros.\n"
            "# `pos_payment` la agrega account_payment_compensation_pos: es el\n"
            "# pos.payment de la linea, o False si el cobro no vino del PdV.\n"
            "result = paid_amount * (0.05 if pos_payment else 0.02)"
        ),
    }
)

# ── 6. Perfil de compensacion y vendedor ─────────────────────────────────────
profile = env["account.compensation.profile"].create(
    {
        "name": "Comisión de vendedores",
        "receipt_name": "Recibo de comisión",
        "flow_type": "payment",
        "rule_ids": [(6, 0, rule.ids)],
        "payments_domain": "[]",
        "invoices_domain": "[('move_type', 'in', ['out_invoice', 'out_receipt'])]",
    }
)
seller.profile_ids = [(6, 0, profile.ids)]

# ── 7. Punto de venta con sesion abierta ─────────────────────────────────────
cash_journal = env["account.journal"].search([("type", "=", "cash"), ("company_id", "=", company.id)], limit=1)
if not cash_journal:
    cash_journal = env["account.journal"].create(
        {"name": "Efectivo", "code": "CSH", "type": "cash", "company_id": company.id}
    )
cash_method = env["pos.payment.method"].create(
    {"name": "Efectivo", "journal_id": cash_journal.id, "company_id": company.id}
)
config = env["pos.config"].create(
    {
        "name": "Mostrador Repuestos",
        "company_id": company.id,
        "payment_method_ids": [(6, 0, cash_method.ids)],
        "iface_available_categ_ids": [(6, 0, pos_categ.ids)],
    }
)
config.with_user(admin).open_ui()
session = config.current_session_id
session.with_user(admin).set_opening_control(0, "")

# ── 8. Orden del PdV facturada (de aqui sale el pago del PdV) ────────────────
pos_amount = 6500.00
pos_order = env["pos.order"].create(
    {
        "company_id": company.id,
        "session_id": session.id,
        "partner_id": walk_in.id,
        "amount_total": pos_amount,
        "amount_tax": 0.0,
        "amount_paid": pos_amount,
        "amount_return": 0.0,
        "lines": [
            (
                0,
                0,
                {
                    "name": "Batería 12V 75Ah",
                    "product_id": battery.id,
                    "qty": 1,
                    "price_unit": pos_amount,
                    "price_subtotal": pos_amount,
                    "price_subtotal_incl": pos_amount,
                    "tax_ids": [(6, 0, [])],
                },
            )
        ],
    }
)
pos_order.add_payment(
    {
        "pos_order_id": pos_order.id,
        "payment_method_id": cash_method.id,
        "amount": pos_amount,
        "payment_date": fields.Datetime.now(),
    }
)
pos_order.action_pos_order_paid()
pos_order.with_context(generate_pdf=False).action_pos_order_invoice()
pos_invoice = pos_order.account_move
pos_payment = pos_order.payment_ids[:1]

# ── 9. Factura normal cobrada por banco, para contrastar ─────────────────────
bank_journal = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
invoice = env["account.move"].create(
    {
        "move_type": "out_invoice",
        "partner_id": workshop.id,
        "invoice_date": today,
        "invoice_line_ids": [
            (0, 0, {"product_id": oil.id, "quantity": 4, "price_unit": 950.00, "tax_ids": [(6, 0, [])]})
        ],
    }
)
invoice.action_post()
# El pago se crea y se concilia a mano. Con la app de Contabilidad instalada,
# Odoo no le asienta el pago hasta conciliar el extracto bancario (la factura
# queda "En pago"), y sin asiento no hay conciliacion que leer: `force_payment_move`
# es el contexto que el propio core usa para forzar el asiento del pago.
payment = env["account.payment"].with_context(force_payment_move=True).create(
    {
        "payment_type": "inbound",
        "partner_type": "customer",
        "partner_id": workshop.id,
        "amount": invoice.amount_total,
        "date": today,
        "journal_id": bank_journal.id,
    }
)
payment.action_post()
(invoice.line_ids + payment.move_id.line_ids).filtered(
    lambda line: line.account_id.account_type == "asset_receivable"
).reconcile()

# ── 10. Informe por lotes con el recibo calculado ────────────────────────────
batch = env["account.compensation.batch.report"].create(
    {
        "name": "Comisiones %s" % fields.Date.to_string(month_from)[:7],
        "date_from": month_from,
        "date_to": month_to,
        "company_id": company.id,
    }
)
env["account.compensation.by.profile"].with_context(active_id=batch.id).create(
    {"profile_ids": [(6, 0, profile.ids)]}
).compute_sheet()
receipt = batch.receipt_ids[:1]

# ── 11. xmlids fijos: el generador abre los registros por xmlid ──────────────
env["ir.model.data"]._update_xmlids(
    [
        {"xml_id": "__manual__.categ_repuestos", "record": categ},
        {"xml_id": "__manual__.rule_comision", "record": rule},
        {"xml_id": "__manual__.profile_comision", "record": profile},
        {"xml_id": "__manual__.partner_vendedor", "record": seller},
        {"xml_id": "__manual__.pos_order", "record": pos_order},
        {"xml_id": "__manual__.pos_invoice", "record": pos_invoice},
        {"xml_id": "__manual__.batch_report", "record": batch},
        {"xml_id": "__manual__.receipt", "record": receipt},
    ]
)

env.cr.commit()

print("SEED OK")
show("Compañía", "%s (%s)" % (company.name, company.currency_id.name))
show("Categoría", "%s (%s%%)" % (categ.name, categ.compensation_percentage_sale_base))
show("Regla", "%s [%s]" % (rule.name, rule.code))
show("Perfil", "%s (%s)" % (profile.name, profile.flow_type))
show("Vendedor", seller.name)
show("Punto de venta", "%s / sesión %s (%s)" % (config.name, session.name, session.state))
show("Orden PdV", "%s -> %s" % (pos_order.name, pos_invoice.name))
show("Pago PdV", "%s (id %s)" % (pos_payment.display_name, pos_payment.id))
show("Factura banco", "%s (%s) pago %s" % (invoice.name, invoice.payment_state, payment.name))
show("Informe por lotes", "%s (%s)" % (batch.name, batch.state))
show("Recibo", "%s (%s)" % (receipt.name, receipt.state))
show("Líneas del recibo", len(receipt.compensation_line_ids))
show(
    "Líneas con pago del PdV",
    len(receipt.compensation_line_ids.filtered(lambda line: line.pos_payment_id)),
)
show("Total", "%s %s" % (receipt.total_compensation_amount, receipt.currency_id.name))
