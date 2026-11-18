# Datos de ejemplo para el manual de pos_azul (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
MODULE = "pos_azul"

company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL"})
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= env.ref("point_of_sale.group_pos_manager")
company.partner_id.lang = "es_DO"

bank = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
azul = env["pos.payment.method"].create(
    {
        "name": "Tarjeta Azul",
        "type": "bank",
        "journal_id": bank.id,
        "payment_method_type": "terminal",
        "payment_provider": "azul_ingenico",
        "ingenico_terminal_ip": "localhost",
        "ingenico_terminal_port": "9001",
        "ingenico_timeout": 90,
    }
)
config = env["pos.config"].search([("company_id", "=", company.id)], limit=1)
if not config:
    config = env["pos.config"].create({"name": "Tienda Principal"})
config.write({"name": "Tienda Principal", "payment_method_ids": [(4, azul.id)]})

for name, price in [("Café molido 1 lb", 450.0), ("Botella de agua 20 oz", 35.0), ("Galletas de avena", 120.0)]:
    env["product.product"].create({"name": name, "list_price": price, "available_in_pos": True, "taxes_id": [(5, 0, 0)]})

if not config.current_session_id:
    session = env["pos.session"].create({"config_id": config.id, "user_id": admin.id})
    session.set_opening_control(0, "")


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


demo_action("demo_payment_method", {"name": azul.name, "res_model": "pos.payment.method", "view_mode": "form", "res_id": azul.id})
print("seed pos_azul OK config=%s session=%s method=%s" % (config.id, config.current_session_id.id, azul.id))
env.cr.commit()
