# Datos de ejemplo para el manual de website_stock_availability (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "website_stock_availability"

company = env.ref("base.main_company")
company.write({"name": "Ferretería Dominicana SRL", "country_id": env.ref("base.do").id})
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= env.ref("stock.group_stock_manager") | env.ref("stock.group_stock_multi_warehouses") | env.ref(
    "product.group_product_variant"
)

website = env["website"].search([("company_id", "=", company.id)], limit=1) or env.ref("website.default_website")
website.write(
    {
        "name": "Ferretería Dominicana",
        "language_ids": [Command.link(es.id)],
        "default_lang_id": es.id,
        "show_stock": "warehouse_with_stock",
    }
)

Warehouse = env["stock.warehouse"]
main = Warehouse.search([("company_id", "=", company.id)], limit=1)
main.write({"name": "Almacén Principal", "show_warehouse_web": True})
santiago = Warehouse.create({"name": "Almacén Santiago", "code": "SAN", "company_id": company.id})
transit = Warehouse.create(
    {"name": "Almacén Tránsito", "code": "TRA", "company_id": company.id, "show_warehouse_web": False}
)

color = env["product.attribute"].create(
    {
        "name": "Color",
        "display_type": "radio",
        "create_variant": "always",
        "value_ids": [Command.create({"name": "Amarillo"}), Command.create({"name": "Negro"})],
    }
)
template = env["product.template"].create(
    {
        "name": "Taladro Inalámbrico 20V",
        "type": "consu",
        "is_storable": True,
        "list_price": 6950.0,
        "is_published": True,
        "website_id": website.id,
        "attribute_line_ids": [Command.create({"attribute_id": color.id, "value_ids": [Command.set(color.value_ids.ids)]})],
    }
)
yellow = template.product_variant_ids.filtered(lambda p: "Amarillo" in p.display_name)
black = template.product_variant_ids - yellow


def add_stock(product, warehouse, qty):
    env["stock.quant"].with_context(inventory_mode=True).create(
        {"product_id": product.id, "location_id": warehouse.lot_stock_id.id, "inventory_quantity": qty}
    ).action_apply_inventory()


add_stock(yellow, main, 12)
add_stock(yellow, santiago, 5)
add_stock(yellow, transit, 8)
add_stock(black, santiago, 3)


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


form_action("demo_wh_main", main)
form_action("demo_wh_transit", transit)
demo_action(
    "demo_quants",
    {
        "name": "Existencias por almacén",
        "res_model": "stock.quant",
        "view_mode": "list",
        "domain": [("product_id.product_tmpl_id", "=", template.id), ("location_id.usage", "=", "internal")],
        "context": {"group_by": ["product_id"]},
    },
)
print("SEED OK", website.id, template.website_url, yellow.free_qty, black.free_qty)
env.cr.commit()
