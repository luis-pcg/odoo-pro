# Seed para el manual de VALIDACIÓN del IR-3 (casillas 3 "Sueldos pagados por
# el agente" y 4 "Otras remuneraciones").
#
# Construye un escenario de nómina controlado donde los montos de cada casilla
# se pueden verificar a mano, regla por regla:
#
#   Empleado                  Sueldo    Inputs de la boleta
#   ─────────────────────────────────────────────────────────────────────
#   Juan Pérez Rodríguez      28,000    (ninguno — solo salario)
#   María Gómez Santana       33,000    VAC (vacaciones)
#   Pedro Martínez Cruz       45,000    HNI 12 horas nocturnas
#   Ana Rodríguez Féliz       60,000    COMV 15,000 + HNI 10 h + INC 8,000
#   José Ramírez Guzmán       85,000    COMV 20,000
#   Laura Jiménez Reyes      150,000    (ninguno — solo salario)
#
# Con esto:
#   - Casilla 3 = APAGAR + COM + HNI  (se ve que NO es solo el salario base)
#   - Casilla 4 = categoría "asignaciones gravables" (INC, HNI, ...) + VAC
#     → con el código con bug, HNI aparece en las DOS casillas (doble conteo)
#   - Casilla 8 = ISR retenido (no se toca; es la que sí cuadra)
#
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con env.cr.commit().
from datetime import date, timedelta

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)
period_start = period_end.replace(day=1)

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True

# ── 0. UI en español (es_DO) para que las capturas usen la terminología local ─
es = env["res.lang"]._activate_lang("es_DO")
try:
    wiz = env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True})
    wiz.lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"

# ── 1. Compañía RD ────────────────────────────────────────────────────────────
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "city": "Santo Domingo",
    "street": "Av. Winston Churchill 1099",
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
    company.write({"country_id": do.id})
try:
    company.partner_id.with_context(no_vat_validation=True).vat = "131-79391-6"
except Exception:
    pass

# ── 2. Calendario RD 44h + estructura + diario de salario ────────────────────
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

Partner = env["res.partner"]
afp = Partner.search([("name", "=", "AFP Popular")], limit=1) or Partner.create(
    {"name": "AFP Popular", "is_company": True, "country_id": do.id})
ars = Partner.search([("name", "=", "ARS Universal")], limit=1) or Partner.create(
    {"name": "ARS Universal", "is_company": True, "country_id": do.id})
Dept = env["hr.department"]
dept = Dept.search([("name", "=", "Operaciones")], limit=1) or Dept.create({"name": "Operaciones"})
payroll_key = env.ref("l10n_do_hr_report_base.l10n_do_payroll_key_001")

# ── 3. Empleados ──────────────────────────────────────────────────────────────
contract_start = date(today.year - 1, 1, 1)
EMPLOYEES = [
    # first, last1, last2, cedula, NSS, sexo, nacimiento, sueldo
    ("Juan",  "Pérez",     "Rodríguez", "00112345678", "10001", "male",   "1988-03-15",  28000),
    ("María", "Gómez",     "Santana",   "00223456789", "10002", "female", "1992-07-22",  33000),
    ("Pedro", "Martínez",  "Cruz",      "00334567890", "10003", "male",   "1985-11-08",  45000),
    ("Ana",   "Rodríguez", "Féliz",     "00445678901", "10004", "female", "1990-01-30",  60000),
    ("José",  "Ramírez",   "Guzmán",    "00778901234", "10007", "male",   "1987-12-03",  85000),
    ("Laura", "Jiménez",   "Reyes",     "00101234567", "10010", "female", "1986-02-09", 150000),
]
Employee = env["hr.employee"]
employees = env["hr.employee"]
by_first = {}
for fn, l1, l2, cedula, nss, sex, birthday, wage in EMPLOYEES:
    emp = Employee.search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = Employee.create({
            "name": f"{fn} {l1} {l2}",
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
            "department_id": dept.id,
            "resource_calendar_id": calendar_rd.id,
            "l10n_do_sirla_document_type": "cedula",
            "date_version": contract_start,
            "contract_date_start": contract_start,
            "wage": wage,
            "structure_type_id": structure_type.id,
        })
        emp.version_id.write({
            "l10n_do_schedule_retentions": "end_of_month",
            "l10n_do_payroll_key_id": payroll_key.id,
        })
    employees |= emp
    by_first[fn] = emp

# ── 3b. Parámetro REC_NOCT (recargo nocturno 15%, Art. 204 CT) ───────────────
# La regla HNI lo consulta con payslip._rule_parameter('REC_NOCT') pero el
# módulo NO lo trae en data: en producción se crea a mano. Sin él, la boleta
# con input HNI no se puede calcular.
param = env["hr.rule.parameter"].search([("code", "=", "REC_NOCT")], limit=1)
if not param:
    param = env["hr.rule.parameter"].create({"name": "Recargo nocturno (15%)", "code": "REC_NOCT"})
if not param.parameter_version_ids:
    env["hr.rule.parameter.value"].create({
        "rule_parameter_id": param.id,
        "date_from": "2020-01-01",
        "parameter_value": "0.15",
    })

# ── 4. Lote de nómina con INPUTS controlados ─────────────────────────────────
run = env["hr.payslip.run"].search([("date_start", "=", period_start)], limit=1)
if not run:
    run = env["hr.payslip.run"].create({
        "name": "Nómina %s" % period_start.strftime("%m/%Y"),
        "date_start": period_start, "date_end": period_end,
    })

INPUTS = {
    # empleado: [(código input, monto/cantidad)]
    "Ana":   [("COMV", 15000.0), ("HNI", 10.0), ("INC", 8000.0)],
    "Pedro": [("HNI", 12.0)],
    "José":  [("COMV", 20000.0)],
    "María": [("VAC", 1.0)],
}
itypes = {}
for codes in INPUTS.values():
    for code, _amt in codes:
        if code not in itypes:
            it = env["hr.payslip.input.type"].search([("code", "=", code)], limit=1)
            assert it, "no existe hr.payslip.input.type con código %s" % code
            itypes[code] = it

slips = env["hr.payslip"]
for fn, emp in by_first.items():
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
    for code, amount in INPUTS.get(fn, []):
        if not slip.input_line_ids.filtered(lambda l, c=code: l.code == c):
            slip.write({"input_line_ids": [(0, 0, {
                "input_type_id": itypes[code].id, "amount": amount})]})
    slips |= slip

slips.compute_sheet()
# Se validan sin generar asientos (la base demo no tiene plan contable);
# el IR-3 solo requiere el estado 'validated'.
slips.filtered(lambda s: s.state not in ("validated", "paid")).write({"state": "validated"})

# ── 5. Reporte DGII del período → calcula el IR-3 desde las boletas ──────────
period_name = period_end.strftime("%m/%Y")
Report = env["dgii.reports"]
report = Report.search([("name", "=", period_name), ("company_id", "=", company.id)], limit=1)
if not report:
    report = Report.create({"name": period_name, "company_id": company.id})
report.action_compute_ir3()
try:
    report.action_generate_tss()
except Exception as exc:
    print("WARN: no se pudo generar el TSS: %s" % exc)

env.cr.commit()
print("SEED OK: company=%s employees=%d slips=%d ir3_employees=%d period=%s" % (
    company.name, len(employees), len(slips),
    report.l10n_do_ir3_total_employees, period_name))
