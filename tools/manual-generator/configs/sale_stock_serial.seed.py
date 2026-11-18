# Datos de ejemplo para el manual de sale_stock_serial (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "sale_stock_serial"

company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL", "edit_lots_and_serials_sales": True})
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= (
    env.ref("sales_team.group_sale_manager")
    | env.ref("stock.group_stock_manager")
    | env.ref("sale_stock_serial.group_sale_pick_lot")
)
company.partner_id.lang = "es_DO"

stock = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1).lot_stock_id
Product = env["product.product"]
laptop = Product.create({"name": "Laptop ProBook 450", "is_storable": True, "tracking": "serial", "list_price": 55000})
cement = Product.create({"name": "Cemento gris 42.5 kg", "is_storable": True, "tracking": "lot", "list_price": 480})
customer = env["res.partner"].create({"name": "Constructora del Cibao SRL"})

Lot = env["stock.lot"]
lots = {}
for product, name in [
    (laptop, "SN-PB450-0001"),
    (laptop, "SN-PB450-0002"),
    (laptop, "SN-PB450-0003"),
    (cement, "CEM-2026-09-A"),
    (cement, "CEM-2026-09-B"),
]:
    lots[name] = Lot.create({"name": name, "product_id": product.id, "company_id": company.id})
Quant = env["stock.quant"]
Quant._update_available_quantity(laptop, stock, 1, lot_id=lots["SN-PB450-0001"])
Quant._update_available_quantity(laptop, stock, 1, lot_id=lots["SN-PB450-0002"])
Quant._update_available_quantity(laptop, stock, 1, lot_id=lots["SN-PB450-0003"])
Quant._update_available_quantity(cement, stock, 200, lot_id=lots["CEM-2026-09-A"])
Quant._update_available_quantity(cement, stock, 150, lot_id=lots["CEM-2026-09-B"])


def order(lines):
    return env["sale.order"].create(
        {
            "partner_id": customer.id,
            "order_line": [
                Command.create({"product_id": p.id, "product_uom_qty": q, "lot_id": lot and lots[lot].id})
                for p, q, lot in lines
            ],
        }
    )


draft = order([(laptop, 1, "SN-PB450-0002"), (cement, 40, "CEM-2026-09-B"), (cement, 10, False)])
confirmed = order([(laptop, 1, "SN-PB450-0003"), (cement, 60, "CEM-2026-09-B")])
confirmed.action_confirm()
picking = confirmed.picking_ids[:1]
picking.action_assign()


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


form_action("demo_order_draft", draft)
form_action("demo_order_confirmed", confirmed)
form_action("demo_picking", picking)
demo_action(
    "demo_reserved_lines",
    {
        "name": "Reservas de %s" % picking.name,
        "res_model": "stock.move.line",
        "view_mode": "list",
        "domain": [("picking_id", "=", picking.id)],
    },
)
print("seed sale_stock_serial OK", draft.name, confirmed.name, picking.name, picking.move_line_ids.mapped("lot_id.name"))
env.cr.commit()
