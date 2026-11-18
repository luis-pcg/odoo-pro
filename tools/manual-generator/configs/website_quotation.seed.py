# Datos de ejemplo para el manual de website_quotation (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo import Command

MODULE = "website_quotation"

country_do = env.ref("base.do")
distrito = env.ref("base.state_DO_01")
company = env.ref("base.main_company")
company.write(
    {
        "name": "Empresa Dominicana SRL",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
        "state_id": distrito.id,
        "country_id": country_do.id,
        "phone": "+1 809-555-0100",
    }
)
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
website = env["website"].search([], limit=1)
website.write({"name": "Tienda Empresa Dominicana", "language_ids": [Command.link(es.id)], "default_lang_id": es.id})
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= env.ref("sales_team.group_sale_manager")
admin.partner_id.write(
    {
        "name": "María Rodríguez",
        "email": "maria.rodriguez@example.com",
        "street": "Calle El Conde 55",
        "city": "Santo Domingo",
        "zip": "10210",
        "state_id": distrito.id,
        "country_id": country_do.id,
        "phone": "+1 809-555-0111",
    }
)

Product = env["product.product"]


def product(name, price):
    found = Product.search([("name", "=", name)], limit=1)
    return found or Product.create(
        {"name": name, "list_price": price, "type": "consu", "sale_ok": True, "website_published": True}
    )


chair = product("Silla ergonómica de oficina", 8500.0)
desk = product("Escritorio ejecutivo en roble", 24500.0)
lamp = product("Lámpara LED de escritorio", 1850.0)

env["sale.order"].search([("partner_id", "=", admin.partner_id.id), ("state", "=", "draft")]).unlink()
cart = env["sale.order"].create(
    {
        "partner_id": admin.partner_id.id,
        "website_id": website.id,
        "order_line": [
            Command.create({"product_id": chair.id, "product_uom_qty": 6}),
            Command.create({"product_id": desk.id, "product_uom_qty": 2}),
            Command.create({"product_id": lamp.id, "product_uom_qty": 6}),
        ],
    }
)

act = env["ir.actions.act_window"].create(
    {
        "name": "Cotizaciones solicitadas desde la tienda",
        "res_model": "sale.order",
        "view_mode": "list,form",
        "domain": [("website_id", "!=", False)],
    }
)
env["ir.model.data"].create(
    {"module": MODULE, "name": "demo_web_quotations", "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
)
env.cr.commit()
print("SEED OK", cart.name, cart.state, cart.amount_total)
