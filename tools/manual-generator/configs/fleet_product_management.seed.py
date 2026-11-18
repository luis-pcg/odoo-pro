# Datos de ejemplo para el manual de fleet_product_management (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "fleet_product_management"

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
    env.ref("fleet.fleet_group_manager")
    | env.ref("stock.group_stock_manager")
    | env.ref("sales_team.group_sale_manager")
)
company.partner_id.lang = "es_DO"

Voltage = env["product.voltage"]
v48 = Voltage.create({"name": "48V"})
v72 = Voltage.create({"name": "72V"})
Voltage.create({"name": "96V"})

categ = env["product.category"].create({"name": "Vehículos eléctricos"})
Product = env["product.product"]
controller = Product.create({"name": "Controlador X200", "vehicle_part_type": "controller", "type": "consu"})
engine = Product.create({"name": "Motor EV-100", "vehicle_part_type": "engine", "type": "consu"})
battery = Product.create({"name": "Batería de litio 48V", "vehicle_part_type": "battery", "type": "consu"})

brand = env["fleet.vehicle.model.brand"].create({"name": "Progressa"})
cargo = env["fleet.vehicle.model"].create({"name": "Cargo E1", "brand_id": brand.id})
urban = env["fleet.vehicle.model"].create({"name": "Urban E2", "brand_id": brand.id})

Vehicle = env["fleet.vehicle"]


def vehicle(model, color, plate, voltage, **extra):
    record = Vehicle.create(
        {"model_id": model.id, "color": color, "is_product": True, "categ_id": categ.id, "voltage_id": voltage.id, **extra}
    )
    record.product_id.default_code = plate
    return record


new_vehicle = vehicle(cargo, "Blanco", "G000101", v48)
stock_vehicle = vehicle(
    cargo,
    "Gris",
    "G000102",
    v48,
    controller_product_id=controller.id,
    engine_product_id=engine.id,
    battery_product_id=battery.id,
)
sold_vehicle = vehicle(urban, "Azul", "G000201", v72)
scrap_vehicle = vehicle(urban, "Rojo", "G000202", v72)

warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
stock = warehouse.lot_stock_id
supplier = env.ref("stock.stock_location_suppliers")
customer_loc = env.ref("stock.stock_location_customers")
customer = env["res.partner"].create({"name": "Distribuidora del Cibao SRL", "city": "Santiago"})


def transfer(picking_type, src, dest, products, partner=False, origin=False):
    picking = env["stock.picking"].create(
        {
            "picking_type_id": picking_type.id,
            "location_id": src.id,
            "location_dest_id": dest.id,
            "partner_id": partner and partner.id,
            "origin": origin,
            "move_ids": [
                Command.create(
                    {
                        "product_id": p.id,
                        "product_uom_qty": 1,
                        "uom_id": p.uom_id.id,
                        "location_id": src.id,
                        "location_dest_id": dest.id,
                    }
                )
                for p in products
            ],
        }
    )
    picking.action_confirm()
    picking.action_assign()
    for move in picking.move_ids:
        move.quantity = 1
        move.picked = True
    picking._action_done()
    return picking


transfer(
    warehouse.in_type_id,
    supplier,
    stock,
    (stock_vehicle | sold_vehicle | scrap_vehicle).product_id,
    origin="P00001",
)
delivery = transfer(warehouse.out_type_id, stock, customer_loc, sold_vehicle.product_id, partner=customer, origin="S00001")
scrap = env["stock.move"].create(
    {
        "is_scrap": True,
        "product_id": scrap_vehicle.product_id.id,
        "uom_id": scrap_vehicle.product_id.uom_id.id,
        "quantity": 1,
        "location_id": stock.id,
    }
)
scrap.action_scrap()


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


form_action("demo_vehicle_new", new_vehicle)
form_action("demo_vehicle_stock", stock_vehicle)
form_action("demo_vehicle_sold", sold_vehicle)
form_action("demo_vehicle_product", stock_vehicle.product_id.product_tmpl_id)
form_action("demo_component", controller.product_tmpl_id)
print(
    "SEED OK",
    [(v.display_name, v.state_id.name, v.partner_id.name) for v in new_vehicle | stock_vehicle | sold_vehicle | scrap_vehicle],
)
env.cr.commit()
