# Seed del manual de l10n_do_sale_pos_backend (caja backend con comprobantes fiscales DO).
# Se ejecuta dentro de `odoo shell` y termina con env.cr.commit().

from dateutil.relativedelta import relativedelta

from odoo import fields
from odoo.tests import Form

company = env.ref("base.main_company")
admin = env.ref("base.user_admin")


def show(label, value):
    print("   %-30s %s" % (label + ":", value))


env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin.lang = "es_DO"
admin.tz = "America/Santo_Domingo"
env = env(context=dict(env.context, lang="es_DO", tz="America/Santo_Domingo"))
company = company.with_env(env)
do = env.ref("base.do")

admin.group_ids |= (
    env.ref("account.group_account_manager")
    | env.ref("sales_team.group_sale_manager")
    | env.ref("stock.group_stock_manager")
    | env.ref("sale_pos_backend.sale_pos_backend_manager")
)

company.write({"name": "Ferretería El Martillo", "country_id": do.id, "vat": "131793898"})
company.partner_id.lang = "es_DO"
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company, install_demo=False, force_create=True)
company.account_fiscal_country_id = do
dop = env.ref("base.DOP")
dop.active = True
company.currency_id = dop

Journal = env["account.journal"]
cash = Journal.create({"name": "Efectivo", "type": "cash", "code": "EFE"})
fiscal_journal = Journal.create(
    {"name": "Ventas Fiscales", "code": "VFIS", "type": "sale", "l10n_latam_use_documents": True}
)
warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
tax18 = env["account.tax"].search(
    [("type_tax_use", "=", "sale"), ("amount", "=", 18), ("company_id", "=", company.id)], limit=1
)
exempt = env["account.tax"].search(
    [("type_tax_use", "=", "sale"), ("amount", "=", 0), ("company_id", "=", company.id)], limit=1
)
itbis_declared = env["account.fiscal.position"].create({"name": "ITBIS ya declarado"})
tax18.fiscal_position_ids = [(4, itbis_declared.id)]
exempt.write({"fiscal_position_ids": [(4, itbis_declared.id)], "original_tax_ids": [(4, tax18.id)]})
company.write({"l10n_do_fiscal_position_id": itbis_declared.id, "l10n_do_day_months": 31})

products = {}
for code, name, price in [("MART-01", "Martillo de uña 16 oz", 500), ("TALA-01", "Taladro percutor 1/2\"", 3500)]:
    products[code] = env["product.product"].create(
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
reason = env["sale.return.reason"].create({"name": "Producto defectuoso"})
consumer = env["res.partner"].create({"name": "Consumidor final", "country_id": do.id})
taxpayer = env["res.partner"].create(
    {"name": "Constructora Pérez SRL", "vat": "131098193", "is_company": True, "country_id": do.id}
)

cashier = env["sale.cashier"].create(
    {
        "name": "Caja Fiscal",
        "code": "CF1",
        "journal_id": fiscal_journal.id,
        "warehouse_id": warehouse.id,
        "warehouse_ids": [(6, 0, warehouse.ids)],
        "payment_journal_ids": [(6, 0, cash.ids)],
        "payment_journal_id": cash.id,
        "refund_journal_ids": [(6, 0, cash.ids)],
        "pricelist_id": pricelist.id,
        "available_pricelist_ids": [(6, 0, pricelist.ids)],
        "default_partner_id": consumer.id,
        "refund_reason_ids": [(6, 0, reason.ids)],
        "auto_confirm_picking": True,
    }
)
session = env["sale.cashier.session"].browse(cashier.with_context(user_id=admin.id).open_session_scs()["res_id"])
SaleOrder = env["sale.order"].with_user(admin).with_context(sale_cashier_order=True)


def sell(partner, code, qty, paid=None):
    order = SaleOrder.create(
        {"partner_id": partner.id, "order_line": [(0, 0, {"product_id": products[code].id, "product_uom_qty": qty})]}
    )
    if paid is None:
        return order
    order.action_confirm()
    wizard = env["sale.advance.payment.inv"].with_context(
        active_model="sale.order", active_ids=order.ids, active_id=order.id
    ).create({"advance_payment_method": "delivered"})
    wizard.amount = paid
    wizard.create_invoices()
    return order


def refund(order, quantity):
    with Form(
        env["sale.order.refund"].with_context(active_id=order.id, active_model="sale.order", default_order_id=order.id)
    ) as wizard:
        wizard.refund_type = "return"
        wizard.refund_reason_id = reason
        wizard.location_id = warehouse.lot_stock_id
        wizard.reason = "Producto defectuoso"
        with wizard.line_ids.edit(0) as line:
            line.qty_done = quantity
    return env["account.move"].browse(wizard.record.action_refund()["res_id"])


order_b01 = sell(taxpayer, "TALA-01", 2, paid=8260)
invoice_b01 = order_b01.invoice_ids
credit_recent = refund(order_b01, 1)

order_old = sell(taxpayer, "MART-01", 4, paid=2360)
invoice_old = order_old.invoice_ids
old_date = fields.Date.context_today(admin) - relativedelta(days=45)
env.cr.execute(
    "UPDATE account_move SET invoice_date = %s, date = %s WHERE id = %s", (old_date, old_date, invoice_old.id)
)
invoice_old.invalidate_recordset(["invoice_date", "date"])
credit_old = refund(order_old, 1)

order_b02 = sell(consumer, "MART-01", 1, paid=590)
quotation = sell(taxpayer, "MART-01", 3)

env["ir.model.data"]._update_xmlids(
    [
        {"xml_id": "__manual__.session", "record": session},
        {"xml_id": "__manual__.quotation", "record": quotation},
        {"xml_id": "__manual__.order_b02", "record": order_b02},
        {"xml_id": "__manual__.invoice_b01", "record": invoice_b01},
        {"xml_id": "__manual__.credit_recent", "record": credit_recent},
        {"xml_id": "__manual__.credit_old", "record": credit_old},
    ]
)

env.cr.commit()

print("SEED OK")
show("Compañía", "%s RNC %s" % (company.name, company.vat))
show("Cotización (RNC)", "%s tipo %s" % (quotation.name, quotation.l10n_do_document_type_id.name))
show("Consumidor final", "%s -> %s" % (order_b02.name, order_b02.invoice_ids.name))
show("Factura fiscal", "%s %s" % (invoice_b01.name, invoice_b01.amount_total))
show("NC reciente", "%s modifica %s total %s" % (credit_recent.name, credit_recent.l10n_do_origin_ncf, credit_recent.amount_total))
show("NC > 30 días", "%s modifica %s total %s fp %s" % (credit_old.name, credit_old.l10n_do_origin_ncf, credit_old.amount_total, credit_old.fiscal_position_id.name))
