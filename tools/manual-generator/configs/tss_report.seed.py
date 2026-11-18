# Datos de ejemplo para el manual de tss_report (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date, datetime, timedelta

MODULE = "tss_report"

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
State = env["res.country.state"]
dn = State.search([("country_id", "=", do.id), ("code", "=", "DN")], limit=1) or State.create(
    {"country_id": do.id, "code": "DN", "name": "Distrito Nacional"}
)
company.write(
    {
        "name": "Empresa Dominicana SRL",
        "country_id": do.id,
        "state_id": dn.id,
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
        "attendance_work_entry_type_id": env.ref("hr_work_entry.generic_work_entry_type_attendance").id,
    }
)
company.partner_id.with_context(no_vat_validation=True).vat = "131793916"
try:
    with env.cr.savepoint():
        company.currency_id = dop.id
except Exception:
    pass
company2 = env["res.company"].search([("name", "=", "Sucursal Santiago SRL")], limit=1) or env["res.company"].create(
    {"name": "Sucursal Santiago SRL", "country_id": do.id}
)
admin.write({"company_ids": [(4, company.id), (4, company2.id)], "company_id": company.id})
env = env(user=admin.id, context=dict(env.context, lang="es_DO", allowed_company_ids=[company.id]))

establishment = env["l10n.do.hr.establishment"].create(
    {
        "name": "Empresa Dominicana SRL — Sede Central",
        "l10n_do_rnl_code": "RNL-001",
        "company_ids": [(6, 0, [company.id])],
        "street": company.street,
        "state_id": dn.id,
    }
)
shift = env["l10n.do.hr.work.shift"].create(
    {"code": "D1", "name": "Diurno 8:00-17:00", "time_start": 8.0, "time_stop": 17.0, "company_id": company.id}
)
occupations = env["l10n.do.hr.occupation"].search([], limit=4)
job = env["hr.job"].create({"name": "Contador", "l10n_do_occupation_id": occupations[0].id})
nationality_do = env["l10n.do.hr.nationality"].search([("name", "ilike", "DOMINICAN")], limit=1)
nationality_us = env["l10n.do.hr.nationality"].search([("name", "ilike", "ESTADOUNIDENSE")], limit=1)
education = env["l10n.do.hr.education.level"].search([], limit=1)

structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
structure_type.default_schedule_pay = "monthly"
structure = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")

EMPLOYEES = [
    ("Juan", "Pérez", "Rodríguez", {"identification_id": "001-1234567-8"}, "male", 30000, "cedula", nationality_do),
    ("María", "Gómez", "Santana", {"identification_id": "002-2345678-9"}, "female", 45000, "cedula", nationality_do),
    ("Pedro", "Martínez", "Cruz", {"l10n_do_social_security_number": "1234567"}, "male", 38000, "cedula", nationality_do),
    ("John", "Smith", "Doe", {"passport_id": "AB123456", "country_id": env.ref("base.us").id}, "male", 60000, "pasaporte", nationality_us),
]
employees = env["hr.employee"]
for index, (first, last1, last2, document, sex, wage, doc_type, nationality) in enumerate(EMPLOYEES):
    vals = {
        "name": f"{first} {last1} {last2}",
        "first_name": first,
        "first_last_name": last1,
        "second_last_name": last2,
        "company_id": company.id,
        "country_id": do.id,
        "l10n_do_has_papers": True,
        "sex": sex,
        "birthday": date(1985 + index * 3, 3 + index, 15),
        "job_id": job.id if index == 0 else False,
        "l10n_do_sirla_document_type": doc_type,
        "l10n_do_nationality_id": nationality.id,
        "l10n_do_occupation_id": occupations[index % len(occupations)].id,
        "l10n_do_education_level_id": education.id,
        "l10n_do_work_shift_id": shift.id,
        "l10n_do_establishment_id": establishment.id,
        "date_version": date(2025, 1, 1),
        "contract_date_start": date(2025, 1, 1),
        "wage": wage,
        "structure_type_id": structure_type.id,
        "tz": "America/Santo_Domingo",
    }
    vals.update(document)
    if "passport_id" in document:
        vals["l10n_do_has_papers"] = False
    employees |= env["hr.employee"].create(vals)
juan, maria = employees[0], employees[1]

Movement = env["l10n.do.hr.movement"]
for employee in employees:
    Movement.create(
        {
            "name": f"Alta {employee.name}",
            "employee_id": employee.id,
            "movement_type": "NI",
            "date": date(2025, 1, 1),
            "reason": "Ingreso por contratación",
        }
    )
Movement.create(
    {
        "name": "Cambio de puesto Juan Pérez",
        "employee_id": juan.id,
        "movement_type": "NC",
        "date": date(2026, 8, 1),
        "reason": "Promoción a Contador",
    }
)

rule35 = env.ref("l10n_do_hr_report_base.time_rule_rd_35")
rule100 = env.ref("l10n_do_hr_report_base.time_rule_rd_100")
(rule35 | rule100).write({"active": True})
env.ref("hr_work_entry.hr_time_rule_employee_schedule").active = False

week = date(2026, 9, 7)
Attendance = env["hr.attendance"]
local_offset = timedelta(hours=4)
for employee, long_days in ((juan, 5), (maria, 4)):
    for day in range(6):
        current = week + timedelta(days=day)
        hours = 10 if day < long_days else (4 if day == 5 else 9)
        start = datetime.combine(current, datetime.min.time()) + timedelta(hours=8) + local_offset
        Attendance.create({"employee_id": employee.id, "check_in": start, "check_out": start + timedelta(hours=hours)})
sunday = datetime.combine(week + timedelta(days=6), datetime.min.time()) + timedelta(hours=9) + local_offset
Attendance.create({"employee_id": juan.id, "check_in": sunday, "check_out": sunday + timedelta(hours=4)})
overtime = Attendance.search([("employee_id", "in", (juan | maria).ids), ("time_rule_id", "!=", False)], order="check_in")
causes = [env.ref(f"l10n_do_hr_report_base.overtime_cause_{code}") for code in "dab"]
for index, attendance in enumerate(overtime):
    attendance.l10n_do_overtime_cause_id = causes[index % len(causes)]

payrun = env["hr.payslip.run"].create({"name": "Nómina Septiembre 2026", "date_start": date(2026, 9, 1), "date_end": date(2026, 9, 30)})
payslips = env["hr.payslip"].create(
    [
        {
            "employee_id": employee.id,
            "version_id": employee.version_id.id,
            "struct_id": structure.id,
            "date_from": date(2026, 9, 1),
            "date_to": date(2026, 9, 30),
            "payslip_run_id": payrun.id,
        }
        for employee in employees
    ]
)
payslips.compute_sheet()
payrun.action_validate()


def demo_action(xmlid, vals):
    existing = env.ref(f"{MODULE}.{xmlid}", raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


def form_action(xmlid, record):
    demo_action(xmlid, {"name": record.display_name, "res_model": record._name, "view_mode": "form", "res_id": record.id})


form_action("demo_company", company)
form_action("demo_establishment", establishment)
form_action("demo_employee", juan)
form_action("demo_job", job)
form_action("demo_payslip", payslips.filtered(lambda slip: slip.employee_id == juan))
form_action("demo_time_rule_35", rule35)
form_action("demo_time_rule_100", rule100)
demo_action(
    "demo_time_rules_do",
    {
        "name": "Reglas de tiempo RD",
        "res_model": "hr.time.rule",
        "view_mode": "list,form",
        "domain": [("country_id", "=", do.id)],
        "context": {"active_test": False},
    },
)

assert len(overtime) >= 3, overtime
assert overtime.filtered(lambda a: a.l10n_do_overtime_pct == 100) and overtime.filtered(lambda a: a.l10n_do_overtime_pct == 35)
assert set(payslips.mapped("state")) == {"validated"}, payslips.mapped("state")
print(
    "SEED OK l10n_do_hr_report_base: %d employees, %d overtime attendances, payrun %s"
    % (len(employees), len(overtime), payrun.name)
)
env.cr.commit()

wizard = env["tss.report.wizard"].create({"payslip_run_ids": [(4, payrun.id)]})
wizard.generate_autodeterm()
demo_action(
    "demo_tss_wizard_done",
    {"name": "Autodeterminación", "res_model": wizard._name, "view_mode": "form", "res_id": wizard.id, "target": "new"},
)
tss_lines = wizard.tss_binary.content.decode().split("\r\n")
assert len(tss_lines) == len(employees) + 2, tss_lines
print("SEED OK tss_report: %s, %d lines" % (wizard.tss_filename, len(tss_lines)))
env.cr.commit()
