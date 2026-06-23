# Seed for the "Horas extra nativas → nómina" manual.
# Shows how Odoo core (hr_attendance Overtime Rulesets + hr_work_entry_attendance
# + hr_payroll_attendance) covers what the discarded custom modules did
# (l10n_do_hr_news_attendance / l10n_do_hr_payroll_news_attendance).
# Executed inside `odoo shell` (the `env` global is provided). UI in Spanish.
from datetime import date, datetime, timedelta

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)
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

# ── 1. Compañía ───────────────────────────────────────────────────────────────
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "attendance_overtime_validation": "no_validation",   # horas extra auto-aprobadas
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()

# ── 2. Calendario laboral (40h, lunes-viernes 8-12 / 13-17, tz RD) ───────────
attendances = []
for dow in range(5):
    attendances.append((0, 0, {"name": "Mañana", "dayofweek": str(dow),
                               "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
    attendances.append((0, 0, {"name": "Tarde", "dayofweek": str(dow),
                               "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}))
calendar_rd = env["resource.calendar"].search([("name", "=", "Jornada RD 40 horas")], limit=1)
if not calendar_rd:
    calendar_rd = env["resource.calendar"].create({
        "name": "Jornada RD 40 horas", "company_id": company.id, "tz": TZ,
        "hours_per_day": 8, "attendance_ids": attendances,
    })
calendar_rd.tz = TZ
company.resource_calendar_id = calendar_rd

# Estructura salarial + diario (para poder calcular el recibo)
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

# ── 3. Regla de horas extra (Overtime Ruleset) ───────────────────────────────
overtime_wet = env.ref("hr_work_entry.work_entry_type_overtime")
ruleset = env["hr.attendance.overtime.ruleset"].search([("name", "=", "República Dominicana")], limit=1)
if not ruleset:
    ruleset = env["hr.attendance.overtime.ruleset"].create({
        "name": "República Dominicana",
        "company_id": company.id,
        "country_id": do.id,
        "rate_combination_mode": "max",
    })
if not ruleset.rule_ids:
    env["hr.attendance.overtime.rule"].create({
        "name": "Horas extra diarias (135%)",
        "ruleset_id": ruleset.id,
        "base_off": "quantity",
        "quantity_period": "day",
        "expected_hours_from_contract": True,
        "paid": True,
        "amount_rate": 1.35,
        "work_entry_type_id": overtime_wet.id,
        "sequence": 10,
    })

# Acción de demo (manual): abre solo la regla RD, sin la regla por defecto.
if not env.ref("hr_attendance.demo_ruleset_action", raise_if_not_found=False):
    rs_action = env["ir.actions.act_window"].create({
        "name": "Reglas de horas extra",
        "res_model": "hr.attendance.overtime.ruleset",
        "view_mode": "list,form",
        "domain": "[('id', '=', %d)]" % ruleset.id,
    })
    env["ir.model.data"].create({
        "module": "hr_attendance", "name": "demo_ruleset_action",
        "model": "ir.actions.act_window", "res_id": rs_action.id, "noupdate": True,
    })

# ── 4. Empleados con contrato basado en asistencia + ruleset ─────────────────
Employee = env["hr.employee"]
contract_start = date(today.year - 1, 1, 1)
EMPLOYEES = [
    ("Carlos Méndez", "00112345678", "male",   "1988-03-15", 35000),
    ("María Santana", "00223456789", "female", "1992-07-22", 42000),
]
employees = env["hr.employee"]
for name, cedula, sex, birthday, wage in EMPLOYEES:
    emp = Employee.search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = Employee.create({
            "name": name,
            "company_id": company.id,
            "country_id": do.id,
            "identification_id": cedula,
            "sex": sex,
            "birthday": birthday,
            "tz": TZ,
            "resource_calendar_id": calendar_rd.id,
            # contrato (hr.version)
            "date_version": contract_start,
            "contract_date_start": contract_start,
            "wage": wage,
            "structure_type_id": structure_type.id,
        })
    # Contrato basado en asistencia + regla de horas extra
    emp.version_id.write({
        "work_entry_source": "attendance",
        "ruleset_id": ruleset.id,
        "resource_calendar_id": calendar_rd.id,
    })
    employees |= emp

# ── 5. Asistencias del período (jornada normal + horas extra algunos días) ───
# Local 08:00 -> UTC 12:00 ; 17:00 -> 21:00 ; 19:00 -> 23:00 (RD = UTC-4)
def at_utc(d, local_hour):
    return datetime(d.year, d.month, d.day, local_hour + UTC_OFFSET, 0, 0)

Attendance = env["hr.attendance"]
for emp in employees:
    day = period_start
    while day <= period_end:
        if day.weekday() < 5:    # lunes-viernes
            # Mañana y tarde como marcas separadas (respeta el almuerzo 12-13),
            # así la jornada normal da 8 h y solo los martes dan 2 h extra.
            afternoon_out = 19 if day.weekday() == 1 else 17   # martes: hasta 19:00
            for c_in, c_out in [(8, 12), (13, afternoon_out)]:
                check_in = at_utc(day, c_in)
                check_out = at_utc(day, c_out)
                if not Attendance.search([("employee_id", "=", emp.id), ("check_in", "=", check_in)], limit=1):
                    # create() dispara _update_overtime -> crea las líneas de horas extra
                    Attendance.create({
                        "employee_id": emp.id,
                        "check_in": check_in,
                        "check_out": check_out,
                    })
        day += timedelta(days=1)

# Asegura que las horas extra queden aprobadas (validación: automática)
env["hr.attendance.overtime.line"].search([
    ("employee_id", "in", employees.ids), ("status", "!=", "approved"),
]).write({"status": "approved"})

# Acción de demo (solo para el manual): lista las líneas de horas extra del
# período, así la captura muestra las horas extra detectadas por día.
ot_action = env["ir.actions.act_window"].search(
    [("res_model", "=", "hr.attendance.overtime.line"), ("name", "=", "Horas extra (Asistencia)")], limit=1)
if not ot_action:
    ot_list_view = env["ir.ui.view"].create({
        "name": "demo.ot.line.list",
        "model": "hr.attendance.overtime.line",
        "type": "list",
        "arch": """
            <list create="0" edit="0" default_order="date asc, employee_id">
                <field name="date" string="Día"/>
                <field name="employee_id" string="Empleado"/>
                <field name="duration" string="Horas extra" sum="Total"/>
                <field name="amount_rate" string="Tasa de pago"/>
                <field name="status" string="Estado"/>
            </list>
        """,
    })
    ot_action = env["ir.actions.act_window"].create({
        "name": "Horas extra (Asistencia)",
        "res_model": "hr.attendance.overtime.line",
        "view_mode": "list",
        "view_id": ot_list_view.id,
        "domain": "[('duration', '>', 0)]",
    })
if not env.ref("hr_attendance.demo_ot_lines_action", raise_if_not_found=False):
    env["ir.model.data"].create({
        "module": "hr_attendance", "name": "demo_ot_lines_action",
        "model": "ir.actions.act_window", "res_id": ot_action.id, "noupdate": True,
    })

# ── 6. Recibo de nómina del período (calculado) ──────────────────────────────
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

env.cr.commit()
ot_lines = env["hr.attendance.overtime.line"].search([("employee_id", "in", employees.ids)])
ot_hours = sum(ot_lines.mapped("duration"))
print("SEED OK: empleados=%d asistencias=%d lineas_extra=%d horas_extra=%.1f recibos=%d periodo=%s" % (
    len(employees), env["hr.attendance"].search_count([("employee_id", "in", employees.ids)]),
    len(ot_lines), ot_hours, len(slips), period_start.strftime("%m/%Y")))
