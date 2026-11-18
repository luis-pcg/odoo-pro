# Datos de ejemplo para el manual de fleet_product_rules (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
MODULE = "fleet_product_rules"

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

state_stock = env.ref("fleet_product_management.fleet_vehicle_state_stock")
state_sold = env.ref("fleet_product_management.fleet_vehicle_state_sold")

state_stock.rule_ids.filtered(lambda r: r.field == "rent_periodicity").write({"value": True})
state_sold.rule_ids.write({"value": False, "readonly": True})

brand = env["fleet.vehicle.model.brand"].create({"name": "Progressa"})
cargo = env["fleet.vehicle.model"].create({"name": "Cargo E1", "brand_id": brand.id})
urban = env["fleet.vehicle.model"].create({"name": "Urban E2", "brand_id": brand.id})

Vehicle = env["fleet.vehicle"]


def vehicle(model, color, plate, state=False):
    record = Vehicle.create({"model_id": model.id, "color": color, "is_product": True})
    record.product_id.default_code = plate
    if state:
        record.with_context(force_vehicle_state=True).write({"state_id": state.id})
    return record


new_vehicle = vehicle(cargo, "Blanco", "G000101")
stock_vehicle = vehicle(cargo, "Gris", "G000102", state_stock)
weekly_vehicle = vehicle(urban, "Verde", "G000103")
weekly_vehicle.product_id.rent_periodicity = "weeks"
weekly_vehicle.with_context(force_vehicle_state=True).write({"state_id": state_stock.id})
sold_vehicle = vehicle(urban, "Azul", "G000201", state_sold)
free_vehicle = vehicle(urban, "Rojo", "G000202", state_sold)
free_vehicle.product_id.product_tmpl_id.write({"product_rules_ok": False, "sale_ok": True})


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


form_action("demo_state_stock", state_stock)
form_action("demo_state_sold", state_sold)
form_action("demo_product_stock", stock_vehicle.product_id.product_tmpl_id)
form_action("demo_product_weekly", weekly_vehicle.product_id.product_tmpl_id)
form_action("demo_product_sold", sold_vehicle.product_id.product_tmpl_id)
form_action("demo_product_free", free_vehicle.product_id.product_tmpl_id)
print(
    "SEED OK",
    [
        (v.display_name, v.state_id.name, v.product_id.sale_ok, v.product_id.purchase_ok, v.product_id.rent_periodicity)
        for v in new_vehicle | stock_vehicle | weekly_vehicle | sold_vehicle | free_vehicle
    ],
)
env.cr.commit()
