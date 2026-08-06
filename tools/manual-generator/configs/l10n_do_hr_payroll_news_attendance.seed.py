# Seed for the v17 manual of the CUSTOM overtime flow (modules to be discarded):
#   l10n_do_hr_news_attendance + l10n_do_hr_payroll_news_attendance.
# Flow: asistencia -> asistente "Crear novedades desde asistencia" -> Novedad
#       (con horas extra) -> aprobar -> input en el recibo de nomina.
# Executed inside `odoo shell`. UI in Spanish.
from datetime import date, datetime, timedelta

today = date.today()
period_start = today.replace(day=1)            # el asistente usa el MES ACTUAL
period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
TZ = "America/Santo_Domingo"
UTC_OFFSET = 4

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True

# ── 0. Español ───────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    try:
        env["base.language.install"].create({"lang": "es_DO", "overwrite": True}).lang_install()
    except Exception:
        env.cr.rollback()
env.ref("base.user_admin").write({"lang": "es_DO", "tz": TZ})

# ── 1. Compañía ───────────────────────────────────────────────────────────────
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()

# ── 2. Calendario (40h, lun-vie 8-12 / 13-17, tz RD) ─────────────────────────
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

structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
struct_base = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
salary_journal = env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
if not salary_journal:
    salary_journal = env["account.journal"].create(
        {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id})
for struct in env["hr.payroll.structure"].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal

# ── 3. Tipo de novedad de horas extra (asistente) ────────────────────────────
# El preset "Horas Extra (35%)" ya trae input_type_id; le agregamos el origen
# de asistencias + tipo de hora extra que exige el asistente.
news_type = env.ref("l10n_do_hr_news.news_type_overtime")
news_type.write({
    "name": "Horas Extra Diurnas (35%)",
    "attendances_to_take": "month",
    "overtime_type": "daytime",
})

# ── 4. Empleados con contrato (hr.contract, v17) ─────────────────────────────
Employee = env["hr.employee"]
contract_start = date(today.year - 1, 1, 1)
EMPLOYEES = [
    ("Carlos Méndez", "00112345678", "male",   "1988-03-15", 35000),
    ("María Santana", "00223456789", "female", "1992-07-22", 42000),
]
employees = env["hr.employee"]
for name, cedula, gender, birthday, wage in EMPLOYEES:
    emp = Employee.search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = Employee.create({
            "name": name, "company_id": company.id, "country_id": do.id,
            "identification_id": cedula, "gender": gender, "birthday": birthday,
            "tz": TZ, "resource_calendar_id": calendar_rd.id,
        })
    if not emp.contract_ids:
        env["hr.contract"].create({
            "name": "Contrato %s" % name,
            "employee_id": emp.id,
            "wage": wage,
            "structure_type_id": structure_type.id,
            "resource_calendar_id": calendar_rd.id,
            "date_start": contract_start,
            "state": "open",
            "company_id": company.id,
        })
    employees |= emp

# ── 5. Asistencias del mes (martes 2h extra hasta 19:00) ─────────────────────
def at_utc(d, local_hour):
    return datetime(d.year, d.month, d.day, local_hour + UTC_OFFSET, 0, 0)

Attendance = env["hr.attendance"]
day = period_start
while day <= min(period_end, today):
    if day.weekday() < 5:
        c_out = 19 if day.weekday() == 1 else 17   # martes: 2h extra
        for emp in employees:
            ci = at_utc(day, 8)
            if not Attendance.search([("employee_id", "=", emp.id), ("check_in", "=", ci)], limit=1):
                Attendance.create({"employee_id": emp.id, "check_in": ci, "check_out": at_utc(day, c_out)})
    day += timedelta(days=1)

# ── 6. Asistente: crea las novedades de horas extra desde la asistencia ───────
News = env["l10n.do.hr.news"].with_context(tz=TZ)   # tz RD para el cálculo de horas
created = News.compute_news_employees_attendances(employee_ids=employees.ids, news_type=news_type)

# ── 7. Aprobar las novedades (draft -> confirm -> validate) ──────────────────
for nv in created:
    try:
        nv.action_confirm()
        nv.action_approve()
    except Exception as exc:
        print("WARN approve %s: %s" % (nv.name, exc))

# ── 8. Recibo de nómina del mes (toma el input desde la novedad aprobada) ────
run = env["hr.payslip.run"].search([("date_start", "=", period_start)], limit=1)
if not run:
    run = env["hr.payslip.run"].create({
        "name": "Nómina %s" % period_start.strftime("%m/%Y"),
        "date_start": period_start, "date_end": period_end,
    })
slips = env["hr.payslip"]
for emp in employees:
    slip = env["hr.payslip"].search([("employee_id", "=", emp.id), ("payslip_run_id", "=", run.id)], limit=1)
    if not slip:
        slip = env["hr.payslip"].create({
            "name": "Nómina %s" % emp.name, "employee_id": emp.id,
            "contract_id": emp.contract_ids[:1].id, "struct_id": struct_base.id,
            "date_from": period_start, "date_to": period_end, "payslip_run_id": run.id,
        })
    slips |= slip
# Inserta el input de la novedad aprobada en el recibo. Evitamos el cálculo
# completo de la hoja (una regla salarial de la demo v17 falla) — para el manual
# basta mostrar que el monto de la novedad llega como entrada salarial.
for slip in slips:
    try:
        slip.process_inputs_from_news()
    except Exception as exc:
        print("WARN inputs %s: %s" % (slip.name, exc))
try:
    with env.cr.savepoint():
        slips.compute_sheet()
except Exception as exc:
    print("WARN compute_sheet (se deja el recibo con el input sin calcular): %s" % exc)

# ── 9. Acciones de demo (manual): novedad y tipo de novedad concretos ────────
def demo_action(xmlid_name, name, model, domain, view_mode="list,form"):
    if env.ref("l10n_do_hr_news.%s" % xmlid_name, raise_if_not_found=False):
        return
    act = env["ir.actions.act_window"].create({
        "name": name, "res_model": model, "view_mode": view_mode, "domain": domain})
    env["ir.model.data"].create({
        "module": "l10n_do_hr_news", "name": xmlid_name,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True})

demo_action("demo_news_type_action", "Tipos de novedad", "l10n.do.hr.news.type",
            "[('id', '=', %d)]" % news_type.id)
demo_action("demo_news_action", "Novedades de horas extra", "l10n.do.hr.news",
            "[('id', 'in', %s)]" % (created.ids or [0]))
demo_action("demo_payslip_action", "Recibos de nómina", "hr.payslip",
            "[('id', 'in', %s)]" % (slips.ids or [0]))

env.cr.commit()
print("SEED OK: empleados=%d asistencias=%d novedades=%d montos=%s recibos=%d periodo=%s" % (
    len(employees), Attendance.search_count([("employee_id", "in", employees.ids)]),
    len(created), created.mapped("payslip_input_amount"), len(slips),
    period_start.strftime("%m/%Y")))
