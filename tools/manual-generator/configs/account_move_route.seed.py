# Datos de ejemplo para el manual de account_move_route (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "account_move_route"

company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL"})
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= (
    env.ref("sales_team.group_sale_manager")
    | env.ref("account.group_account_manager")
    | env.ref("account.group_account_basic")
    | env.ref("account.group_account_user")
    | env.ref("stock.group_stock_manager")
    | env.ref("stock.group_adv_location")
)
company.partner_id.lang = "es_DO"

Route = env["stock.route"]
dropship = Route.create({"name": "Entrega directa del proveedor", "sale_selectable": True})
pickup = Route.create({"name": "Retiro en tienda", "sale_selectable": True})

Product = env["product.product"]
inverter = Product.create({"name": "Inversor solar 5 kW", "type": "consu", "sale_ok": True, "list_price": 68500})
panel = Product.create({"name": "Panel solar 550 W", "type": "consu", "sale_ok": True, "list_price": 12900})
cable = Product.create({"name": "Cable solar 6 mm (rollo 100 m)", "type": "consu", "sale_ok": True, "list_price": 9800})
customer = env["res.partner"].create({"name": "Distribuidora del Caribe SRL"})

order = env["sale.order"].create(
    {
        "partner_id": customer.id,
        "order_line": [
            Command.create({"product_id": inverter.id, "product_uom_qty": 2, "route_ids": [Command.set(dropship.ids)]}),
            Command.create({"product_id": panel.id, "product_uom_qty": 12, "route_ids": [Command.set((dropship | pickup).ids)]}),
            Command.create({"product_id": cable.id, "product_uom_qty": 3}),
        ],
    }
)
order.action_confirm()
invoice = order._create_invoices()
invoice.action_post()


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


def form_action(xmlid, record):
    demo_action(xmlid, {"name": record.display_name, "res_model": record._name, "view_mode": "form", "res_id": record.id})


form_action("demo_order", order)
form_action("demo_invoice", invoice)
print(
    "seed account_move_route OK",
    order.name,
    invoice.name,
    [(line.product_id.name, line.route_ids.mapped("name")) for line in invoice.invoice_line_ids],
)
env.cr.commit()
