# Seed data for the stock_analytic_distribution_features user manual.
# Executed inside `odoo shell` (the `env` global is provided).
#
# Builds a self-contained solar-installer demo:
#   0. Spanish UI (es_DO) + analytic accounting group on admin.
#   1. project_stock_account installed on the fly, so the auto_install bridge
#      stock_analytic_distribution_features_project is active and the project flow can
#      be shown next to the manual one.
#   2. Analytic plan "Proyectos" with three works + a native project.
#   3. Storable products at standard cost, with stock on hand.
#   4. The scenarios the manual walks through:
#        A. Validated delivery note, 100 % to one work.
#        B. Picked but NOT validated delivery note, 60/40 split -> the cost is
#           already visible. This is the reason the module exists.
#        C. Delivery note without distribution.
#        D. Scrap charged to a work.
#        E. Delivery note driven by the project (native v19 flow).
#        F. Project + manual distribution -> the manual one wins, no double count.
#   5. A mandatory analytic plan for the `stock_move` domain, left configured so
#      the manual can show the setting (the demo pickings are already validated).
#
# Ends with `env.cr.commit()` and prints "SEED OK".
from odoo import SUPERUSER_ID, api

company = env.ref("base.main_company")

# ── 0. Spanish UI ────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    wiz = env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True})
    wiz.lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env.cr.commit()

# ── 1. Bridge module: install project_stock_account (auto_installs the bridge) ─
to_install = env["ir.module.module"].search(
    [("name", "=", "project_stock_account"), ("state", "=", "uninstalled")]
)
if to_install:
    to_install.button_immediate_install()
    env = api.Environment(env.cr, SUPERUSER_ID, {})
    company = env.ref("base.main_company")

admin = env.ref("base.user_admin")
admin.write({
    "group_ids": [
        (4, env.ref("analytic.group_analytic_accounting").id),
        (4, env.ref("stock.group_stock_multi_locations").id),
        # The "Analytics" block of the Invoicing settings is gated by
        # account.group_account_user; in v19 the manager group does not imply it.
        (4, env.ref("account.group_account_user").id),
        (4, env.ref("account.group_account_manager").id),
    ]
})
# The settings checkbox reflects what base.group_user implies, not the current
# user's groups, so it has to be switched on through res.config.settings.
env["res.config.settings"].create({"group_analytic_accounting": True}).execute()

# ── 2. Analytic plan, works, native project ──────────────────────────────────
Plan = env["account.analytic.plan"]
plan = Plan.search([("name", "=", "Proyectos")], limit=1) or Plan.create({"name": "Proyectos"})
plan_column = plan._column_name()

Account = env["account.analytic.account"]


def get_account(code, name):
    acc = Account.search([("code", "=", code)], limit=1)
    if not acc:
        acc = Account.create(
            {"code": code, "name": name, "plan_id": plan.id, "company_id": company.id}
        )
    return acc


obra_a = get_account("PROY-001", "Planta Solar Bávaro")
obra_b = get_account("PROY-002", "Techo Solar Santiago")
obra_c = get_account("PROY-003", "Parque Solar Azua")

Project = env["project.project"]
project = Project.search([("name", "=", "Parque Solar Azua")], limit=1)
if not project:
    project = Project.create({"name": "Parque Solar Azua"})
project.write({plan_column: obra_c.id})

# ── 3. Products and stock ────────────────────────────────────────────────────
Categ = env["product.category"]
categ = Categ.search([("name", "=", "Materiales Solares")], limit=1)
if not categ:
    categ = Categ.create(
        {
            "name": "Materiales Solares",
            "property_cost_method": "standard",
            "property_valuation": "periodic",
        }
    )

warehouse = env["stock.warehouse"].search([("company_id", "=", company.id)], limit=1)
stock_location = warehouse.lot_stock_id
customer_location = env.ref("stock.stock_location_customers")
supplier_location = env.ref("stock.stock_location_suppliers")
uom_unit = env.ref("uom.product_uom_unit")

Product = env["product.product"]


def get_product(code, name, price):
    p = Product.search([("default_code", "=", code)], limit=1)
    if not p:
        p = Product.create(
            {
                "name": name,
                "default_code": code,
                "is_storable": True,
                "categ_id": categ.id,
                "uom_id": uom_unit.id,
                "standard_price": price,
            }
        )
    p.standard_price = price
    return p


panel = get_product("SOL-PANEL", "Panel solar 550W", 12500.0)
inversor = get_product("SOL-INV", "Inversor 5kW", 45000.0)
estructura = get_product("SOL-EST", "Estructura de montaje", 3200.0)

Quant = env["stock.quant"]
for prod, qty in ((panel, 500), (inversor, 60), (estructura, 400)):
    Quant._update_available_quantity(prod, stock_location, qty)

# ── 4. Scenarios ─────────────────────────────────────────────────────────────
Picking = env["stock.picking"]
Move = env["stock.move"]
type_out = warehouse.out_type_id


def build_picking(origin, lines, project_rec=None):
    vals = {
        "picking_type_id": type_out.id,
        "location_id": stock_location.id,
        "location_dest_id": customer_location.id,
        "origin": origin,
    }
    if project_rec:
        vals["project_id"] = project_rec.id
    picking = Picking.create(vals)
    for product, qty, distribution in lines:
        Move.create(
            {
                "product_id": product.id,
                "product_uom_qty": qty,
                "product_uom": product.uom_id.id,
                "picking_id": picking.id,
                "location_id": stock_location.id,
                "location_dest_id": customer_location.id,
                "analytic_distribution": distribution,
            }
        )
    picking.action_confirm()
    picking.action_assign()
    for move in picking.move_ids:
        move.quantity = move.product_uom_qty
    return picking


# A. Validated, 100 % to one work
pick_a = build_picking(
    "OBRA PROY-001 / despacho 1",
    [(panel, 20, {str(obra_a.id): 100}), (estructura, 20, {str(obra_a.id): 100})],
)
pick_a.move_ids.picked = True
pick_a.button_validate()

# B. Picked but NOT validated, 60/40 -> estimated cost already visible
pick_b = build_picking(
    "OBRAS PROY-001 + PROY-002 / despacho compartido",
    [(inversor, 4, {str(obra_a.id): 60, str(obra_b.id): 40})],
)
pick_b.move_ids.picked = True

# C. No distribution
pick_c = build_picking("Despacho sin imputar", [(panel, 5, None)])
pick_c.move_ids.picked = True
pick_c.button_validate()

# D. Scrap
scrap = env["stock.scrap"].create(
    {
        "product_id": panel.id,
        "product_uom_id": panel.uom_id.id,
        "scrap_qty": 2,
        "location_id": stock_location.id,
        "origin": "Panel roto en obra PROY-002",
        "analytic_distribution": {str(obra_b.id): 100},
    }
)
scrap.action_validate()

# E. Native project flow
type_out.analytic_costs = True
pick_e = build_picking("Proyecto Azua / despacho nativo", [(panel, 8, None)], project_rec=project)
pick_e.move_ids.picked = True
pick_e.button_validate()

# F. Project + manual distribution -> manual wins
pick_f = build_picking(
    "Proyecto Azua / despacho reimputado",
    [(inversor, 2, {str(obra_a.id): 100})],
    project_rec=project,
)
pick_f.move_ids.picked = True
pick_f.button_validate()

# A draft picking, left open so the manual can show the empty widget
pick_draft = build_picking("OBRA PROY-002 / despacho pendiente", [(estructura, 12, None)])

# ── 5. Mandatory analytic plan on the stock_move domain ──────────────────────
Applicability = env["account.analytic.applicability"]
if not Applicability.search([("business_domain", "=", "stock_move")], limit=1):
    Applicability.create(
        {
            "business_domain": "stock_move",
            "analytic_plan_id": plan.id,
            "applicability": "mandatory",
        }
    )

env.cr.commit()

aal_count = env["account.analytic.line"].search_count([(plan_column, "!=", False)])
print(
    "SEED OK: plan=%s columna=%s cuentas=3 conduces=%d partidas_analiticas=%d"
    % (plan.name, plan_column, Picking.search_count([]), aal_count)
)
