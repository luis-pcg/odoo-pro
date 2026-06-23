# Seed data for the l10n_do_hr_report_base / dgii_ir3_report user manual
# (DGT-2/3/4 + IR-3 + TSS). Executed inside `odoo shell` (the `env` global is
# provided). The UI is switched to Spanish (es_DO) so the screenshots match the
# DGII/SIRLA terminology.
#
# Builds a full, self-contained demo:
#   0. Spanish language (es_DO) + admin user in Spanish.
#   1. Company RD (country DO, currency DOP, province, street, risk type, RNC).
#   2. RNL establishment (multi-company: company_ids) linked directly on each employee.
#   3. 44h RD work calendar + a SIRLA work shift.
#   4. 6 employees with full name, SIRLA data, establishment and a live contract.
#   5. DGT-4 personnel movements (new hires) + DGT-2 overtime lines.
#   6. A computed + validated payslip batch for last month.
#   7. The DGII period report, which computes the IR-3 from the payslips + TSS file.
#
# Idempotent enough for a fresh `test_v19_*` DB. Ends with `env.cr.commit()`.
from datetime import date, datetime, timedelta

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)
period_start = period_end.replace(day=1)

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True

# ── 0. Spanish UI (so the manual screenshots are in Spanish) ─────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    wiz = env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True})
    wiz.lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"

# ── RD provinces (the localization may not ship res.country.state for DO) ─────
State = env["res.country.state"]
provinces = {}
for code, name in [("DN", "Distrito Nacional"), ("ST", "Santiago"), ("SP", "San Pedro de Macorís")]:
    st = State.search([("country_id", "=", do.id), ("code", "=", code)], limit=1)
    if not st:
        st = State.create({"country_id": do.id, "code": code, "name": name})
    provinces[code] = st

# ── 1. Company ────────────────────────────────────────────────────────────────
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "state_id": provinces["DN"].id,
    "street": "Av. Winston Churchill 1099",
    "city": "Santo Domingo",
    "phone": "809-555-0100",
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
try:
    company.partner_id.with_context(no_vat_validation=True).vat = "131-79391-6"
except Exception:
    pass

# ── 2. RNL establishment (multi-company) ─────────────────────────────────────
# The establishment is NOT linked to the company anymore: it is multi-company
# (company_ids) and is assigned directly on each employee.
Establishment = env["l10n.do.hr.establishment"]
establishment = Establishment.search([("l10n_do_rnl_code", "=", "RNL-001")], limit=1)
if not establishment:
    establishment = Establishment.create({
        "name": "Empresa Dominicana SRL — Sede Central",
        "l10n_do_rnl_code": "RNL-001",
        "company_ids": [(6, 0, [company.id])],   # defaults to the current company
        "street": company.street,
        "state_id": company.state_id.id,
    })

# A second company so the multi-company UI is active and the establishment's
# "Empresas" (company_ids) field is visible in the manual screenshots.
company2 = env["res.company"].search([("name", "=", "Sucursal Santiago SRL")], limit=1)
if not company2:
    company2 = env["res.company"].create({"name": "Sucursal Santiago SRL", "country_id": do.id})
admin_user = env.ref("base.user_admin")
admin_user.write({"company_ids": [(4, company.id), (4, company2.id)], "company_id": company.id})

# ── 3. Work calendar (RD 44h) + SIRLA work shift ─────────────────────────────
attendances = []
for dow in range(5):
    attendances.append((0, 0, {"name": "Mañana", "dayofweek": str(dow),
                               "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
    attendances.append((0, 0, {"name": "Tarde", "dayofweek": str(dow),
                               "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}))
attendances.append((0, 0, {"name": "Sábado", "dayofweek": "5",
                           "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
calendar_rd = env["resource.calendar"].search([("name", "=", "Jornada RD 44 horas")], limit=1)
if not calendar_rd:
    calendar_rd = env["resource.calendar"].create({
        "name": "Jornada RD 44 horas", "company_id": company.id,
        "hours_per_day": 8, "attendance_ids": attendances,
    })
company.resource_calendar_id = calendar_rd

shift = env["l10n.do.hr.work.shift"].search([("code", "=", "D1")], limit=1)
if not shift:
    shift = env["l10n.do.hr.work.shift"].create({
        "code": "D1", "name": "Diurno 8-17", "time_start": 8.0, "time_stop": 17.0,
        "company_id": company.id,
    })

# Structure + salary journal (so payslips can be created/computed)
structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
structure_type.write({"default_resource_calendar_id": calendar_rd.id, "default_schedule_pay": "monthly"})
struct_base = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
salary_journal = env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
if not salary_journal:
    salary_journal = env["account.journal"].create(
        {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id})
for struct in env["hr.payroll.structure"].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal

# ── SIRLA catalogs (loaded from CSV) ─────────────────────────────────────────
nat_do = env.ref("l10n_do_hr_report_base.nationality_1")          # DOMINICANA
education = env["l10n.do.hr.education.level"].search([], limit=1)
occupations = env["l10n.do.hr.occupation"].search([], limit=6)

# ── 4. Employees with full name + SIRLA data + establishment + contract ──────
Dept = env["hr.department"]
departments = {
    "admin": Dept.search([("name", "=", "Administración")], limit=1) or Dept.create({"name": "Administración"}),
    "ventas": Dept.search([("name", "=", "Ventas")], limit=1) or Dept.create({"name": "Ventas"}),
    "ops": Dept.search([("name", "=", "Operaciones")], limit=1) or Dept.create({"name": "Operaciones"}),
}
Partner = env["res.partner"]
afp = Partner.search([("name", "=", "AFP Popular")], limit=1) or Partner.create(
    {"name": "AFP Popular", "is_company": True, "country_id": do.id})
ars = Partner.search([("name", "=", "ARS Universal")], limit=1) or Partner.create(
    {"name": "ARS Universal", "is_company": True, "country_id": do.id})

contract_start = date(today.year - 1, 1, 1)
EMPLOYEES = [
    # first, last1, last2, cedula, NSS, sex, birthday, dept, wage
    ("Juan",   "Pérez",     "Rodríguez", "00112345678", "10001", "male",   "1988-03-15", "admin",  28000),
    ("María",  "Gómez",     "Santana",   "00223456789", "10002", "female", "1992-07-22", "admin",  33000),
    ("Pedro",  "Martínez",  "Cruz",      "00334567890", "10003", "male",   "1985-11-08", "ops",    45000),
    ("Ana",    "Rodríguez", "Féliz",     "00445678901", "10004", "female", "1990-01-30", "ventas", 60000),
    ("José",   "Ramírez",   "Guzmán",    "00778901234", "10007", "male",   "1987-12-03", "ops",    85000),
    ("Laura",  "Jiménez",   "Reyes",     "00101234567", "10010", "female", "1986-02-09", "admin", 150000),
]

Employee = env["hr.employee"]
employees = env["hr.employee"]
for i, (fn, l1, l2, cedula, nss, sex, birthday, dept, wage) in enumerate(EMPLOYEES):
    name = f"{fn} {l1} {l2}"
    emp = Employee.search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = Employee.create({
            "name": name,
            "first_name": fn, "first_last_name": l1, "second_last_name": l2,
            "company_id": company.id,
            "country_id": do.id,
            "identification_id": cedula,
            "l10n_do_social_security_number": nss,
            "l10n_do_has_papers": True,
            "l10n_do_afp_partner_id": afp.id,
            "l10n_do_ars_partner_id": ars.id,
            "sex": sex,
            "birthday": birthday,
            "department_id": departments[dept].id,
            "resource_calendar_id": calendar_rd.id,
            # SIRLA / DGT data
            "l10n_do_sirla_document_type": "cedula",
            "l10n_do_nationality_id": nat_do.id,
            "l10n_do_occupation_id": occupations[i % len(occupations)].id if occupations else False,
            "l10n_do_education_level_id": education.id if education else False,
            "l10n_do_work_shift_id": shift.id,
            "l10n_do_establishment_id": establishment.id,   # assigned directly
            # contract (hr.version)
            "date_version": contract_start,
            "contract_date_start": contract_start,
            "wage": wage,
            "structure_type_id": structure_type.id,
        })
        emp.version_id.write({"l10n_do_schedule_retentions": "end_of_month"})
    employees |= emp

# ── 5. DGT-4 personnel movements (new hires) ─────────────────────────────────
Movement = env["l10n.do.hr.movement"]
for emp in employees:
    if not Movement.search([("employee_id", "=", emp.id), ("movement_type", "=", "NI")], limit=1):
        Movement.create({
            "name": f"Alta {emp.name}",
            "employee_id": emp.id,
            "movement_type": "NI",
            "date": contract_start,
            "reason": "Ingreso por contratación",
            "company_id": company.id,
        })

# ── 5b. Overtime hours (DGT-2) ───────────────────────────────────────────────
# DGT-2 shows extra hours per employee with the Art. 153 cause + DR surcharge %
# (amount_rate 1.35 -> 35 %, 2.0 -> 100 %).
causes = [env.ref("l10n_do_hr_report_base.overtime_cause_%s" % c) for c in "abcde"]
OT = env["hr.attendance.overtime.line"]
ot_plan = [(2, 2.0, 1.35, 0), (9, 3.0, 2.0, 3), (16, 1.5, 1.35, 1), (23, 2.5, 2.0, 4)]
for emp in employees:
    for off, hrs, rate, ci in ot_plan:
        day = period_start + timedelta(days=off)
        if day > period_end:
            continue
        start = datetime(day.year, day.month, day.day, 17, 0, 0)
        stop = start + timedelta(hours=hrs)
        if not OT.search([("employee_id", "=", emp.id), ("time_start", "=", start)], limit=1):
            OT.create({
                "employee_id": emp.id,
                "date": day,
                "time_start": start,
                "time_stop": stop,
                "duration": hrs,
                "amount_rate": rate,
                "l10n_do_overtime_cause_id": causes[ci].id,
            })

# ── 6. Payslip batch (computed + validated) ──────────────────────────────────
run = env["hr.payslip.run"].search([("date_start", "=", period_start)], limit=1)
if not run:
    run = env["hr.payslip.run"].create({
        "name": "Nómina %s" % period_start.strftime("%m/%Y"),
        "date_start": period_start, "date_end": period_end,
    })
slips = env["hr.payslip"]
for emp in employees:
    slip = env["hr.payslip"].search(
        [("employee_id", "=", emp.id), ("payslip_run_id", "=", run.id)], limit=1)
    if not slip:
        slip = env["hr.payslip"].create({
            "name": "Nómina %s" % emp.name,
            "employee_id": emp.id,
            "struct_id": struct_base.id,
            "date_from": period_start,
            "date_to": period_end,
            "payslip_run_id": run.id,
        })
    slips |= slip
slips.compute_sheet()
# Mark as validated WITHOUT generating accounting entries (no chart of accounts
# is configured in this demo DB); the IR-3 only needs the 'validated' state.
slips.filtered(lambda s: s.state not in ("validated", "paid")).write({"state": "validated"})

# ── 7. DGII period report -> computes IR-3 from the validated payslips ────────
period_name = period_end.strftime("%m/%Y")
Report = env["dgii.reports"]
report = Report.search([("name", "=", period_name), ("company_id", "=", company.id)], limit=1)
if not report:
    report = Report.create({"name": period_name, "company_id": company.id})
report.action_compute_ir3()
try:
    report.action_generate_tss()
except Exception as exc:
    print("WARN: could not pre-generate the TSS file: %s" % exc)

env.cr.commit()
print("SEED OK: company=%s establishment=%s employees=%d slips=%d ir3_employees=%d period=%s" % (
    company.name, establishment.l10n_do_rnl_code, len(employees), len(slips),
    report.l10n_do_ir3_total_employees, period_name))
