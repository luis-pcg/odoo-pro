# Datos de ejemplo para el manual de l10n_do_hr_news (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date

MODULE = "l10n_do_hr_news"

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
env = env(context=dict(env.context, lang="es_DO"))

company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL", "country_id": env.ref("base.do").id})

Department = env["hr.department"]
Job = env["hr.job"]
Employee = env["hr.employee"]
ventas = Department.create({"name": "Ventas"})
operaciones = Department.create({"name": "Operaciones"})
vendedor = Job.create({"name": "Ejecutivo de Ventas"})
supervisor = Job.create({"name": "Supervisor de Ventas"})

admin_employee = admin.employee_id or Employee.create({"name": "Administrador", "user_id": admin.id})
env = env(user=admin.id)
gerente = Employee.create({"name": "Carmen Rosario", "department_id": ventas.id, "job_id": supervisor.id})
ana = Employee.create(
    {
        "name": "Ana Mercedes Pérez",
        "department_id": ventas.id,
        "job_id": vendedor.id,
        "parent_id": gerente.id,
        "wage": 45000.0,
    }
)
luis = Employee.create(
    {
        "name": "Luis Alberto Santana",
        "department_id": operaciones.id,
        "parent_id": gerente.id,
        "wage": 38000.0,
    }
)

News = env["l10n.do.hr.news"]
change_type = env.ref("l10n_do_hr_news.news_type_change")
reprimand = env.ref("l10n_do_hr_news.news_type_employee_reprimand")
reprimand.validation_type = "both"

ana.write({"job_id": supervisor.id, "wage": 52000.0})
auto_news = News.search([("employee_id", "=", ana.id), ("news_type_id", "=", change_type.id)])

draft = News.create(
    {
        "news_type_id": reprimand.id,
        "employee_id": luis.id,
        "request_date": date(2026, 9, 15),
        "note": "Llegadas tarde reiteradas durante la primera quincena de septiembre.",
    }
)

second = News.create(
    {
        "news_type_id": reprimand.id,
        "employee_id": ana.id,
        "request_date": date(2026, 9, 10),
        "note": "Incumplimiento del protocolo de atención al cliente.",
    }
)
second.action_confirm()
second.action_approve()

manual_change = News.create(
    {
        "news_type_id": change_type.id,
        "employee_id": luis.id,
        "request_date": date(2026, 9, 20),
        "note": "Traslado aprobado por la gerencia de ventas.",
        "news_type_change_ids": [
            (
                0,
                0,
                {
                    "change_type": "department",
                    "current_department_id": operaciones.id,
                    "new_department_id": ventas.id,
                },
            ),
            (
                0,
                0,
                {
                    "change_type": "job",
                    "current_job_id": False,
                    "new_job_id": vendedor.id,
                },
            ),
        ],
    }
)
manual_change.action_confirm()

refused = News.create(
    {
        "news_type_id": env.ref("l10n_do_hr_news.news_type_overtime").id,
        "employee_id": luis.id,
        "request_date": date(2026, 9, 5),
        "note": "Horas reportadas sin autorización previa.",
    }
)
refused.action_confirm()
refused.action_approve()
refused.action_refuse()


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


for xmlid, record in (
    ("demo_news_draft", draft),
    ("demo_news_second_approval", second),
    ("demo_news_manual_change", manual_change),
    ("demo_news_auto_change", auto_news[:1]),
    ("demo_news_refused", refused),
):
    demo_action(
        xmlid, {"name": record.name, "res_model": "l10n.do.hr.news", "view_mode": "form", "res_id": record.id}
    )
demo_action(
    "demo_news_type_change",
    {
        "name": change_type.name,
        "res_model": "l10n.do.hr.news.type",
        "view_mode": "form",
        "res_id": change_type.id,
    },
)
demo_action(
    "demo_news_type_reprimand",
    {"name": reprimand.name, "res_model": "l10n.do.hr.news.type", "view_mode": "form", "res_id": reprimand.id},
)
demo_action(
    "demo_employee_ana",
    {"name": ana.name, "res_model": "hr.employee", "view_mode": "form", "res_id": ana.id},
)

print("seed l10n_do_hr_news OK: %d novedades" % News.search_count([]))
env.cr.commit()
