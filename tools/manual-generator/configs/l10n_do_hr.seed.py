# Seed for the manual of l10n_do_hr — "Parientes del empleado" (dónde quedaron
# los campos tras la migración 17 -> 19). Desde una base LIMPIA crea una compañía
# RD, el empleado "Emmanuel Peña" (el del ticket) y tres parientes que ejercitan
# los dos campos reportados como faltantes:
#
#   * María Altagracia Peña  — Cónyuge. Retener per Cápita = Sí, Contacto de
#     emergencia = Sí. (aparece en el conteo de dependientes de nómina)
#   * Pedro Luis Peña        — Hijo. Retener per Cápita = Sí.
#   * Rosa Mercedes Peña     — Madre. Contacto de emergencia = Sí.
#
# Ejecutado dentro de `odoo shell` (`env` disponible). Termina con commit.
from datetime import date

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
TZ = "America/Santo_Domingo"

# ── 0. Español ────────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

# ── 1. Compañía RD ────────────────────────────────────────────────────────────
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
    company.write({"country_id": do.id})

# ── 2. Empleado "Emmanuel Peña" ───────────────────────────────────────────────
emp = env["hr.employee"].search([("identification_id", "=", "00114857412")], limit=1)
if not emp:
    emp = env["hr.employee"].create({
        "name": "Emmanuel Peña",
        "company_id": company.id,
        "country_id": do.id,
        "identification_id": "00114857412",
        "l10n_do_social_security_number": "80012345",
        "l10n_do_has_papers": True,
        "tz": TZ,
    })

# ── 3. Parientes ──────────────────────────────────────────────────────────────
rel_spouse = env.ref("l10n_do_hr.relation_spouse")
rel_child = env.ref("l10n_do_hr.relation_child")
rel_parent = env.ref("l10n_do_hr.relation_parent")


def make_relative(name, relation, cedula, vals):
    existing = env["hr.employee.relative"].search(
        [("employee_id", "=", emp.id), ("name", "=", name)], limit=1)
    if existing:
        return existing
    base = {
        "employee_id": emp.id,
        "relation_id": relation.id,
        "name": name,
        "l10n_do_identification_id": cedula,
    }
    base.update(vals)
    return env["hr.employee.relative"].create(base)


spouse = make_relative(
    "María Altagracia Peña", rel_spouse, "00198765432",
    {
        "gender": "female",
        "date_of_birth": date(1990, 5, 12),
        "phone_number": "809-555-0142",
        "l10n_do_is_active": True,          # Retener per Cápita
        "l10n_do_emergency_contact": True,  # ¿Es un contacto de Emergencia?
    },
)
make_relative(
    "Pedro Luis Peña", rel_child, "40255566778",
    {
        "gender": "male",
        "date_of_birth": date(2015, 9, 3),
        "l10n_do_is_active": True,          # Retener per Cápita
    },
)
make_relative(
    "Rosa Mercedes Peña", rel_parent, "00133344556",
    {
        "gender": "female",
        "date_of_birth": date(1962, 1, 20),
        "phone_number": "809-555-0199",
        "l10n_do_emergency_contact": True,  # ¿Es un contacto de Emergencia?
    },
)

# ── 4. Acciones demo para las capturas ────────────────────────────────────────
def demo_action(xmlid, vals):
    existing = env.ref("l10n_do_hr.%s" % xmlid, raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": "l10n_do_hr", "name": xmlid,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })
    return act


demo_action("demo_employee_emmanuel", {
    "name": "Empleado - Emmanuel Peña", "res_model": "hr.employee",
    "view_mode": "form", "res_id": emp.id, "domain": "[('id', '=', %d)]" % emp.id,
})
demo_action("demo_relatives_list", {
    "name": "Parientes - Emmanuel Peña", "res_model": "hr.employee.relative",
    "view_mode": "list,form",
    "domain": "[('employee_id', '=', %d)]" % emp.id,
    "context": "{'default_employee_id': %d}" % emp.id,
})
demo_action("demo_relative_form", {
    "name": "Pariente - María Altagracia Peña", "res_model": "hr.employee.relative",
    "view_mode": "form", "res_id": spouse.id,
})

env.cr.commit()
