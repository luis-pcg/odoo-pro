# Datos de ejemplo para el manual de sale_stock_restriction (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "sale_stock_restriction"

company = env.ref("base.main_company")
company.write(
    {
        "name": "Empresa Dominicana SRL",
        "sale_stock_restriction": True,
        "sale_stock_restriction_type": "available",
    }
)
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
    | env.ref("stock.group_adv_location")
    | env.ref("stock.group_stock_multi_locations")
)
bypass_group = env.ref("sale_stock_restriction.sale_stock_restrict_wo_stock")
bypass_group.user_ids = [Command.unlink(admin.id)]
company.partner_id.lang = "es_DO"

warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
warehouse.name = "Almacén Principal"
stock = warehouse.lot_stock_id
Product = env["product.product"]
fridge = Product.create({"name": "Nevera Inverter 14 pies", "is_storable": True, "list_price": 38500})
cement = Product.create({"name": "Cemento gris 42.5 kg", "is_storable": True, "list_price": 480})
special = Product.create(
    {
        "name": "Aire acondicionado 24000 BTU (bajo pedido)",
        "is_storable": True,
        "list_price": 52000,
        "can_be_sold_without_stock": True,
    }
)
customer = env["res.partner"].create({"name": "Constructora del Cibao SRL"})

Quant = env["stock.quant"]
Quant._update_available_quantity(fridge, stock, 2)
Quant._update_available_quantity(cement, stock, 200)

route = env["stock.route"].create(
    {
        "name": "Importación directa",
        "sale_selectable": True,
        "confirm_sale_without_stock": True,
        "company_id": company.id,
    }
)


def order(lines):
    return env["sale.order"].create(
        {
            "partner_id": customer.id,
            "warehouse_id": warehouse.id,
            "order_line": [
                Command.create(
                    {
                        "product_id": p.id,
                        "product_uom_qty": q,
                        **({"route_ids": [Command.set(r.ids)]} if r else {}),
                    }
                )
                for p, q, r in lines
            ],
        }
    )


blocked = order([(cement, 40, None), (fridge, 5, None)])
allowed = order([(cement, 40, None), (fridge, 2, None), (special, 1, None), (fridge, 3, route)])


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


def form_action(xmlid, record, **extra):
    demo_action(
        xmlid,
        {"name": record.display_name, "res_model": record._name, "view_mode": "form", "res_id": record.id, **extra},
    )


form_action("demo_order_blocked", blocked)
form_action("demo_order_allowed", allowed)
form_action("demo_product_special", special, view_id=env.ref("product.product_normal_form_view").id)
form_action("demo_route", route)
form_action("demo_group", bypass_group)
print("SEED OK", blocked.name, allowed.name, route.name)
env.cr.commit()
