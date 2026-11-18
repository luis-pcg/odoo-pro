# Seed para el manual de l10n_do_hr_holidays (Odoo 17).
# Monta una compañía dominicana con jornada lunes-viernes y dos empleados que
# piden el MISMO rango de fechas (jue 05/03/2026 - lun 09/03/2026) con tipos de
# permiso distintos, para que el contraste se vea de un vistazo:
#   - Licencia por matrimonio (días calendario) -> 5 días
#   - Vacaciones             (días laborables)  -> 3 días
# Se ejecuta dentro de `odoo shell`. Interfaz en español.
from datetime import date

TZ = "America/Santo_Domingo"
DATE_FROM = date(2026, 3, 5)   # jueves
DATE_TO = date(2026, 3, 9)     # lunes
# La licencia médica de María va a otro rango: dos permisos no pueden solaparse.
MED_FROM = date(2026, 4, 2)    # jueves
MED_TO = date(2026, 4, 6)      # lunes

company = env.ref("base.main_company")
do = env.ref("base.do")

# ── 0. Español ───────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").write({"lang": "es_DO", "tz": TZ})

# ── 1. Compañía ──────────────────────────────────────────────────────────────
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id})
company.partner_id.lang = "es_DO"

# ── 2. Jornada 40h, lunes a viernes 8-12 / 13-17, tz RD ──────────────────────
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

# ── 3. Empleados ─────────────────────────────────────────────────────────────
Employee = env["hr.employee"]
EMPLOYEES = [
    ("Juan Pérez", "00112345678", "male"),
    ("María Gómez", "00223456789", "female"),
]
employees = {}
for name, cedula, gender in EMPLOYEES:
    emp = Employee.search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = Employee.create({
            "name": name, "company_id": company.id, "country_id": do.id,
            "identification_id": cedula, "gender": gender, "tz": TZ,
            "resource_calendar_id": calendar_rd.id,
        })
    employees[name] = emp

# ── 4. Tipos de permiso ──────────────────────────────────────────────────────
# El campo l10n_do_duration_type es lo que aporta el módulo: decide si la
# duración se mide en días laborables (estándar Odoo) o en días calendario.
LeaveType = env["hr.leave.type"]
TYPES = [
    # (nombre, duración, requiere asignación)
    ("Vacaciones", "working_day", "yes"),
    ("Licencia médica", "natural_day", "yes"),
    ("Licencia por matrimonio", "natural_day", "no"),
    ("Licencia por duelo", "natural_day", "no"),
    ("Permiso por horas", "working_day", "no"),
]
leave_types = {}
for name, duration_type, requires in TYPES:
    lt = LeaveType.search([("name", "=", name), ("company_id", "in", [company.id, False])], limit=1)
    vals = {
        "name": name,
        "company_id": company.id,
        "request_unit": "hour" if name == "Permiso por horas" else "day",
        "requires_allocation": requires,
        "allocation_validation_type": "no",
        "leave_validation_type": "no_validation",
        "l10n_do_duration_type": duration_type,
        "time_type": "leave",
    }
    # Sólo se crea: reescribir `requires_allocation` en un tipo que ya tiene
    # permisos tomados lo bloquea Odoo, y así el seed se puede volver a correr.
    if not lt:
        lt = LeaveType.create(vals)
    leave_types[name] = lt

# ── 5. Asignación de vacaciones (14 días) ────────────────────────────────────
Allocation = env["hr.leave.allocation"]
allocations = {}


def allocate(emp, type_name, days, label):
    alloc = Allocation.search([
        ("employee_id", "=", emp.id),
        ("holiday_status_id", "=", leave_types[type_name].id),
    ], limit=1)
    if not alloc:
        alloc = Allocation.create({
            "name": label,
            "holiday_status_id": leave_types[type_name].id,
            "employee_id": emp.id,
            "number_of_days": days,
            "date_from": date(2026, 1, 1),
        })
    if alloc.state != "validate":
        alloc.action_validate()
    return alloc


for emp in employees.values():
    allocations[emp.name] = allocate(emp, "Vacaciones", 14, "Vacaciones 2026")
# Asignación medida en días calendario: la solicitud la consume día por día,
# fines de semana incluidos.
allocations["médica"] = allocate(employees["María Gómez"], "Licencia médica", 30, "Licencia médica 2026")

# ── 6. Solicitudes: mismo rango, distinta base de cálculo ────────────────────
Leave = env["hr.leave"]
REQUESTS = [
    # (empleado, tipo, desde, hasta)
    ("Juan Pérez", "Licencia por matrimonio", DATE_FROM, DATE_TO),   # calendario -> 5
    ("María Gómez", "Vacaciones", DATE_FROM, DATE_TO),               # laborables -> 3
    ("María Gómez", "Licencia médica", MED_FROM, MED_TO),            # calendario con asignación -> 5
]
leaves = {}
for emp_name, type_name, req_from, req_to in REQUESTS:
    emp = employees[emp_name]
    lt = leave_types[type_name]
    leave = Leave.search([("employee_id", "=", emp.id), ("holiday_status_id", "=", lt.id)], limit=1)
    if not leave:
        leave = Leave.create({
            "employee_id": emp.id,
            "holiday_status_id": lt.id,
            "request_date_from": req_from,
            "request_date_to": req_to,
        })
    leaves[type_name] = leave

# ── 7. XML ids y acciones de demo para las capturas ─────────────────────────
def xmlid(name, record):
    """Registra un xml_id estable para que capture.mjs abra el registro por id."""
    ref = env.ref("l10n_do_hr_holidays.%s" % name, raise_if_not_found=False)
    if ref:
        return
    env["ir.model.data"].create({
        "module": "l10n_do_hr_holidays", "name": name,
        "model": record._name, "res_id": record.id, "noupdate": True})


xmlid("demo_type_matrimonio", leave_types["Licencia por matrimonio"])
xmlid("demo_type_vacaciones", leave_types["Vacaciones"])
xmlid("demo_type_medica", leave_types["Licencia médica"])
xmlid("demo_leave_matrimonio", leaves["Licencia por matrimonio"])
xmlid("demo_leave_vacaciones", leaves["Vacaciones"])
xmlid("demo_leave_medica", leaves["Licencia médica"])
xmlid("demo_allocation_medica", allocations["médica"])


def demo_action(xmlid_name, name, model, domain, view_mode="tree,form", context="{}"):
    existing = env.ref("l10n_do_hr_holidays.%s" % xmlid_name, raise_if_not_found=False)
    if existing:
        existing.write({"domain": domain, "view_mode": view_mode, "context": context})
        return
    act = env["ir.actions.act_window"].create({
        "name": name, "res_model": model, "view_mode": view_mode,
        "domain": domain, "context": context})
    env["ir.model.data"].create({
        "module": "l10n_do_hr_holidays", "name": xmlid_name,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True})


demo_action("demo_leave_type_action", "Tipos de tiempo personal", "hr.leave.type",
            "[('id', 'in', %s)]" % sorted(lt.id for lt in leave_types.values()))
demo_action("demo_leave_action", "Solicitudes de tiempo personal", "hr.leave",
            "[('id', 'in', %s)]" % sorted(lv.id for lv in leaves.values()))
demo_action("demo_allocation_action", "Asignaciones", "hr.leave.allocation",
            "[('id', 'in', %s)]" % sorted(a.id for a in allocations.values()))
# Kanban de tipos con el contexto de un empleado: muestra "Time Off Taken",
# que es donde se ve que la asignación se consumió en días calendario.
demo_action("demo_balance_action", "Balance de María Gómez", "hr.leave.type",
            "[('id', 'in', %s)]" % sorted([leave_types["Vacaciones"].id, leave_types["Licencia médica"].id]),
            view_mode="kanban,tree,form",
            context="{'employee_id': %d}" % employees["María Gómez"].id)

env.cr.commit()
print("SEED OK")
for type_name, leave in leaves.items():
    print("  %-24s %-14s %s -> %s = %s días (%s)" % (
        type_name, leave.employee_id.name, leave.request_date_from, leave.request_date_to,
        leave.number_of_days, leave.holiday_status_id.l10n_do_duration_type))
print("  Asignación vacaciones (laborables): tomados=%s de %s" % (
    allocations["María Gómez"].leaves_taken, allocations["María Gómez"].number_of_days))
print("  Asignación licencia médica (calendario): tomados=%s de %s" % (
    allocations["médica"].leaves_taken, allocations["médica"].number_of_days))
