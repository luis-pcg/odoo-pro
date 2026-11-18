# Datos de ejemplo para el manual de l10n_do_hr_payroll_news (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date

MODULE = "l10n_do_hr_payroll_news"

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})

do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id})
try:
    with env.cr.savepoint():
        company.currency_id = dop.id
except Exception:
    pass

Employee = env["hr.employee"]
if not admin.employee_id:
    Employee.create({"name": "Administrador", "user_id": admin.id})
env = env(user=admin.id, context=dict(env.context, lang="es_DO"))

structure = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
stype = env.ref("l10n_do_hr_payroll.structure_type_employee")
stype.default_schedule_pay = "semi-monthly"

ana = env["hr.employee"].create(
    {
        "name": "Ana Mercedes Pérez",
        "company_id": company.id,
        "country_id": do.id,
        "l10n_do_has_papers": True,
        "wage": 60000.0,
        "date_version": date(2022, 1, 1),
        "contract_date_start": date(2022, 1, 1),
        "structure_type_id": stype.id,
    }
)

overtime = env.ref("l10n_do_hr_news.news_type_overtime")
News = env["l10n.do.hr.news"]

draft = News.create(
    {
        "news_type_id": overtime.id,
        "employee_id": ana.id,
        "request_date": date(2026, 9, 1),
        "payslip_input_amount": 4.0,
        "duration_type": "limited",
        "payslip_total_amount": 16.0,
        "l10n_do_apply_on": "all",
        "note": "Cierre de inventario: 4 horas extra por quincena hasta completar 16.",
    }
)

validated = News.create(
    {
        "news_type_id": overtime.id,
        "employee_id": ana.id,
        "request_date": date(2026, 9, 3),
        "payslip_input_amount": 6.0,
        "duration_type": "one",
        "note": "Horas extra por el conteo físico del almacén.",
    }
)
validated.action_confirm()
validated.action_approve()

payslip = env["hr.payslip"].create(
    {
        "name": "Nómina 1ra quincena Septiembre 2026 - Ana Mercedes Pérez",
        "employee_id": ana.id,
        "version_id": ana.version_id.id,
        "struct_id": structure.id,
        "company_id": company.id,
        "date_from": date(2026, 9, 1),
        "date_to": date(2026, 9, 15),
    }
)
payslip.compute_sheet()


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


form_action("demo_news_type_overtime", overtime)
form_action("demo_news_draft", draft)
form_action("demo_news_validated", validated)
form_action("demo_salary_attachment", validated.salary_attachment_id)
form_action("demo_payslip", payslip)

assert validated.salary_attachment_id, "the validated news has no salary adjustment"
assert payslip.input_line_ids.filtered(lambda i: i.code == "HEL"), "the payslip did not pick the overtime up"
print("seed l10n_do_hr_payroll_news OK: adjustment %s" % validated.salary_attachment_id.display_name)
env.cr.commit()
