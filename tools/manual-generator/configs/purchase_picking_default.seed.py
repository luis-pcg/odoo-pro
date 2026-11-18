# Datos de ejemplo para el manual de purchase_picking_default (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import fields

MODULE = "purchase_picking_default"

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
    env.ref("purchase.group_purchase_manager")
    | env.ref("stock.group_stock_manager")
    | env.ref("stock.group_stock_multi_warehouses")
    | env.ref("stock.group_stock_multi_locations")
)
company.partner_id.lang = "es_DO"

main_wh = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
main_wh.write({"name": "Almacén Santo Domingo"})
santiago = env["stock.warehouse"].create({"name": "Almacén Santiago", "code": "STI", "company_id": company.id})
env["stock.picking.type"].search([("code", "=", "incoming")]).with_context(lang="es_DO").name = "Recepciones"

vendor = env["res.partner"].create(
    {
        "name": "Distribuidora del Cibao SRL",
        "is_company": True,
        "supplier_rank": 1,
        "city": "Santiago de los Caballeros",
        "warehouse_id": santiago.id,
    }
)
env["res.partner"].create({"name": "Importadora Capital SRL", "is_company": True, "supplier_rank": 1})

buy_route = main_wh.buy_pull_id.route_id
buy_route.product_selectable = True
product = env["product.product"].create(
    {
        "name": "Saco de arroz 100 lb",
        "is_storable": True,
        "standard_price": 2900,
        "route_ids": [(4, buy_route.id)],
        "seller_ids": [(0, 0, {"partner_id": vendor.id, "price": 2900})],
    }
)
env["stock.rule"].run(
    [
        env["stock.rule"].Procurement(
            product,
            50,
            product.uom_id,
            main_wh.lot_stock_id,
            product.name,
            "Reabastecimiento",
            company,
            {"warehouse_id": main_wh, "date_planned": fields.Datetime.now()},
        )
    ]
)
replenishment = env["purchase.order.line"].search([("product_id", "=", product.id)]).order_id


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


form_action("demo_vendor", vendor)
form_action("demo_replenishment_rfq", replenishment)
print("seed purchase_picking_default OK", replenishment.name, replenishment.picking_type_id.display_name)
env.cr.commit()
