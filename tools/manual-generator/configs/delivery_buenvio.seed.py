# Datos de ejemplo para el manual de delivery_buenvio (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "delivery_buenvio"

company = env.ref("base.main_company")
country_do = env.ref("base.do")
distrito = env.ref("base.state_DO_01")
santiago = env.ref("base.state_DO_25")
company.write(
    {
        "name": "Empresa Dominicana SRL",
        "street": "Av. Winston Churchill",
        "street2": "Torre Empresarial, piso 4",
        "city": "Santo Domingo",
        "state_id": distrito.id,
        "country_id": country_do.id,
        "phone": "+1 809-555-0100",
        "buenvio_building_number": "1099",
        "buenvio_sector_number": "Piantini",
        "order_shipment_when_confirming_your_picking": True,
    }
)
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= env.ref("sales_team.group_sale_manager") | env.ref("stock.group_stock_manager")
admin.partner_id.write(
    {
        "street": "Calle El Conde 55",
        "city": "Santo Domingo",
        "state_id": distrito.id,
        "country_id": country_do.id,
        "phone": "+1 809-555-0111",
        "buenvio_building_number": "55",
        "buenvio_sector_number": "Zona Colonial",
    }
)
company.partner_id.lang = "es_DO"

carrier = env["delivery.carrier"].create(
    {
        "name": "Buenvío",
        "delivery_type": "buenvio",
        "buenvio_api_key": "API-KEY-DE-BUENVIO",
        "product_id": env.ref("delivery_buenvio.product_product_delivery_buenvio_world").id,
        "country_ids": [Command.set(country_do.ids)],
    }
)

stock = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1).lot_stock_id
Product = env["product.product"]
vase = Product.create(
    {"name": "Florero de cerámica", "is_storable": True, "weight": 2.0, "fragile": True, "list_price": 1850}
)
coffee = Product.create({"name": "Café Santo Domingo 1 lb", "is_storable": True, "weight": 0.45, "list_price": 395})
env["stock.quant"]._update_available_quantity(vase, stock, 40)
env["stock.quant"]._update_available_quantity(coffee, stock, 200)

customer = env["res.partner"].create(
    {
        "name": "María Rodríguez",
        "email": "maria.rodriguez@example.com",
        "phone": "+1 809-221-2345",
        "street": "Calle del Sol 23",
        "city": "Santiago de los Caballeros",
        "state_id": santiago.id,
        "country_id": country_do.id,
        "buenvio_building_number": "23",
        "buenvio_sector_number": "Los Jardines",
    }
)


def order():
    so = env["sale.order"].create(
        {
            "partner_id": customer.id,
            "order_line": [
                Command.create({"product_id": vase.id, "product_uom_qty": 1}),
                Command.create({"product_id": coffee.id, "product_uom_qty": 3}),
            ],
        }
    )
    so.set_delivery_line(carrier, 350.0)
    so.action_confirm()
    return so


pending = order()
pending_picking = pending.picking_ids[:1]
shipped = order()
shipped_picking = shipped.picking_ids[:1]
shipped_picking.write(
    {
        "carrier_tracking_ref": "BV-2026-000123",
        "carrier_price": 350.0,
        "buenvio_order_id": "48213",
        "buenvio_message": "Orden creada correctamente",
        "buenvio_okay": True,
    }
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


form_action("demo_carrier", carrier)
form_action("demo_company", company)
form_action("demo_customer", customer)
form_action("demo_country", country_do)
form_action("demo_product", vase)
form_action("demo_order", pending)
form_action("demo_picking_pending", pending_picking)
form_action("demo_picking_shipped", shipped_picking)
print(
    "seed delivery_buenvio OK",
    pending.name,
    pending_picking.name,
    pending_picking.send_status,
    shipped_picking.name,
    shipped_picking.send_status,
)
env.cr.commit()
