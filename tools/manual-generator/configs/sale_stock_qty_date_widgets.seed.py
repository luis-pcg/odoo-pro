# Datos de ejemplo para el manual de sale_stock_qty_date_widgets (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

company = env.ref("base.main_company")
company.name = "Ferretería Dominicana SRL"
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
    | env.ref("stock.group_stock_multi_warehouses")
    | env.ref("stock.group_stock_multi_locations")
)
company.partner_id.lang = "es_DO"

main = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
main.write({"name": "Almacén Santo Domingo", "code": "SDQ"})
santiago = env["stock.warehouse"].create({"name": "Almacén Santiago", "code": "STI", "company_id": company.id})

Location = env["stock.location"]
sdq_a = Location.create({"name": "Pasillo A", "location_id": main.lot_stock_id.id, "usage": "internal"})
sdq_b = Location.create({"name": "Pasillo B", "location_id": main.lot_stock_id.id, "usage": "internal"})
sti_a = Location.create({"name": "Estante 1", "location_id": santiago.lot_stock_id.id, "usage": "internal"})

Product = env["product.product"]
drill = Product.create({"name": "Taladro percutor 800W", "is_storable": True, "list_price": 4850})
Quant = env["stock.quant"]
Quant._update_available_quantity(drill, sdq_a, 12)
Quant._update_available_quantity(drill, sdq_b, 6)
Quant._update_available_quantity(drill, sti_a, 9)
Quant._update_reserved_quantity(drill, sdq_a, 4)

params = env["ir.config_parameter"].sudo()
params.set_str("sale_stock_qty_date_widgets.qty_date_widget_view_option", "view_only_warehouse")
params.set_str("sale_stock_qty_select_widgets.qty_select_widget_view_option", "available_quantity")
params.set_int("sale_stock_qty_decimal_widgets.decimal_qty_widget_view_option", env.ref("uom.decimal_product_uom").id)

customer = env["res.partner"].create({"name": "Constructora del Cibao SRL"})
order = env["sale.order"].create(
    {
        "partner_id": customer.id,
        "user_id": admin.id,
        "warehouse_id": main.id,
        "order_line": [Command.create({"product_id": drill.id, "product_uom_qty": 5})],
    }
)
env.cr.commit()
print("SEED OK |", order.name, "| quants:", [(q.location_id.complete_name, q.quantity, q.available_quantity) for q in drill.stock_quant_ids if q.location_id.usage == "internal"])
