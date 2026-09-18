# Seed for the manual of account_multi_journal_payment (Pago multi-diario).
# Builds, from a CLEAN DB, a Dominican company with:
#
#   * Chart of accounts 'do' and three payment journals (dos bancos + caja).
#   * La opcion "Multi Journal Payments" encendida en la compania.
#   * Dos facturas de proveedor identicas de RD$50,000:
#       - una publicada y SIN pagar, para capturar el asistente de pago;
#       - una publicada y YA pagada, repartida entre dos bancos, para
#         capturar los dos pagos resultantes.
#
# Ejecutado dentro de `odoo shell` (`env` disponible). Termina con commit.

MODULE = "account_multi_journal_payment"

company = env.ref("base.main_company")
do = env.ref("base.do")

# -- 0. Espanol --------------------------------------------------------------
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

env["ir.module.module"].search(
    [("name", "in", [MODULE, "account", "l10n_do"]), ("state", "=", "installed")]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Compania RD + plan contable dominicano -------------------------------
company.write({"name": "INDEXA SRL", "country_id": do.id, "vat": "131793916"})
env["account.chart.template"].try_loading("do", company=company, install_demo=False)
company.multi_journal_payment = True

# -- 2. Diarios de pago ------------------------------------------------------
def journal(name, code, jtype):
    rec = env["account.journal"].search(
        [("code", "=", code), ("company_id", "=", company.id)], limit=1
    )
    if rec:
        rec.name = name
        return rec
    return env["account.journal"].create(
        {"name": name, "code": code, "type": jtype, "company_id": company.id}
    )


banco_popular = journal("Banco Popular - Cta. Corriente", "BNK1", "bank")
banreservas = journal("Banreservas - Cta. Corriente", "BRES", "bank")
caja = journal("Caja Chica", "CSH1", "cash")

# -- 3. Suplidor -------------------------------------------------------------
partner = env["res.partner"].search([("name", "=", "Suplidora Nacional, SRL")], limit=1)
if not partner:
    partner = env["res.partner"].create(
        {"name": "Suplidora Nacional, SRL", "vat": "131000029", "country_id": do.id}
    )

cuenta_gasto = env["account.account"].search(
    [("account_type", "=", "expense"), ("company_ids", "in", company.id)], limit=1
) or env["account.account"].search([("account_type", "=", "expense")], limit=1)


def factura(numero, monto=50000.0):
    bill = env["account.move"].create(
        {
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": "2026-09-01",
            "date": "2026-09-01",
            "l10n_latam_document_number": numero,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "name": "Suministro de oficina",
                        "quantity": 1,
                        "price_unit": monto,
                        "account_id": cuenta_gasto.id,
                        "tax_ids": [(6, 0, [])],
                    },
                )
            ],
        }
    )
    bill.action_post()
    return bill


bill_pendiente = factura("B0100000001")
bill_pagada = factura("B0100000002")

# -- 4. Pagar la segunda repartida entre dos bancos --------------------------
wizard = (
    env["account.payment.register"]
    .with_context(active_model="account.move", active_ids=bill_pagada.ids)
    .create({})
)
moneda = company.currency_id
wizard.payment_journal_ids[0].write(
    {"journal_id": banco_popular.id, "amount": 30000.0, "currency_id": moneda.id}
)
wizard.write(
    {
        "payment_journal_ids": [
            (
                0,
                0,
                {
                    "journal_id": banreservas.id,
                    "amount": 20000.0,
                    "currency_id": moneda.id,
                    "source_currency_id": moneda.id,
                    "source_amount": 20000.0,
                },
            )
        ]
    }
)
pagos = wizard._create_payments()

# -- 5. Acciones de demo para el manual --------------------------------------
def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {
            "module": MODULE,
            "name": xmlid,
            "model": "ir.actions.act_window",
            "res_id": act.id,
            "noupdate": True,
        }
    )
    return act


demo_action("demo_diarios", {
    "name": "Diarios de banco y efectivo",
    "res_model": "account.journal",
    "view_mode": "list,form",
    "domain": "[('type', 'in', ('bank', 'cash'))]",
})
demo_action("demo_factura_pendiente", {
    "name": "Factura pendiente",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": bill_pendiente.id,
})
demo_action("demo_factura_pagada", {
    "name": "Factura pagada",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": bill_pagada.id,
})
demo_action("demo_pagos", {
    "name": "Pagos generados",
    "res_model": "account.payment",
    "view_mode": "list,form",
    "domain": "[('id', 'in', %s)]" % str(pagos.ids),
})

env.cr.commit()

print(
    "SEED OK | pendiente:", bill_pendiente.name,
    "| pagada:", bill_pagada.name, bill_pagada.payment_state,
    "| pagos:", [(p.journal_id.name, p.amount) for p in pagos],
)
