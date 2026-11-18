# Datos de ejemplo para el manual de sale_order_with_other_locations (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "sale_order_with_other_locations"

company = env.ref("base.main_company")
country_do = env.ref("base.do")
distrito = env.ref("base.state_DO_01")
santiago = env.ref("base.state_DO_25")
company.write(
    {
        "name": "Empresa Dominicana SRL",
        "street": "Av. Winston Churchill",
        "city": "Santo Domingo",
        "state_id": distrito.id,
        "country_id": country_do.id,
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
    | env.ref("stock.group_stock_multi_locations")
)

wh_sd = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
wh_sd.write({"name": "Almacén Santo Domingo", "code": "SD"})
wh_sti = env["stock.warehouse"].create({"name": "Almacén Santiago", "code": "STI"})
wh_sti.partner_id.write(
    {"street": "Av. 27 de Febrero", "city": "Santiago", "state_id": santiago.id, "country_id": country_do.id}
)
distrito.warehouse_ids = [Command.set(wh_sd.ids)]
santiago.warehouse_ids = [Command.set(wh_sti.ids)]

customer = env["res.partner"].create(
    {
        "name": "Ferretería del Cibao",
        "email": "compras@ferreteriacibao.do",
        "street": "Calle del Sol 120",
        "city": "Santiago",
        "state_id": santiago.id,
        "country_id": country_do.id,
    }
)
drill = env["product.product"].create({"name": "Taladro inalámbrico 20V", "is_storable": True, "list_price": 6500})
env["stock.quant"]._update_available_quantity(drill, wh_sd.lot_stock_id, 10)

website = env["website"].search([("company_id", "=", company.id)], limit=1)
order = env["sale.order"].create(
    {
        "partner_id": customer.id,
        "website_id": website.id,
        "order_line": [Command.create({"product_id": drill.id, "product_uom_qty": 2})],
    }
)
order.order_line.warehouse_ids = wh_sd
order.action_confirm()
transfer = order.env["stock.picking"].search(
    [("origin", "=", order.name), ("picking_type_id", "=", wh_sd.int_type_id.id)]
)


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


form_action("demo_country", country_do)
form_action("demo_order", order)
form_action("demo_transfer", transfer)
demo_action(
    "demo_order_pickings",
    {
        "name": "Transferencias de %s" % order.name,
        "res_model": "stock.picking",
        "view_mode": "list,form",
        "domain": [("origin", "=", order.name)],
    },
)
demo_action(
    "demo_states",
    {
        "name": "States / Warehouses",
        "res_model": "res.country.state",
        "view_mode": "list",
        "domain": [("country_id", "=", country_do.id), ("warehouse_ids", "!=", False)],
    },
)
print("warehouse", order.warehouse_id.name, "transfer", transfer.name, transfer.state)
env.cr.commit()
print("SEED OK")
