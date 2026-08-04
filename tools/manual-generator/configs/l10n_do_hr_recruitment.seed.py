# Seed para el manual de l10n_do_hr_recruitment — "Solicitud de Vacante".
#
# Desde una base LIMPIA arma un escenario completo de reclutamiento RD:
#
#   * Compañía "Empresa Dominicana SRL" (RD, es_DO)
#   * Departamentos Tecnología / Ventas / Recursos Humanos con gerentes
#   * Empleados: Carolina Reyes (reclutadora, ligada al usuario admin),
#     Ana Beltrán (gerente de Tecnología / solicitante), Pedro Guzmán
#     (entrevistador técnico), José Sánchez (candidato interno)
#   * Puestos: "Desarrollador Odoo Senior" y "Ejecutivo de Ventas" con
#     Titulaciones (l10n_do_recruitment_degree_ids)
#   * 4 solicitudes de vacante, una por estado relevante:
#       VAC00001 En proceso  (aprobada y abierta, con 3 postulantes)
#       VAC00002 Por aprobar (recién solicitada, Muy urgente)
#       VAC00003 Hecho       (cerrada, cobertura interna)
#       VAC00004 Rechazada
#   * Postulantes ligados a VAC00001 (uno con Informe de entrevista lleno)
#   * Acciones demo para que Playwright capture cada pantalla
#
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date, timedelta

MODULE = "l10n_do_hr_recruitment"

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
TZ = "America/Santo_Domingo"
today = date.today()

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

# ── 2. Departamentos ──────────────────────────────────────────────────────────
Department = env["hr.department"]


def make_department(name):
    dep = Department.search([("name", "=", name), ("company_id", "=", company.id)], limit=1)
    if not dep:
        dep = Department.create({"name": name, "company_id": company.id})
    return dep


dep_tech = make_department("Tecnología")
dep_sales = make_department("Ventas")
dep_hr = make_department("Recursos Humanos")

# ── 3. Empleados ──────────────────────────────────────────────────────────────
Employee = env["hr.employee"]


def employee_vals(name, cedula, department, job_title):
    return {
        "name": name,
        "company_id": company.id,
        "country_id": do.id,
        "identification_id": cedula,
        "department_id": department.id,
        "job_title": job_title,
        "tz": TZ,
    }


def make_employee(name, cedula, department, job_title):
    emp = Employee.search([("identification_id", "=", cedula)], limit=1)
    if emp:
        return emp
    return Employee.create(employee_vals(name, cedula, department, job_title))


admin = env.ref("base.user_admin")

# La reclutadora es el empleado del usuario admin: así el campo "Empleado
# solicitante" trae un valor por defecto y las reglas de registro (ver
# security/l10n_do_hr_recruitment_security.xml) tienen a quién comparar.
# La instalación de `hr` ya crea el empleado del admin: se reutiliza (hay un
# UNIQUE (user_id, company_id) en hr_employee), no se crea otro.
carolina = admin.employee_id or Employee.search([("user_id", "=", admin.id)], limit=1)
if carolina:
    carolina.write(employee_vals(
        "Carolina Reyes", "00110000001", dep_hr, "Analista de Reclutamiento"))
else:
    carolina = make_employee(
        "Carolina Reyes", "00110000001", dep_hr, "Analista de Reclutamiento")
    carolina.user_id = admin.id
ana = make_employee("Ana Beltrán", "00110000002", dep_tech, "Gerente de Tecnología")
pedro = make_employee("Pedro Guzmán", "00110000003", dep_tech, "Líder Técnico")
jose = make_employee("José Sánchez", "00110000004", dep_tech, "Desarrollador Odoo")
marcos = make_employee("Marcos Peña", "00110000005", dep_sales, "Gerente de Ventas")

dep_tech.manager_id = ana.id
dep_sales.manager_id = marcos.id
dep_hr.manager_id = carolina.id

# ── 4. Puestos de trabajo ─────────────────────────────────────────────────────
Job = env["hr.job"]
degree_bachelor = env.ref("hr_recruitment.degree_bachelor")
degree_licenced = env.ref("hr_recruitment.degree_licenced")


def make_job(name, department, degrees, **extra):
    job = Job.search([("name", "=", name), ("company_id", "=", company.id)], limit=1)
    if job:
        return job
    vals = {
        "name": name,
        "company_id": company.id,
        "department_id": department.id,
        "user_id": admin.id,  # Reclutador (usuario) del puesto
        "interviewer_ids": [(6, 0, [admin.id])],
        "l10n_do_recruitment_degree_ids": [(6, 0, [d.id for d in degrees])],
    }
    vals.update(extra)
    return Job.create(vals)


job_dev = make_job(
    "Desarrollador Odoo Senior",
    dep_tech,
    [degree_licenced],
    l10n_do_job_goal="Construir y mantener los módulos de la localización dominicana.",
    l10n_do_job_functions="Desarrollo Python/OWL, revisión de código, soporte a QA.",
    l10n_do_min_experience="more_than_3_years",
)
job_sales = make_job(
    "Ejecutivo de Ventas",
    dep_sales,
    [degree_bachelor],
    l10n_do_job_goal="Aumentar la cartera de clientes en la zona metropolitana.",
)

# Titulación del empleado (campo que aporta este módulo a la ficha)
jose.l10n_do_recruitment_degree_id = degree_licenced.id
pedro.l10n_do_recruitment_degree_id = degree_licenced.id

# ── 5. Solicitudes de vacante ─────────────────────────────────────────────────
# OJO: create() fuerza siempre state='to_be_approved' (ver models/
# l10n_do_hr_vacancy_application.py). El estado final se escribe después.
Vacancy = env["l10n.do.hr.vacancy.application"]


def make_vacancy(job, state, dates, **extra):
    vals = {
        "job_id": job.id,
        "company_id": company.id,
        "requesting_employee_id": ana.id if job == job_dev else marcos.id,
        "recruiter_id": carolina.id,
        "interviewer_ids": [(6, 0, [pedro.id, carolina.id])],
        "date_request": dates["date_request"],
    }
    vals.update(extra)
    vac = Vacancy.create(vals)
    vac.write(dict(dates, state=state))
    return vac


vac_in_process = make_vacancy(
    job_dev,
    "in_process",
    {
        "date_request": today - timedelta(days=30),
        "date_approval": today - timedelta(days=25),
        "date_open": today - timedelta(days=20),
    },
    priority="1",
    vacancy_type="replacement",
    resources_qty=1,
    contract_type="fixed",
    desired_hire_date=today + timedelta(days=15),
    reason="Renuncia del titular del puesto. Se requiere cubrir la posición para "
    "no detener el roadmap de la localización.",
    coverage_type="external",
)

vac_to_approve = make_vacancy(
    job_sales,
    "to_be_approved",
    {"date_request": today - timedelta(days=3)},
    priority="2",
    vacancy_type="headcount_expansion",
    resources_qty=2,
    contract_type="fixed",
    desired_hire_date=today + timedelta(days=45),
    reason="Apertura de la nueva zona comercial Este. Se necesitan dos ejecutivos.",
    coverage_type="mixed",
    selected_employee_ids=[(6, 0, [jose.id])],
)

vac_done = make_vacancy(
    job_dev,
    "done",
    {
        "date_request": today - timedelta(days=120),
        "date_approval": today - timedelta(days=113),
        "date_open": today - timedelta(days=110),
        "date_close": today - timedelta(days=75),
    },
    priority="0",
    vacancy_type="new_position",
    resources_qty=1,
    contract_type="intern",
    reason="Plaza nueva de pasantía cubierta internamente.",
    coverage_type="internal",
    selected_employee_ids=[(6, 0, [jose.id])],
)

vac_rejected = make_vacancy(
    job_sales,
    "rejected",
    {"date_request": today - timedelta(days=60)},
    priority="0",
    vacancy_type="new_position",
    resources_qty=1,
    coverage_type="external",
    reason="Solicitud fuera del presupuesto aprobado del año.",
)

# ── 6. Postulantes de la vacante en proceso ───────────────────────────────────
# job_id en hr.applicant es related store de la vacante: NO se pasa a mano.
Applicant = env["hr.applicant"]
stage_new = env.ref("hr_recruitment.stage_job1")
stage_first = env.ref("hr_recruitment.stage_job2")
stage_contract = env.ref("hr_recruitment.stage_job4")


def make_applicant(name, email, phone, stage, **extra):
    app = Applicant.search([("partner_name", "=", name)], limit=1)
    if app:
        return app
    vals = {
        "partner_name": name,
        "email_from": email,
        "partner_phone": phone,
        "company_id": company.id,
        "stage_id": stage.id,
        "type_id": degree_licenced.id,
        "l10n_do_vacancy_application_id": vac_in_process.id,
    }
    vals.update(extra)
    return Applicant.create(vals)


app_1 = make_applicant(
    "Rafael Antonio Núñez",
    "rafael.nunez@example.com",
    "809-555-0111",
    stage_contract,
    salary_expected=95000,
    availability=today + timedelta(days=15),
    priority="3",
    l10n_do_comments=(
        "Entrevista técnica: 9/10. Domina Odoo 17/19, ORM y OWL.\n"
        "Entrevista con RRHH: buena comunicación, disponibilidad inmediata.\n"
        "Referencias verificadas con dos empleadores anteriores.\n"
        "Recomendación: enviar propuesta económica."
    ),
)
make_applicant(
    "Yohanna Cabrera",
    "yohanna.cabrera@example.com",
    "809-555-0122",
    stage_first,
    salary_expected=88000,
    priority="2",
    l10n_do_comments="Entrevista técnica pendiente. Perfil fuerte en frontend.",
)
make_applicant(
    "Elvin Rodríguez",
    "elvin.rodriguez@example.com",
    "809-555-0133",
    stage_new,
    salary_expected=80000,
    priority="1",
)

# ── 7. Acciones demo para las capturas ────────────────────────────────────────
def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": MODULE, "name": xmlid,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })
    return act


demo_action("demo_vacancy_list", {
    "name": "Solicitudes de Vacante",
    "res_model": "l10n.do.hr.vacancy.application",
    "view_mode": "list,form",
})
demo_action("demo_vacancy_list_by_state", {
    "name": "Solicitudes de Vacante por estado",
    "res_model": "l10n.do.hr.vacancy.application",
    "view_mode": "list,form",
    "context": "{'group_by': ['state']}",
})
demo_action("demo_vacancy_to_approve", {
    "name": "Solicitud por aprobar",
    "res_model": "l10n.do.hr.vacancy.application",
    "view_mode": "form",
    "res_id": vac_to_approve.id,
})
demo_action("demo_vacancy_in_process", {
    "name": "Solicitud en proceso",
    "res_model": "l10n.do.hr.vacancy.application",
    "view_mode": "form",
    "res_id": vac_in_process.id,
})
demo_action("demo_vacancy_done", {
    "name": "Solicitud cerrada",
    "res_model": "l10n.do.hr.vacancy.application",
    "view_mode": "form",
    "res_id": vac_done.id,
})
demo_action("demo_vacancy_applicants", {
    "name": "Postulantes de la vacante",
    "res_model": "hr.applicant",
    "view_mode": "list,form",
    "domain": "[('l10n_do_vacancy_application_id', '=', %d)]" % vac_in_process.id,
    "context": "{'default_l10n_do_vacancy_application_id': %d}" % vac_in_process.id,
})
demo_action("demo_applicant_form", {
    "name": "Postulante - Rafael Antonio Núñez",
    "res_model": "hr.applicant",
    "view_mode": "form",
    "res_id": app_1.id,
})
demo_action("demo_job_form", {
    "name": "Puesto - Desarrollador Odoo Senior",
    "res_model": "hr.job",
    "view_mode": "form",
    "res_id": job_dev.id,
})
demo_action("demo_employee_form", {
    "name": "Empleado - José Sánchez",
    "res_model": "hr.employee",
    "view_mode": "form",
    "res_id": jose.id,
})

env.cr.commit()
print("SEED OK: %s vacantes, %s postulantes" % (
    Vacancy.search_count([]), Applicant.search_count([])))
