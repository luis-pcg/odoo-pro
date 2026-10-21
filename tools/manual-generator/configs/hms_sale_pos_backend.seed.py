# Seed del manual de sale_pos_backend (caja en el backend sobre pedidos de venta).
# Se ejecuta dentro de `odoo shell` y termina con env.cr.commit().

from odoo import fields
from odoo.tests import Form

company = env.ref("base.main_company")
admin = env.ref("base.user_admin")


def show(label, value):
    print("   %-30s %s" % (label + ":", value))


es = env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin.lang = "es_DO"
admin.tz = "America/Santo_Domingo"
env = env(context=dict(env.context, lang="es_DO", tz="America/Santo_Domingo"))
company = company.with_env(env)

admin.group_ids |= (
    env.ref("account.group_account_manager")
    | env.ref("sales_team.group_sale_manager")
    | env.ref("stock.group_stock_manager")
    | env.ref("product.group_product_pricelist")
    | env.ref("sale_pos_backend.sale_pos_backend_manager")
)

company.write({"name": "Ferretería El Martillo", "country_id": env.ref("base.do").id, "vat": "131793898"})
company.partner_id.lang = "es_DO"
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company, install_demo=False, force_create=True)
company.account_fiscal_country_id = env.ref("base.do")
dop = env.ref("base.DOP")
usd = env.ref("base.USD")
dop.active = usd.active = True
company.currency_id = dop
env["res.currency.rate"].create({"currency_id": usd.id, "name": "2026-01-01", "inverse_company_rate": 60.0})

Journal = env["account.journal"]
cash = Journal.create({"name": "Efectivo", "type": "cash", "code": "EFE"})
bank = Journal.search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
bank.name = "Tarjeta / Transferencia"
sale_journal = Journal.search([("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
warehouse.name = "Tienda Principal"

tax18 = env["account.tax"].search(
    [("type_tax_use", "=", "sale"), ("amount", "=", 18), ("company_id", "=", company.id)], limit=1
)
Product = env["product.product"]
products = {}
for code, name, price in [
    ("MART-01", "Martillo de uña 16 oz", 500),
    ("TALA-01", "Taladro percutor 1/2\"", 3500),
    ("CLAV-01", "Caja de clavos 2\" (1 lb)", 150),
]:
    products[code] = Product.create(
        {
            "name": name,
            "default_code": code,
            "type": "consu",
            "is_storable": True,
            "list_price": price,
            "invoice_policy": "order",
            "taxes_id": [(6, 0, tax18.ids)],
        }
    )
    env["stock.quant"]._update_available_quantity(products[code], warehouse.lot_stock_id, 100)

pricelist = env["product.pricelist"].create({"name": "Precio público", "currency_id": dop.id})

Template = env["cashbox.template"]
Template.search([]).write({"currency_id": dop.id})
usd_bill = Template.create({"value": 100, "currency_id": usd.id})
dop_bills = Template.search([("currency_id", "=", dop.id), ("value", "in", [100, 200, 500, 1000, 2000])])

reasons = env["sale.return.reason"].create([{"name": "Producto defectuoso"}, {"name": "Cambio de opinión"}])
walk_in = env["res.partner"].create({"name": "Cliente de contado", "country_id": env.ref("base.do").id})
customer = env["res.partner"].create(
    {"name": "Constructora Pérez SRL", "is_company": True, "country_id": env.ref("base.do").id}
)

common = {
    "journal_id": sale_journal.id,
    "warehouse_id": warehouse.id,
    "warehouse_ids": [(6, 0, warehouse.ids)],
    "payment_journal_ids": [(6, 0, (cash | bank).ids)],
    "payment_journal_id": cash.id,
    "refund_journal_ids": [(6, 0, cash.ids)],
    "pricelist_id": pricelist.id,
    "available_pricelist_ids": [(6, 0, pricelist.ids)],
    "default_partner_id": walk_in.id,
    "refund_reason_ids": [(6, 0, reasons.ids)],
    "auto_confirm_picking": True,
    "cash_back": True,
}
Cashier = env["sale.cashier"]
main_cashier = Cashier.create(
    dict(
        common,
        name="Caja Principal",
        code="C01",
        cash_control=True,
        cash_control_multi_currency=True,
        default_cashbox_ids=[(6, 0, (dop_bills | usd_bill).ids)],
        amount_authorized_diff=50,
        reason_return_required=True,
        can_edit_payment_date=True,
        can_edit_memo=True,
    )
)
express_cashier = Cashier.create(dict(common, name="Caja Express", code="C02"))
back_cashier = Cashier.create(
    dict(
        common,
        name="Caja Almacén",
        code="C03",
        cash_control=True,
        default_cashbox_ids=[(6, 0, dop_bills.ids)],
    )
)


def open_with_balance(cashier, quantities):
    session = env["sale.cashier.session"].browse(cashier.open_session_scs()["res_id"])
    wizard = env["sale.cashier.session.open"].with_context(
        active_model="sale.cashier.session", active_id=session.id
    ).create({})
    for line in wizard.sale_cashier_session_cashbox_ids:
        line.qty = quantities.get(line.cashbox_template_id, 0)
    wizard.action_session_cashbox_set_balance_open()
    session.action_session_open()
    return session


def sell(session, partner, lines, paid=None, journal=None):
    order = (
        env["sale.order"]
        .with_user(session.user_id)
        .with_context(sale_cashier_order=True)
        .create(
            {
                "partner_id": partner.id,
                "order_line": [(0, 0, {"product_id": products[c].id, "product_uom_qty": q}) for c, q in lines],
            }
        )
    )
    order.action_confirm()
    if paid is None:
        return order
    wizard = env["sale.advance.payment.inv"].with_context(
        active_model="sale.order", active_ids=order.ids, active_id=order.id
    ).create({"advance_payment_method": "delivered"})
    wizard.amount = paid
    if journal:
        wizard.journal_id = journal
    wizard.create_invoices()
    return order


express_session = express_cashier.with_context(user_id=admin.id).open_session_scs()
express_session = env["sale.cashier.session"].browse(express_session["res_id"])
sell(express_session, walk_in, [("CLAV-01", 4)], paid=708)
express_session.action_pos_session_close()

session = open_with_balance(main_cashier.with_context(user_id=admin.id), {dop_bills.filtered(lambda t: t.value == 1000): 2, dop_bills.filtered(lambda t: t.value == 100): 5, usd_bill: 1})
order_cash = sell(session, walk_in, [("MART-01", 2)], paid=1200)
order_card = sell(session, customer, [("TALA-01", 1), ("CLAV-01", 2)], paid=4484, journal=bank)
order_to_pay = sell(session, customer, [("MART-01", 1), ("CLAV-01", 10)])
quotation = (
    env["sale.order"]
    .with_user(admin)
    .with_context(sale_cashier_order=True)
    .create({"partner_id": walk_in.id, "order_line": [(0, 0, {"product_id": products["TALA-01"].id})]})
)

with Form(
    env["sale.order.refund"].with_context(active_id=order_card.id, active_model="sale.order", default_order_id=order_card.id)
) as refund_form:
    refund_form.refund_type = "return"
    refund_form.refund_reason_id = reasons[0]
    refund_form.location_id = warehouse.lot_stock_id
    refund_form.reason = "Clavos oxidados"
    for index in range(len(refund_form.line_ids)):
        with refund_form.line_ids.edit(index) as line:
            line.qty_done = 1 if line.product_id == products["CLAV-01"] else 0
credit_note = env["account.move"].browse(refund_form.record.action_refund()["res_id"])

warehouse_user = env["res.users"].create(
    {
        "name": "Pedro Almacén",
        "login": "pedro",
        "group_ids": [(6, 0, (env.ref("base.group_user") | env.ref("sale_pos_backend.sale_pos_backend_user")).ids)],
    }
)
back_session = env["sale.cashier.session"].browse(
    back_cashier.with_context(user_id=warehouse_user.id).open_session_scs()["res_id"]
)

env["ir.model.data"]._update_xmlids(
    [
        {"xml_id": "__manual__.cashier_main", "record": main_cashier},
        {"xml_id": "__manual__.session_main", "record": session},
        {"xml_id": "__manual__.session_back", "record": back_session},
        {"xml_id": "__manual__.session_express", "record": express_session},
        {"xml_id": "__manual__.order_cash", "record": order_cash},
        {"xml_id": "__manual__.order_card", "record": order_card},
        {"xml_id": "__manual__.order_to_pay", "record": order_to_pay},
        {"xml_id": "__manual__.quotation", "record": quotation},
        {"xml_id": "__manual__.invoice_cash", "record": order_cash.invoice_ids},
        {"xml_id": "__manual__.credit_note", "record": credit_note},
    ]
)

env.cr.commit()

print("SEED OK")
show("Compañía", "%s (%s)" % (company.name, company.currency_id.name))
show("Cajas", ", ".join(Cashier.search([]).mapped("name")))
show("Sesión principal", "%s (%s) apertura %s" % (session.name, session.state, session.cash_register_opening_balance))
show("Saldos por moneda", session.sale_carhier_session_balance_ids.mapped(lambda b: (b.currency_id.name, b.cash_register_opening_balance)))
show("Factura contado", "%s %s cambio %s" % (order_cash.invoice_ids.name, order_cash.invoice_ids.payment_state, order_cash.invoice_ids.change))
show("Factura tarjeta", "%s %s" % (order_card.invoice_ids.filtered(lambda m: m.move_type == "out_invoice").name, order_card.invoice_ids[:1].payment_state))
show("Nota de crédito", "%s %s" % (credit_note.name, credit_note.amount_total))
show("Por cobrar", "%s %s" % (order_to_pay.name, order_to_pay.invoice_status))
show("Sesión Express", "%s (%s)" % (express_session.name, express_session.state))
show("Sesión Almacén", "%s (%s)" % (back_session.name, back_session.state))

# ---- hms_sale_pos_backend ----
admin.group_ids |= env.ref("hms_partner.group_medical_service_user")
Partner = env["res.partner"]
ars = Partner.create({"name": "ARS Humano", "medical_contact_type": "insurance", "is_company": True, "insurance_type": "private"})
doctor = Partner.create(
    {"name": "Dra. Ana Méndez", "medical_speciality_ids": [(0, 0, {"name": "Traumatología"})]}
)
surgeon = Partner.create(
    {"name": "Dr. Luis Castillo", "medical_speciality_ids": [(0, 0, {"name": "Cirugía general"})]}
)
patient = Partner.create(
    {
        "name": "Juan Pérez",
        "medical_contact_type": "patient",
        "medical_record": "EXP-2026-0045",
        "insurance_partner_id": ars.id,
        "affiliate_id": "AF-778812",
        "country_id": env.ref("base.do").id,
    }
)
SaleOrder = env["sale.order"].with_user(admin).with_context(sale_cashier_order=True)
medical_order = SaleOrder.create(
    {
        "partner_id": patient.id,
        "authorization_number": "AUT-55120",
        "treating_partner_id": doctor.id,
        "surgeon_partner_id": surgeon.id,
        "order_line": [(0, 0, {"product_id": products["TALA-01"].id})],
    }
)
medical_order.action_confirm()
wizard = env["sale.advance.payment.inv"].with_context(
    active_model="sale.order", active_ids=medical_order.ids, active_id=medical_order.id
).create({"advance_payment_method": "delivered"})
wizard.create_invoices()
medical_quote = SaleOrder.create(
    {"partner_id": patient.id, "treating_partner_id": doctor.id, "order_line": [(0, 0, {"product_id": products["MART-01"].id})]}
)
env["ir.model.data"]._update_xmlids(
    [
        {"xml_id": "__manual__.patient", "record": patient},
        {"xml_id": "__manual__.medical_order", "record": medical_order},
        {"xml_id": "__manual__.medical_quote", "record": medical_quote},
        {"xml_id": "__manual__.medical_invoice", "record": medical_order.invoice_ids},
    ]
)
env.cr.commit()
show("Pedido médico", "%s -> %s (%s)" % (medical_order.name, medical_order.invoice_ids.name, medical_order.invoice_ids.treating_partner_id.name))
