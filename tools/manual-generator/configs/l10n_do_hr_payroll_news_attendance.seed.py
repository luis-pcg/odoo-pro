# Seed for the manual of l10n_do_hr_payroll_news_attendance.
# Builds, from a CLEAN DB, the full Dominican payroll + native attendance
# overtime scenario and shows how this module carries the overtime into the
# payslip as the overtime INPUT (HEL) that the RD structure pays.
# Executed inside `odoo shell` (the `env` global is provided). UI in Spanish.
from datetime import date, datetime, timedelta

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)   # last day of previous month
period_start = period_end.replace(day=1)
TZ = "America/Santo_Domingo"   # UTC-4, sin horario de verano
UTC_OFFSET = 4                  # hora local + 4 = UTC

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

# ── 1. Compañía RD (moneda DOP, riesgo laboral, horas extra auto-aprobadas) ───
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
    "attendance_overtime_validation": "no_validation",
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
    company.write({"country_id": do.id})

# ── 2. Calendario laboral RD 44h (L-V 8-12/13-17 + Sáb 8-12), tz RD ───────────
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
calendar_rd.tz = TZ
company.resource_calendar_id = calendar_rd

# ── 3. Estructura salarial RD + diario ────────────────────────────────────────
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

# ── 4. Overtime Ruleset RD: regla cantidad/día 135% -> work entry OVERTIME ─────
overtime_wet = env.ref("hr_work_entry.work_entry_type_overtime")
ruleset = env["hr.attendance.overtime.ruleset"].search([("name", "=", "República Dominicana")], limit=1)
if not ruleset:
    ruleset = env["hr.attendance.overtime.ruleset"].create({
        "name": "República Dominicana", "company_id": company.id,
        "country_id": do.id, "rate_combination_mode": "max",
    })
if not ruleset.rule_ids:
    env["hr.attendance.overtime.rule"].create({
        "name": "Horas extra diarias (135%)",
        "ruleset_id": ruleset.id,
        "base_off": "quantity", "quantity_period": "day",
        "expected_hours_from_contract": True,
        "paid": True, "amount_rate": 1.35,
        "work_entry_type_id": overtime_wet.id, "sequence": 10,
    })

# ── 5. Empleado con contrato basado en ASISTENCIA + ruleset ───────────────────
contract_start = date(today.year - 1, 1, 1)
emp = env["hr.employee"].search([("identification_id", "=", "00112345678")], limit=1)
if not emp:
    emp = env["hr.employee"].create({
        "name": "Carlos Méndez", "company_id": company.id, "country_id": do.id,
        "identification_id": "00112345678", "l10n_do_social_security_number": "90001",
        "l10n_do_has_papers": True, "sex": "male", "birthday": "1988-03-15",
        "tz": TZ, "resource_calendar_id": calendar_rd.id,
        "date_version": contract_start, "contract_date_start": contract_start,
        "wage": 30000.0, "structure_type_id": structure_type.id,
    })
emp.version_id.write({
    "work_entry_source": "attendance",
    "ruleset_id": ruleset.id,
    "resource_calendar_id": calendar_rd.id,
    "l10n_do_schedule_retentions": "end_of_month",
})

# ── 6. Asistencias: 3 días laborables 08:00-18:00 (10h) -> 2h extra c/u = 6h ──
def at_utc(d, local_hour):
    return datetime(d.year, d.month, d.day, local_hour + UTC_OFFSET, 0, 0)

ot_days, day = [], period_start
while day <= period_end and len(ot_days) < 3:
    if day.weekday() < 5:
        ot_days.append(day)
    day += timedelta(days=1)
for d in ot_days:
    if not env["hr.attendance"].search([("employee_id", "=", emp.id), ("check_in", "=", at_utc(d, 8))], limit=1):
        env["hr.attendance"].create({   # create() dispara _update_overtime
            "employee_id": emp.id, "check_in": at_utc(d, 8), "check_out": at_utc(d, 18),
        })
env["hr.attendance.overtime.line"].search(
    [("employee_id", "=", emp.id), ("status", "!=", "approved")]).write({"status": "approved"})

# ── 7. Recibo del período + calcular (dispara el bridge: OVERTIME -> HEL) ─────
slip = env["hr.payslip"].search([("employee_id", "=", emp.id), ("date_from", "=", period_start)], limit=1)
if not slip:
    slip = env["hr.payslip"].create({
        "name": "Nómina %s" % emp.name, "employee_id": emp.id, "struct_id": struct_base.id,
        "date_from": period_start, "date_to": period_end,
    })
slip.compute_sheet()

# ── 8. Acciones de demo para el manual ────────────────────────────────────────
def demo_action(xmlid, vals):
    if env.ref("l10n_do_hr_payroll_news_attendance.%s" % xmlid, raise_if_not_found=False):
        return
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": "l10n_do_hr_payroll_news_attendance", "name": xmlid,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })

# 8a. Configuración de nómina del contrato (origen asistencia + ruleset)
demo_action("demo_version_action", {
    "name": "Configuración de nómina (contrato)", "res_model": "hr.version",
    "view_mode": "form", "res_id": emp.version_id.id,
    "domain": "[('id', '=', %d)]" % emp.version_id.id,
})
# 8b. Overtime Ruleset RD
demo_action("demo_ruleset_action", {
    "name": "Regla de horas extra", "res_model": "hr.attendance.overtime.ruleset",
    "view_mode": "form", "res_id": ruleset.id, "domain": "[('id', '=', %d)]" % ruleset.id,
})
# 8c. Horas extra detectadas (líneas de overtime)
ot_view = env["ir.ui.view"].create({
    "name": "demo.ot.line.list", "model": "hr.attendance.overtime.line", "type": "list",
    "arch": """<list create="0" edit="0" default_order="date asc">
        <field name="date" string="Día"/><field name="employee_id" string="Empleado"/>
        <field name="duration" string="Horas extra" sum="Total"/>
        <field name="amount_rate" string="Tasa"/><field name="status" string="Estado"/></list>""",
})
demo_action("demo_ot_lines_action", {
    "name": "Horas extra (Asistencia)", "res_model": "hr.attendance.overtime.line",
    "view_mode": "list", "view_id": ot_view.id, "domain": "[('duration', '>', 0)]",
})
# 8d. Recibo (form) -> pestaña Días Trabajados con la línea OVERTIME
demo_action("demo_payslip_action", {
    "name": "Recibo de nómina", "res_model": "hr.payslip",
    "view_mode": "form", "res_id": slip.id, "domain": "[('id', '=', %d)]" % slip.id,
})
# 8e. Input HEL del recibo
inp_view = env["ir.ui.view"].create({
    "name": "demo.hel.input.list", "model": "hr.payslip.input", "type": "list",
    "arch": """<list create="0" edit="0">
        <field name="payslip_id" string="Recibo"/><field name="code" string="Código"/>
        <field name="name" string="Concepto"/><field name="amount" string="Horas"/></list>""",
})
demo_action("demo_hel_input_action", {
    "name": "Entrada de horas extra (HEL)", "res_model": "hr.payslip.input",
    "view_mode": "list", "view_id": inp_view.id,
    "domain": "[('payslip_id', '=', %d)]" % slip.id,
})
# 8f. Líneas salariales del recibo (HEL paga + NETO)
line_view = env["ir.ui.view"].create({
    "name": "demo.payslip.line.list", "model": "hr.payslip.line", "type": "list",
    "arch": """<list create="0" edit="0" default_order="sequence">
        <field name="code" string="Código"/><field name="name" string="Concepto"/>
        <field name="quantity" string="Cantidad"/><field name="total" string="Monto"/></list>""",
})
demo_action("demo_hel_lines_action", {
    "name": "Líneas del recibo", "res_model": "hr.payslip.line",
    "view_mode": "list", "view_id": line_view.id,
    "domain": "[('slip_id', '=', %d), ('code', 'in', ['BASE','APAGAR','HEL','BRUTO','SFSE','SVDSE','NET'])]" % slip.id,
})

env.cr.commit()
hel_amt = sum(slip.line_ids.filtered(lambda r: r.code == "HEL").mapped("total"))
hel_in = sum(slip.input_line_ids.filtered(lambda i: i.code == "HEL").mapped("amount"))
print("SEED OK: empleado=%s OT_input(HEL)=%.1f h HEL_pago=%.2f periodo=%s" % (
    emp.name, hel_in, hel_amt, period_start.strftime("%m/%Y")))
