# Seed for the manual of l10n_do_hr_payroll (ISR retention scale).
# Builds, from a CLEAN DB, the Dominican payroll flow with four employees whose
# salaries fall one in each DGII retention scale (exempt / 15% / 20% / 25%),
# computes their payslips and validates that the ISR salary rule follows the
# configurable l10n.do.hr.retention.scale records (including editing the scale
# and recomputing). Executed inside `odoo shell` (`env` is provided).
from datetime import date, timedelta

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)   # last day of previous month
period_start = period_end.replace(day=1)
TZ = "America/Santo_Domingo"

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True

# ── 0. Español ───────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"

# ── 1. Compañía RD ────────────────────────────────────────────────────────────
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
    company.write({"country_id": do.id})

# ── 2. Calendario RD 44h + estructura ─────────────────────────────────────────
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
        "name": "Jornada RD 44 horas", "company_id": company.id, "tz": TZ,
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

# ── 3. Empleados: un salario por escala DGII ─────────────────────────────────
contract_start = date(today.year - 1, 1, 1)
EMPLOYEES = [
    ("Pedro Sánchez", "00110000001", "90001", 30000.0),    # exento
    ("María Gómez", "00110000002", "90002", 45000.0),      # escala 15%
    ("Luisa Herrera", "00110000003", "90003", 60000.0),    # escala 20%
    ("José Rodríguez", "00110000004", "90004", 100000.0),  # escala 25%
]
employees = env["hr.employee"]
for name, cedula, nss, wage in EMPLOYEES:
    emp = env["hr.employee"].search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = env["hr.employee"].create({
            "name": name, "company_id": company.id, "country_id": do.id,
            "identification_id": cedula, "l10n_do_social_security_number": nss,
            "l10n_do_has_papers": True, "tz": TZ,
            "resource_calendar_id": calendar_rd.id,
            "date_version": contract_start, "contract_date_start": contract_start,
            "wage": wage, "structure_type_id": structure_type.id,
        })
    emp.version_id.write({"l10n_do_schedule_retentions": "distributed",
                          "resource_calendar_id": calendar_rd.id})
    employees |= emp

# ── 4. Recibos del período + cálculo ──────────────────────────────────────────
slips = env["hr.payslip"]
for emp in employees:
    slip = env["hr.payslip"].search(
        [("employee_id", "=", emp.id), ("date_from", "=", period_start)], limit=1)
    if not slip:
        slip = env["hr.payslip"].create({
            "name": "Nómina %s" % emp.name, "employee_id": emp.id,
            "struct_id": struct_base.id,
            "date_from": period_start, "date_to": period_end,
        })
    slip.compute_sheet()
    slips |= slip

# ── 5. Validación: la regla ISR sigue la escala configurada ──────────────────
Scale = env["l10n.do.hr.retention.scale"]
errors = []


def isr_of(slip):
    return sum(slip.line_ids.filtered(lambda l: l.code == "ISR").mapped("total"))


def saldgii_of(slip):
    return sum(slip.line_ids.filtered(lambda l: l.code == "SALDGII").mapped("total"))


report = []
for slip in slips:
    annual = saldgii_of(slip) * 12
    expected = -(Scale._compute_annual_retention(annual) / 12)
    got = isr_of(slip)
    ok = abs(expected - got) < 0.01
    if not ok:
        errors.append("%s: esperado %.2f, regla dio %.2f" % (slip.employee_id.name, expected, got))
    report.append("%s: anual=%.2f ISR=%.2f (esperado %.2f) %s" % (
        slip.employee_id.name, annual, got, expected, "OK" if ok else "FAIL"))

# 5b. Reactividad: editar la escala -> recalcular -> el ISR cambia; restaurar.
maria_slip = slips.filtered(lambda s: s.employee_id.identification_id == "00110000002")
isr_2026 = isr_of(maria_slip)
scale_exempt = Scale.search([("exempt", "=", True)], limit=1)
scale_15 = Scale.search([("exempt", "=", False)], order="base_amount", limit=1)
old_top, old_base = scale_exempt.top_amount, scale_15.base_amount
scale_exempt.top_amount = 500000.00
scale_15.base_amount = 500000.01
maria_slip.compute_sheet()
isr_edited = isr_of(maria_slip)
annual_maria = saldgii_of(maria_slip) * 12
expected_edited = -((annual_maria - 500000.01) * 0.15 / 12)
if abs(isr_edited - expected_edited) > 0.01:
    errors.append("Escala editada: esperado %.2f, regla dio %.2f" % (expected_edited, isr_edited))
scale_exempt.top_amount = old_top
scale_15.base_amount = old_base
maria_slip.compute_sheet()
if abs(isr_of(maria_slip) - isr_2026) > 0.01:
    errors.append("Restauración de escala no volvió al ISR original")
report.append("Reactividad escala: 2026=%.2f editada(exento 500k)=%.2f restaurada=%.2f" % (
    isr_2026, isr_edited, isr_of(maria_slip)))

# ── 6. Acciones de demo para las capturas ─────────────────────────────────────
def demo_action(xmlid, vals):
    existing = env.ref("l10n_do_hr_payroll.%s" % xmlid, raise_if_not_found=False)
    if existing:
        return
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": "l10n_do_hr_payroll", "name": xmlid,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })


# 6a. Empleados con su salario mensual
emp_view = env["ir.ui.view"].create({
    "name": "demo.emp.list", "model": "hr.employee", "type": "list",
    "arch": """<list create="0" edit="0">
        <field name="name" string="Empleado"/>
        <field name="identification_id" string="Cédula"/>
        <field name="l10n_do_social_security_number" string="NSS"/>
        <field name="wage" string="Salario mensual"/>
        <field name="structure_type_id" string="Tipo de estructura"/></list>""",
})
demo_action("demo_employees_action", {
    "name": "Empleados de prueba", "res_model": "hr.employee",
    "view_mode": "list", "view_id": emp_view.id,
    "domain": "[('id', 'in', %s)]" % employees.ids,
})
# 6b. Recibo de José (escala 25%) en form
jose_slip = slips.filtered(lambda s: s.employee_id.identification_id == "00110000004")
demo_action("demo_payslip_action", {
    "name": "Recibo de nómina", "res_model": "hr.payslip",
    "view_mode": "form", "res_id": jose_slip.id,
    "domain": "[('id', '=', %d)]" % jose_slip.id,
})
# 6c. Comparativa de líneas SALDGII / ISR / NET de los 4 recibos
line_view = env["ir.ui.view"].create({
    "name": "demo.isr.line.list", "model": "hr.payslip.line", "type": "list",
    "arch": """<list create="0" edit="0" default_order="employee_id,sequence">
        <field name="employee_id" string="Empleado"/>
        <field name="code" string="Código"/>
        <field name="name" string="Concepto"/>
        <field name="total" string="Monto"/></list>""",
})
demo_action("demo_isr_lines_action", {
    "name": "Líneas ISR por empleado", "res_model": "hr.payslip.line",
    "view_mode": "list", "view_id": line_view.id,
    "domain": "[('slip_id', 'in', %s), ('code', 'in', ['SALDGII', 'ISR', 'NET'])]" % slips.ids,
})

env.cr.commit()
if errors:
    print("SEED FAIL:")
    for e in errors:
        print("  -", e)
else:
    print("SEED OK: %d recibos calculados, periodo %s" % (len(slips), period_start.strftime("%m/%Y")))
    for r in report:
        print("  ", r)
