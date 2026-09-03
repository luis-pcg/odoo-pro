# Seed del manual de l10n_do_hr_holidays; corre dentro de `odoo shell`.
#   ./generate-manual.sh --module=l10n_do_hr_holidays \
#     --extra-modules=l10n_do_hr_payroll,hr_work_entry_holidays
from datetime import date, datetime, timedelta

TZ = "America/Santo_Domingo"
UTC_OFFSET = 4  # hora local + 4 = UTC

today = date.today()
first = today.replace(day=1)
monday_1 = first + timedelta(days=(7 - first.weekday()) % 7)
sunday_1 = monday_1 + timedelta(days=6)
monday_2 = monday_1 + timedelta(days=7)
sunday_2 = monday_2 + timedelta(days=6)
holiday = monday_2 + timedelta(days=2)
month_start = first
month_end = (first + timedelta(days=31)).replace(day=1) - timedelta(days=1)

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"

company.write({"name": "Empresa Dominicana SRL", "country_id": do.id})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()

admin = env.ref("base.user_admin")
for xmlid in ["hr_holidays.group_hr_holidays_manager", "hr.group_hr_manager"]:
    group = env.ref(xmlid, raise_if_not_found=False)
    if group:
        admin.write({"group_ids": [(4, group.id)]})
admin.tz = TZ

attendances = []
for day, name in enumerate(["Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]):
    for hour_from, hour_to, period in [(8.0, 12.0, "morning"), (13.0, 17.0, "afternoon")]:
        attendances.append((0, 0, {
            "name": name,
            "dayofweek": str(day),
            "hour_from": hour_from,
            "hour_to": hour_to,
            "day_period": period,
        }))
calendar = env["resource.calendar"].create({
    "name": "Lunes a viernes 40h (RD)",
    "company_id": company.id,
    "tz": TZ,
    "hours_per_day": 8.0,
    "attendance_ids": attendances,
})
company.resource_calendar_id = calendar

env["resource.calendar.leaves"].create({
    "name": "Día feriado (demostración)",
    "company_id": company.id,
    "date_from": datetime.combine(holiday, datetime.min.time()) + timedelta(hours=UTC_OFFSET),
    "date_to": datetime.combine(holiday, datetime.max.time()) + timedelta(hours=UTC_OFFSET),
})

structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee", raise_if_not_found=False)
contract_start = date(today.year - 1, 1, 1)


def make_employee(name, cedula):
    vals = {
        "name": name,
        "company_id": company.id,
        "country_id": do.id,
        "identification_id": cedula,
        "resource_calendar_id": calendar.id,
        "tz": TZ,
        "date_version": contract_start,
        "contract_date_start": contract_start,
        "wage": 45000,
    }
    if structure_type:
        vals["structure_type_id"] = structure_type.id
    return env["hr.employee"].create(vals)


emp_laborables = make_employee("Ana Rodríguez Féliz", "00445678901")
emp_calendario = make_employee("Pedro Martínez Cruz", "00334567890")
emp_laborables_feriado = make_employee("Carmen Díaz Polanco", "00667890123")
emp_calendario_feriado = make_employee("José Ramírez Guzmán", "00778901234")

work_entry_type = env.ref("hr_work_entry.work_entry_type_legal_leave", raise_if_not_found=False) \
    or env["hr.work.entry.type"].search([("code", "=", "LEAVE110")], limit=1) \
    or env.ref("hr_work_entry.work_entry_type_leave", raise_if_not_found=False)


def make_leave_type(name, duration_type, color):
    vals = {
        "name": name,
        "requires_allocation": False,
        "request_unit": "day",
        "leave_validation_type": "hr",
        "company_id": company.id,
        "l10n_do_duration_type": duration_type,
        "color": color,
    }
    if work_entry_type and "work_entry_type_id" in env["hr.leave.type"]._fields:
        vals["work_entry_type_id"] = work_entry_type.id
    return env["hr.leave.type"].create(vals)


lt_vacaciones = make_leave_type("Vacaciones", "working_day", 2)
lt_matrimonio = make_leave_type("Licencia por matrimonio (5 días)", "natural_day", 4)
lt_duelo = make_leave_type("Licencia por duelo (3 días)", "natural_day", 6)
lt_paternidad = make_leave_type("Licencia por paternidad (2 días)", "natural_day", 8)

# xmlids fijos: el generador abre el registro por xmlid, no buscando por nombre
env["ir.model.data"]._update_xmlids([
    {"xml_id": "__manual__.lt_vacaciones", "record": lt_vacaciones},
    {"xml_id": "__manual__.lt_matrimonio", "record": lt_matrimonio},
])

# sin lang en el contexto, `duration_display` se guarda como "7 days"
Leave = env["hr.leave"].with_context(
    mail_notrack=True, tracking_disable=True, lang="es_DO")


def make_leave(employee, leave_type, date_from, date_to):
    leave = Leave.create({
        "employee_id": employee.id,
        "holiday_status_id": leave_type.id,
        "request_date_from": date_from,
        "request_date_to": date_to,
    })
    leave.action_approve()
    return leave


leaves = [
    ("semana sin feriado, laborables",
     make_leave(emp_laborables, lt_vacaciones, monday_1, sunday_1)),
    ("semana sin feriado, calendario",
     make_leave(emp_calendario, lt_matrimonio, monday_1, sunday_1)),
    ("semana con feriado, laborables",
     make_leave(emp_laborables_feriado, lt_vacaciones, monday_2, sunday_2)),
    ("semana con feriado, calendario",
     make_leave(emp_calendario_feriado, lt_duelo, monday_2, sunday_2)),
]
env["ir.model.data"]._update_xmlids([
    {"xml_id": "__manual__.leave_laborables", "record": leaves[0][1]},
    {"xml_id": "__manual__.leave_calendario", "record": leaves[1][1]},
])
for label, leave in leaves:
    print("SEED duracion: %-32s %s" % (label, leave.duration_display))

version = emp_calendario.version_id
try:
    version.generate_work_entries(month_start, month_end, force=True)
except Exception:
    env.cr.rollback()

struct = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base", raise_if_not_found=False)
if struct and not struct.journal_id:
    journal = env["account.journal"].search(
        [("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
    if journal:
        struct.journal_id = journal
if struct:
    payslip = env["hr.payslip"].create({
        "name": "Recibo de %s" % emp_calendario.name,
        "employee_id": emp_calendario.id,
        "version_id": version.id,
        "struct_id": struct.id,
        "date_from": month_start,
        "date_to": month_end,
    })
    try:
        payslip.compute_sheet()
    except Exception:
        env.cr.rollback()
    env["ir.model.data"]._update_xmlids([
        {"xml_id": "__manual__.payslip", "record": payslip},
    ])
    for line in payslip.worked_days_line_ids:
        print("SEED nomina: %-10s %5.2f dias %6.2f horas" % (
            line.work_entry_type_id.code or line.name,
            line.number_of_days, line.number_of_hours))

env.cr.commit()
print("SEED OK")
