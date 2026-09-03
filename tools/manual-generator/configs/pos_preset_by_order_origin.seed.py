# Seed del manual de pos_preset_by_order_origin (Preajuste de PdV segun el
# origen de la orden). Desde una base LIMPIA arma:
#
#   * Compania "Pasteleria del Jardin" (RD) con plan contable generico y DOP.
#   * Un PdV en modo restaurante con un piso y cuatro mesas.
#   * Los dos preajustes de fabrica renombrados y "silenciosos" (sin
#     identificacion ni franjas horarias): Comer en el local / Para llevar.
#   * Los dos ajustes del modulo: En mesa = Comer en el local,
#     Venta directa = Para llevar (y Predeterminado = Para llevar, que es lo
#     que permite que una venta directa vacia adopte la mesa).
#   * Tres productos de pasteleria y un metodo de pago en efectivo.
#   * La sesion del PdV ya abierta, para que las capturas entren directo al
#     plano de mesas.
#
# Se ejecuta dentro de `odoo shell` (el global `env` esta disponible) y termina
# con env.cr.commit().

company = env.ref("base.main_company")
do = env.ref("base.do")
admin = env.ref("base.user_admin")


def show(label, value):
    print("   %-28s %s" % (label + ":", value))


# ── 0. Espanol dominicano ────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
company = company.with_env(env)

# ── 1. Compania y plan contable ──────────────────────────────────────────────
company.write({"name": "Pastelería del Jardín", "country_id": do.id})
company.partner_id.lang = "es_DO"
if not company.chart_template:
    env["account.chart.template"].try_loading(
        "generic_coa", company=company, install_demo=False
    )
dop = env.ref("base.DOP")
dop.active = True
if company.currency_id != dop:
    company.currency_id = dop

# ── 2. Productos de la vitrina ───────────────────────────────────────────────
categ = env["pos.category"].create({"name": "Pastelería"})
products = env["product.template"].create(
    [
        {
            "name": "Suspiro de fresa",
            "list_price": 180.00,
            "type": "consu",
            "available_in_pos": True,
            "pos_categ_ids": [(6, 0, categ.ids)],
            "taxes_id": [(6, 0, [])],
        },
        {
            "name": "Brownie de nuez",
            "list_price": 140.00,
            "type": "consu",
            "available_in_pos": True,
            "pos_categ_ids": [(6, 0, categ.ids)],
            "taxes_id": [(6, 0, [])],
        },
        {
            "name": "Café con leche",
            "list_price": 95.00,
            "type": "consu",
            "available_in_pos": True,
            "pos_categ_ids": [(6, 0, categ.ids)],
            "taxes_id": [(6, 0, [])],
        },
    ]
)

# ── 3. Metodo de pago en efectivo ────────────────────────────────────────────
cash_journal = env["account.journal"].search(
    [("type", "=", "cash"), ("company_id", "=", company.id)], limit=1
)
if not cash_journal:
    cash_journal = env["account.journal"].create(
        {"name": "Efectivo", "code": "CSH", "type": "cash", "company_id": company.id}
    )
cash_method = env["pos.payment.method"].create(
    {"name": "Efectivo", "journal_id": cash_journal.id, "company_id": company.id}
)

# ── 4. Punto de venta en modo restaurante ────────────────────────────────────
config = env["pos.config"].create(
    {
        "name": "Salón Pastelería",
        "module_pos_restaurant": True,
        "company_id": company.id,
        "payment_method_ids": [(6, 0, cash_method.ids)],
        "iface_available_categ_ids": [(6, 0, categ.ids)],
    }
)
config.floor_ids.unlink()
floor = env["restaurant.floor"].create(
    {"name": "Salón", "pos_config_ids": [(6, 0, config.ids)]}
)
env["restaurant.table"].create(
    [
        {
            "table_number": number,
            "floor_id": floor.id,
            "seats": 4,
            "shape": "square",
            "position_h": position_h,
            "position_v": position_v,
        }
        for number, position_h, position_v in (
            (1, 120, 120),
            (2, 340, 120),
            (3, 120, 320),
            (4, 340, 320),
        )
    ]
)

# ── 5. Preajustes silenciosos ────────────────────────────────────────────────
# Los de fabrica piden nombre (Takeout) o direccion (Delivery) y abren dialogos
# en cada orden: el modulo asigna el preajuste sin pasar por ellos, asi que hay
# que apagarlos.
dine_in = env.ref("pos_restaurant.pos_takein_preset")
takeaway = env.ref("pos_restaurant.pos_takeout_preset")
dine_in.write({"name": "Comer en el local", "identification": "none", "use_timing": False})
takeaway.write(
    {
        "name": "Para llevar",
        "identification": "none",
        "use_timing": False,
        "resource_calendar_id": False,
    }
)

# ── 6. Los ajustes del modulo ────────────────────────────────────────────────
config.write(
    {
        "use_presets": True,
        "available_preset_ids": [(6, 0, (takeaway | dine_in).ids)],
        "default_preset_id": takeaway.id,
        "direct_sale_preset_id": takeaway.id,
        "table_preset_id": dine_in.id,
    }
)

# ── 7. Sesion abierta ────────────────────────────────────────────────────────
config.with_user(admin).open_ui()
session = config.current_session_id
session.with_user(admin).set_opening_control(0, "")

env.cr.commit()

print("SEED OK")
show("Compañía", "%s (%s)" % (company.name, company.currency_id.name))
show("Punto de venta", "%s (id %s)" % (config.name, config.id))
show("Piso y mesas", "%s / %s" % (floor.name, len(floor.table_ids)))
show("Preajuste en mesa", config.table_preset_id.name)
show("Preajuste venta directa", config.direct_sale_preset_id.name)
show("Predeterminado", config.default_preset_id.name)
show("Productos", ", ".join(products.mapped("name")))
show("Sesión", "%s (%s)" % (session.name, session.state))
