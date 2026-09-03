#!/bin/bash
# verify_l10n_do_natural_days.sh — chequea l10n_do_hr_holidays sobre una DB con
# nomina: duracion, festivos, horario intacto, work entries y dias trabajados.
#
# Uso: ./verify_l10n_do_natural_days.sh [--db=DB] [--skip-update]
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_CONTAINER="odoo-db"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="l10n_do_hr_holidays"

DB="test_v19_l10n_do_hr_holidays"
DO_UPDATE=true
for arg in "$@"; do
  case "$arg" in
    --db=*)        DB="${arg#--db=}" ;;
    --skip-update) DO_UPDATE=false ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_FLAGS="-c /etc/odoo/odoo.conf --db_host=$DB_HOST --db_port=$DB_PORT \
--db_user=$DB_USER --db_password=$DB_PASS --no-http --max-cron-threads=0 \
--workers=0 --log-level=warn"

echo "======================================================"
echo " Verify: duracion en dias calendario (RD)"
echo " Modulo : $MODULE"
echo " DB     : $DB"
echo " Cont.  : $CONTAINER"
echo "======================================================"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: el daemon de Docker no responde. Abre Docker Desktop y reintenta." >&2
  exit 1
fi

if ! docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
     "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1; then
  echo "ERROR: la DB '$DB' no existe en $DB_CONTAINER." >&2
  echo "       Creala con: cd tools/manual-generator && ./generate-manual.sh \\" >&2
  echo "         --module=l10n_do_hr_holidays \\" >&2
  echo "         --extra-modules=l10n_do_hr_payroll,hr_work_entry_holidays --keep-db" >&2
  exit 1
fi

if $DO_UPDATE; then
  echo "--- odoo -u $MODULE -----------------------------------"
  docker exec -i "$CONTAINER" bash -lc "odoo $ODOO_FLAGS -d $DB -u $MODULE --stop-after-init" \
    || { echo "ERROR: el update fallo (vista rota?)." >&2; exit 1; }
fi

echo "--- asserts -------------------------------------------"
docker exec -i "$CONTAINER" bash -lc "odoo shell $ODOO_FLAGS -d $DB" <<'PYEOF'
from datetime import date, datetime

import pytz

failures = []


def check(label, cond):
    print(("  [ok]   " if cond else "  [FAIL] ") + label)
    if not cond:
        failures.append(label)


TZ = "America/Santo_Domingo"
MONDAY, WEDNESDAY, SATURDAY, SUNDAY = (
    date(2026, 3, 2), date(2026, 3, 4), date(2026, 3, 7), date(2026, 3, 8),
)

company = env.company
company.resource_calendar_id.tz = TZ
env.user.tz = TZ

calendar = env["resource.calendar"].create({
    "name": "L-V 8h (verify)",
    "tz": TZ,
    "company_id": company.id,
    "hours_per_day": 8.0,
    "attendance_ids": [
        (0, 0, {
            "name": name, "dayofweek": str(day),
            "hour_from": hour_from, "hour_to": hour_to, "day_period": period,
        })
        for day, name in enumerate(["Lunes", "Martes", "Miercoles", "Jueves", "Viernes"])
        for hour_from, hour_to, period in [(8.0, 12.0, "morning"), (13.0, 17.0, "afternoon")]
    ],
})

structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee", raise_if_not_found=False)
if not structure_type:
    structure_type = env["hr.payroll.structure.type"].search([], limit=1)


def make_employee(name):
    return env["hr.employee"].create({
        "name": name,
        "company_id": company.id,
        "resource_calendar_id": calendar.id,
        "tz": TZ,
        "date_version": date(2025, 1, 1),
        "contract_date_start": date(2025, 1, 1),
        "wage": 40000,
        "structure_type_id": structure_type.id,
    })


emp_working = make_employee("Empleado dias laborables")
emp_natural = make_employee("Empleado dias calendario")

work_entry_type = env["hr.work.entry.type"].search([("code", "=", "LEAVE110")], limit=1) \
    or env.ref("hr_work_entry.work_entry_type_leave")


def make_leave_type(name, duration_type):
    return env["hr.leave.type"].create({
        "name": name,
        "requires_allocation": False,
        "request_unit": "day",
        "leave_validation_type": "no_validation",
        "company_id": company.id,
        "l10n_do_duration_type": duration_type,
        "work_entry_type_id": work_entry_type.id,
    })


lt_working = make_leave_type("Vacaciones (laborables)", "working_day")
lt_natural = make_leave_type("Licencia (calendario)", "natural_day")


def make_leave(employee, leave_type, date_from, date_to):
    return env["hr.leave"].create({
        "employee_id": employee.id,
        "holiday_status_id": leave_type.id,
        "request_date_from": date_from,
        "request_date_to": date_to,
    })


leave_working = make_leave(emp_working, lt_working, MONDAY, SUNDAY)
leave_natural = make_leave(emp_natural, lt_natural, MONDAY, SUNDAY)
print("  working_day: %s | natural_day: %s" % (
    leave_working.duration_display, leave_natural.duration_display))
check("lunes->domingo working_day = 5 dias", leave_working.number_of_days == 5)
check("lunes->domingo natural_day = 7 dias", leave_natural.number_of_days == 7)
check("natural_day conserva las horas reales del calendario (40)",
      leave_natural.number_of_hours == 40)
check("las dos licencias quedan aprobadas",
      leave_working.state == "validate" and leave_natural.state == "validate")

# otra semana y otros empleados: si no, el festivo contamina los work entries
env["resource.calendar.leaves"].create({
    "name": "Festivo de prueba (miercoles 18/03)",
    "company_id": company.id,
    "date_from": datetime(2026, 3, 18, 4, 0, 0),
    "date_to": datetime(2026, 3, 19, 3, 59, 59),
})
leave_working_ph = make_leave(
    make_employee("Empleado laborables + festivo"), lt_working,
    date(2026, 3, 16), date(2026, 3, 22))
leave_natural_ph = make_leave(
    make_employee("Empleado calendario + festivo"), lt_natural,
    date(2026, 3, 16), date(2026, 3, 22))
check("con festivo el working_day baja a 4 dias", leave_working_ph.number_of_days == 4)
check("con festivo el natural_day sigue en 7 dias", leave_natural_ph.number_of_days == 7)

tz = pytz.timezone(TZ)
saturday = calendar._attendance_intervals_batch(
    tz.localize(datetime(2026, 3, 7, 0, 0, 0)),
    tz.localize(datetime(2026, 3, 7, 23, 59, 59)),
)[False]
check("el sabado sigue sin asistencias en el horario", not list(saturday))
check("el horario sigue siendo de lunes a viernes",
      set(calendar.attendance_ids.mapped("dayofweek")) == {"0", "1", "2", "3", "4"})

version = emp_natural.version_id
version.generate_work_entries(date(2026, 3, 1), date(2026, 3, 14), force=True)
entries = env["hr.work.entry"].search([
    ("employee_id", "=", emp_natural.id),
    ("date", ">=", datetime(2026, 3, 2, 0, 0, 0)),
    ("date", "<=", datetime(2026, 3, 8, 23, 59, 59)),
])
by_day = {}
for entry in entries:
    by_day.setdefault(entry.date, []).append(entry)
for day in sorted(by_day):
    print("    %s %-9s %s" % (
        day, day.strftime("%a"),
        ", ".join("%s %.1fh" % (e.work_entry_type_id.code, e.duration) for e in by_day[day])))
check("no hay work entries el sabado 07/03", SATURDAY not in by_day)
check("no hay work entries el domingo 08/03", SUNDAY not in by_day)
leave_entries = entries.filtered(lambda e: e.leave_id == leave_natural)
check("solo 5 work entries de ausencia (lunes a viernes)", len(leave_entries) == 5)
check("las 5 ausencias suman 40 horas", sum(leave_entries.mapped("duration")) == 40)

struct = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base", raise_if_not_found=False) \
    or structure_type.default_struct_id \
    or env["hr.payroll.structure"].search([("use_worked_day_lines", "=", True)], limit=1)
payslip = env["hr.payslip"].create({
    "name": "Verify natural days",
    "struct_id": struct.id,
    "version_id": version.id,
    "employee_id": emp_natural.id,
    "date_from": date(2026, 3, 1),
    "date_to": date(2026, 3, 14),
})
for line in payslip.worked_days_line_ids:
    print("    %-28s %5.2f dias %6.2f horas" % (
        line.work_entry_type_id.code or line.name, line.number_of_days, line.number_of_hours))
leave_lines = payslip.worked_days_line_ids.filtered(
    lambda l: l.work_entry_type_id == work_entry_type)
check("la nomina cuenta 5 dias de ausencia, no 7",
      bool(leave_lines) and sum(leave_lines.mapped("number_of_days")) == 5)
check("la nomina cuenta 40 horas de ausencia",
      bool(leave_lines) and sum(leave_lines.mapped("number_of_hours")) == 40)

print("")
if failures:
    print("RESULTADO: %d check(s) fallaron" % len(failures))
    for label in failures:
        print("  - " + label)
else:
    print("RESULTADO: todos los checks pasaron")
PYEOF
