# Seed for the manual of l10n_do_rnc_validation (Validacion de RNC/Cedula).
#
# Builds, from a CLEAN DB, a Dominican company and the contacts the manual
# shows, created through the module's own create() override so the screenshots
# reflect what the module actually produces:
#
#   * 131793916  (9 digits, RNC)     -> INDEXA SRL, company
#   * 101850043  (9 digits, RNC)     -> ITERATIVO SRL, company
#   * 00113918205 (11 digits, cedula) -> JOSE LUIS LOPEZ, individual
#   * 131566332  -> created WITHOUT a lookup, to show the duplicate guard
#
# The Indexa API is stubbed during the seed: it needs a token, and the DGII SOAP
# fallback is currently answering HTML instead of XML, so a live lookup would
# leave every contact empty and the manual would document nothing. The stub
# returns the payload shape the real service returns; everything downstream
# (create(), _get_updated_vals(), _compute_is_company()) is the module's code.
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

from unittest.mock import MagicMock, patch

MODULE = "l10n_do_rnc_validation"
API = "odoo.addons.l10n_do_rnc_validation.models.res_partner.requests.get"
DGII = "odoo.addons.l10n_do_rnc_validation.models.res_partner.rnc.check_dgii"

company = env.ref("base.main_company")
do = env.ref("base.do")

# -- 0. Espanol --------------------------------------------------------------
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

env["ir.module.module"].search(
    [
        ("name", "in", ["l10n_do_rnc_validation", "l10n_do_accounting", "l10n_do"]),
        ("state", "=", "installed"),
    ]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Compania RD + plan contable dominicano -------------------------------
company.l10_do_can_validate_rnc = False
company.write(
    {
        "name": "INDEXA SRL",
        "country_id": do.id,
        "vat": "131793916",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
    }
)
company.partner_id.lang = "es_DO"
env["account.chart.template"].try_loading("do", company=company, install_demo=False)
company.l10_do_can_validate_rnc = True

Partner = env["res.partner"]


def indexa_response(payload):
    resp = MagicMock()
    resp.json.return_value = {"status": "success", "data": [payload]}
    return resp


def empty_response():
    resp = MagicMock()
    resp.json.return_value = {"status": "success", "data": []}
    return resp


# -- 2. Contacto empresa creado desde el RNC ---------------------------------
# Lo unico que se escribe es el RNC: nombre, referencia, telefono y direccion
# los trae el modulo.
with patch(API, return_value=indexa_response({
    "business_name": "ITERATIVO SRL",
    "tradename": "ITERATIVO",
    "phone": "8092227777",
    "street": "El Vergel",
    "street_number": "23",
    "sector": "ENSANCHE NACO",
    "rnc": "101850043",
})):
    iterativo = Partner.create({"vat": "101850043"})
iterativo.country_id = do

# -- 3. Contacto persona creado desde la cedula ------------------------------
with patch(API, return_value=indexa_response({
    "business_name": "JOSE LUIS LOPEZ PEREZ",
    "tradename": "",
    "phone": "8095551234",
    "street": "Duarte",
    "street_number": "45",
    "sector": "GAZCUE",
    "rnc": "00113918205",
})):
    jose = Partner.create({"vat": "00113918205"})
jose.country_id = do

# -- 4. Contacto sin datos remotos (la API no lo conoce) ---------------------
# El modulo cae al servicio de la DGII; aqui tampoco hay datos, asi que solo
# queda el RNC y el nombre que escribio el usuario.
with patch(API, return_value=empty_response()), patch(DGII, return_value=None):
    sin_datos = Partner.create({"name": "SUPLIDOR SIN REGISTRO", "vat": "131566332"})
sin_datos.country_id = do

# -- 5. Vista de lista que muestra lo que llena el modulo ---------------------
# La lista de contactos del nucleo no trae ni la referencia ni el indicador de
# empresa, que es justo lo que hay que ver aqui.
list_view = env["ir.ui.view"].create({
    "name": "res.partner.list.rnc.demo",
    "model": "res.partner",
    "type": "list",
    "arch": """
        <list string="Contactos dominicanos" create="false">
            <field name="name"/>
            <field name="vat" string="RNC/Cedula"/>
            <field name="ref" string="Nombre comercial"/>
            <field name="is_company" string="Es una empresa" widget="boolean"/>
            <field name="phone"/>
            <field name="street"/>
        </list>
    """,
})
env["ir.model.data"].create({
    "module": MODULE,
    "name": "demo_partner_list_view",
    "model": "ir.ui.view",
    "res_id": list_view.id,
    "noupdate": True,
})

# -- 6. Acciones demo para las capturas --------------------------------------


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {
            "module": MODULE,
            "name": xmlid,
            "model": "ir.actions.act_window",
            "res_id": act.id,
            "noupdate": True,
        }
    )
    return act


demo_action("demo_partner_company", {
    "name": "Contacto empresa (RNC)",
    "res_model": "res.partner",
    "view_mode": "form",
    "res_id": iterativo.id,
})
demo_action("demo_partner_person", {
    "name": "Contacto persona (Cedula)",
    "res_model": "res.partner",
    "view_mode": "form",
    "res_id": jose.id,
})
partner_list = demo_action("demo_partner_list", {
    "name": "Contactos dominicanos",
    "res_model": "res.partner",
    "view_mode": "list,form",
    "domain": "[('vat', '!=', False)]",
})
partner_list.write({"view_ids": [(5, 0, 0), (0, 0, {"sequence": 1, "view_mode": "list", "view_id": list_view.id})]})
demo_action("demo_partner_new", {
    "name": "Nuevo contacto",
    "res_model": "res.partner",
    "view_mode": "form",
})
demo_action("demo_params", {
    "name": "Parametros del sistema",
    "res_model": "ir.config_parameter",
    "view_mode": "list",
    "domain": "['|', ('key', 'like', 'rnc.indexa'), ('key', 'like', 'l10n_do_rnc_validation')]",
})

env.cr.commit()
print(
    "SEED OK: %s (empresa=%s), %s (persona=%s), %s (sin datos)"
    % (
        iterativo.name,
        iterativo.is_company,
        jose.name,
        jose.is_company,
        sin_datos.name,
    )
)
