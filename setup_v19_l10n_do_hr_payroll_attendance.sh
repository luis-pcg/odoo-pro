#!/bin/bash
# setup_v19_l10n_do_hr_payroll_attendance.sh
#
# Crea y configura una base de datos NUEVA (no de test, sin datos demo) para
# probar el puente de horas extra por asistencia hacia la nomina dominicana:
# el modulo l10n_do_hr_payroll_news_attendance en Odoo 19.
#
# Que hace (siguiendo el manual docs/manuals/hr_payroll_attendance/README.md y
# el README del propio modulo):
#
#   1. Crea la DB v19_l10n_do_hr_payroll_attendance e instala
#      l10n_do_hr_payroll_news_attendance (arrastra l10n_do_hr_payroll_news,
#      hr_payroll_attendance -> hr_work_entry_attendance -> hr_attendance).
#   2. Configura la compania: pais RD, moneda DOP, tipo de riesgo laboral.
#      Deja la validacion de horas extra en "Aprobacion automatica".
#   3. Configura calendario laboral RD de 44h (tz UTC para overtime determinista).
#   4. Crea una Regla de horas extra (Overtime Ruleset) "Republica Dominicana"
#      con una regla diaria por cantidad (paga, tipo de entrada Horas Extra 35%).
#   5. Crea empleados dominicanos con contrato vigente (hr.version) basado en
#      calendario + esa regla de horas extra (overtime_from_attendance=True).
#   6. Registra ASISTENCIAS (hr.attendance) que exceden la jornada para algunos
#      empleados -> Odoo genera lineas de horas extra aprobadas.
#   7. Genera entradas de trabajo y CALCULA la nomina. El puente del modulo, en
#      compute_sheet, lee la linea OVERTIME de Dias Trabajados y crea/actualiza
#      un hr.salary.attachment de un periodo etiquetado [HE-ASISTENCIA] que
#      alimenta el input HEL; la regla salarial HEL paga el recargo 35%.
#   8. Verifica: imprime por empleado las horas OVERTIME, el attachment
#      [HE-ASISTENCIA], el input HEL y el monto pagado por la regla HEL; y
#      comprueba la idempotencia (recomputar no duplica el attachment).
#
# Los datos se COMMITEAN (la DB queda lista para usar via web).
#
# Uso:
#   ./setup_v19_l10n_do_hr_payroll_attendance.sh                  # crea DB nueva
#   ./setup_v19_l10n_do_hr_payroll_attendance.sh --db=mi_db       # nombre propio
#   ./setup_v19_l10n_do_hr_payroll_attendance.sh --recreate       # borra y recrea
#   ./setup_v19_l10n_do_hr_payroll_attendance.sh --skip-install   # solo siembra
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
# El modulo puente arrastra l10n_do_hr_payroll_news + hr_payroll_attendance
# (-> hr_work_entry_attendance -> hr_attendance). Instalamos hr_attendance
# explicito para asegurar sus reglas/UI.
MODULE="l10n_do_hr_payroll_news_attendance,hr_attendance"

DB_NAME="v19_l10n_do_hr_payroll_attendance"
RECREATE=false
SKIP_INSTALL=false
for arg in "$@"; do
  case "$arg" in
    --recreate)     RECREATE=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    --db=*)         DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Setup horas extra por asistencia -> nomina RD"
echo " Modulo     : l10n_do_hr_payroll_news_attendance"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo "======================================================"

wait_for_db() {
  docker exec "$CONTAINER" bash -lc "
    for i in \$(seq 1 30); do
      if PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
        echo 'Postgres OK (intento '\$i')'; exit 0
      fi
      sleep 2
    done
    echo 'ERROR: Postgres no respondio tras 30 intentos' >&2; exit 1
  "
}

db_exists() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" \
    | grep -q 1
}

if ! $SKIP_INSTALL; then
  echo "→ Esperando a Postgres..."
  wait_for_db || exit 1

  if db_exists; then
    if $RECREATE; then
      echo "→ DB $DB_NAME existe, eliminando (--recreate)..."
      docker exec "$CONTAINER" bash -lc "
        PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
          \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid()\" >/dev/null
        PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
      " || { echo 'ERROR eliminando la DB' >&2; exit 1; }
    else
      echo "ERROR: la DB $DB_NAME ya existe. Usa --recreate para reemplazarla o --skip-install para solo sembrar." >&2
      exit 1
    fi
  fi

  echo "→ Creando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULE sin datos demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
fi

echo "→ Configurando compania, calendario, regla de horas extra, empleados y asistencias..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
from datetime import date, datetime, timedelta

import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

today = date.today()
# Mes anterior completo para el lote de nomina
period_end = today.replace(day=1) - timedelta(days=1)
period_start = period_end.replace(day=1)

# ════════════════════════════════════════════════════════════════════════════
# 1. COMPANIA: pais RD, moneda DOP, riesgo laboral, validacion HE automatica
# ════════════════════════════════════════════════════════════════════════════
company = env.ref('base.main_company')
do = env.ref('base.do')
dop = env.ref('base.DOP')
dop.active = True
vals = {
    'name': 'Empresa Dominicana SRL',
    'country_id': do.id,
    'city': 'Santo Domingo',
    'phone': '809-555-0100',
    'l10n_do_occupational_risk_type_id': env.ref('l10n_do_hr_payroll.risk_type_1').id,
    # Horas extra aprobadas automaticamente (no requiere aprobacion de gerente)
    'attendance_overtime_validation': 'no_validation',
}
company.write(vals)
try:
    company.currency_id = dop.id
    print('Compania: %s | pais=%s moneda=%s riesgo=%s validacion_HE=%s' % (
        company.name, company.country_id.code, company.currency_id.name,
        company.l10n_do_occupational_risk_type_id.name,
        company.attendance_overtime_validation))
except Exception as e:
    env.cr.rollback()
    company.write(vals)
    print('AVISO: no se pudo cambiar la moneda a DOP (%s). Resto de config aplicada.' % e)

try:
    company.partner_id.with_context(no_vat_validation=True).vat = '131-79391-6'
except Exception:
    pass

# ════════════════════════════════════════════════════════════════════════════
# 2. CALENDARIO LABORAL RD 44h: L-V 8h (8-12 / 13-17) + sabado 4h (8-12)
#    tz=UTC para que el calculo de horas extra sea determinista en este demo.
# ════════════════════════════════════════════════════════════════════════════
attendances = []
for dow in range(5):  # lunes..viernes
    attendances.append((0, 0, {'name': 'Mañana', 'dayofweek': str(dow),
                               'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}))
    attendances.append((0, 0, {'name': 'Tarde', 'dayofweek': str(dow),
                               'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}))
attendances.append((0, 0, {'name': 'Sabado', 'dayofweek': '5',
                           'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}))
calendar_rd = env['resource.calendar'].create({
    'name': 'Jornada RD 44 horas',
    'company_id': company.id,
    'hours_per_day': 8,
    'tz': 'UTC',
    'attendance_ids': attendances,
})
company.resource_calendar_id = calendar_rd
print('Calendario: %s (tz=%s)' % (calendar_rd.name, calendar_rd.tz))

# ════════════════════════════════════════════════════════════════════════════
# 3. TIPO DE ESTRUCTURA / ESTRUCTURA BASE DEL MODULO + diario
# ════════════════════════════════════════════════════════════════════════════
structure_type = env.ref('l10n_do_hr_payroll.structure_type_employee')
structure_type.write({
    'default_resource_calendar_id': calendar_rd.id,
    'default_schedule_pay': 'monthly',
})
struct_base = env.ref('l10n_do_hr_payroll.hr_payroll_structure_base')

salary_journal = env['account.journal'].search(
    [('code', '=', 'SLR'), ('company_id', '=', company.id)], limit=1)
if not salary_journal:
    salary_journal = env['account.journal'].create({
        'name': 'Nómina', 'code': 'NOM', 'type': 'general', 'company_id': company.id})
for struct in env['hr.payroll.structure'].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal
print('Estructura: %s (tipo: %s, diario: %s)' % (
    struct_base.name, structure_type.name, struct_base.journal_id.name))

# ════════════════════════════════════════════════════════════════════════════
# 4. REGLA DE HORAS EXTRA (Overtime Ruleset) — "Republica Dominicana"
#    Regla diaria por cantidad: lo que excede la jornada del contrato es extra,
#    pagada, con tipo de entrada de trabajo "Horas Extra" (code OVERTIME) al 35%.
# ════════════════════════════════════════════════════════════════════════════
overtime_wet = env.ref('hr_work_entry.work_entry_type_overtime')  # code OVERTIME
ruleset = env['hr.attendance.overtime.ruleset'].create({
    'name': 'República Dominicana',
    'company_id': company.id,
    'country_id': do.id,
    'rate_combination_mode': 'max',
    'rule_ids': [(0, 0, {
        'name': 'Horas extra diurnas (35%)',
        'base_off': 'quantity',
        'quantity_period': 'day',
        'expected_hours_from_contract': True,
        'paid': True,
        'work_entry_type_id': overtime_wet.id,
        'amount_rate': 1.35,
    })],
})
print('Regla de horas extra: %s (%d regla, tipo entrada=%s code=%s)' % (
    ruleset.name, len(ruleset.rule_ids),
    overtime_wet.name, overtime_wet.code))

# ════════════════════════════════════════════════════════════════════════════
# 5. EMPLEADOS con contrato vigente (hr.version) basado en CALENDARIO + regla HE
#    (calendario + ruleset => las horas normales salen de la jornada y solo las
#     horas extra salen de la asistencia; el sueldo mensual fijo no se afecta).
# ════════════════════════════════════════════════════════════════════════════
Dept = env['hr.department']
departments = {
    'admin': Dept.create({'name': 'Administración'}),
    'ops': Dept.create({'name': 'Operaciones'}),
}
Partner = env['res.partner']
afp = Partner.create({'name': 'AFP Popular', 'is_company': True, 'country_id': do.id})
ars = Partner.create({'name': 'ARS Universal', 'is_company': True, 'country_id': do.id})

contract_start = date(today.year - 1, 1, 1)
# nombre, cedula, NSS, sexo, nacimiento, depto, salario, dias_con_HE (asistencia)
EMPLOYEES = [
    ('Juan Pérez Rodríguez',    '00112345678', '10001', 'male',   '1988-03-15', 'ops',   28000, 5),
    ('María Gómez Santana',     '00223456789', '10002', 'female', '1992-07-22', 'admin', 35000, 3),
    ('Pedro Martínez Cruz',     '00334567890', '10003', 'male',   '1985-11-08', 'ops',   45000, 8),
    ('Ana Rodríguez Féliz',     '00445678901', '10004', 'female', '1990-01-30', 'admin', 60000, 0),
    ('Luis Fernández Castillo', '00556789012', '10005', 'male',   '1983-05-12', 'ops',   90000, 0),
]

Employee = env['hr.employee']
employees = env['hr.employee']
emp_ot_days = {}
for name, cedula, nss, gender, birthday, dept, wage, ot_days in EMPLOYEES:
    emp = Employee.create({
        'name': name,
        'company_id': company.id,
        'country_id': do.id,
        'tz': 'UTC',
        'identification_id': cedula,
        'l10n_do_social_security_number': nss,
        'l10n_do_has_papers': True,
        'l10n_do_afp_partner_id': afp.id,
        'l10n_do_ars_partner_id': ars.id,
        'sex': gender,
        'birthday': birthday,
        'department_id': departments[dept].id,
        'resource_calendar_id': calendar_rd.id,
        'date_version': contract_start,
        'contract_date_start': contract_start,
        'wage': wage,
        'structure_type_id': structure_type.id,
    })
    # Contrato: basado en calendario (default) + regla de horas extra por asistencia
    emp.version_id.write({
        'l10n_do_schedule_retentions': 'end_of_month',
        'ruleset_id': ruleset.id,
        'overtime_from_attendance': True,
    })
    employees |= emp
    emp_ot_days[emp.id] = ot_days
    print('  + %-26s ced=%s RD$%-9s HE=%d dia(s)' % (
        name, cedula, '{:,.0f}'.format(wage), ot_days))
print('Empleados creados: %d' % len(employees))

# ════════════════════════════════════════════════════════════════════════════
# 6. ASISTENCIAS que exceden la jornada -> Odoo genera lineas de horas extra
#    Jornada 8-12 / 13-17 (8h/dia, sin linea de almuerzo). Asistencia
#    08:00-19:00 = 11h -> ~3h extra ese dia. Se registran en dias habiles del mes.
# ════════════════════════════════════════════════════════════════════════════
def weekdays_in_period(start, end, n):
    out, d = [], start
    while d <= end and len(out) < n:
        if d.weekday() < 5:  # L-V
            out.append(d)
        d += timedelta(days=1)
    return out

Attendance = env['hr.attendance']
total_att = 0
for emp in employees:
    ot_days = emp_ot_days[emp.id]
    if not ot_days:
        continue
    for d in weekdays_in_period(period_start, period_end, ot_days):
        Attendance.create({
            'employee_id': emp.id,
            # tz del empleado = UTC -> datetimes se interpretan en UTC
            'check_in': datetime(d.year, d.month, d.day, 8, 0, 0),
            'check_out': datetime(d.year, d.month, d.day, 19, 0, 0),
        })
        total_att += 1
print('Asistencias creadas: %d (08:00-19:00, ~3h extra/dia)' % total_att)

# Verificacion intermedia: lineas de horas extra aprobadas
ot_lines = env['hr.attendance.overtime.line'].search([
    ('employee_id', 'in', employees.ids),
    ('date', '>=', period_start), ('date', '<=', period_end),
])
approved = ot_lines.filtered(lambda l: l.status == 'approved')
print('Lineas de horas extra: %d (aprobadas: %d, total horas: %.2f)' % (
    len(ot_lines), len(approved), sum(approved.mapped('duration'))))

# ════════════════════════════════════════════════════════════════════════════
# 7. LOTE DE NOMINA: generar entradas de trabajo + compute_sheet (dispara puente)
# ════════════════════════════════════════════════════════════════════════════
line('=')
print(' Lote de nomina %s — %s' % (period_start, period_end))
line('=')
run = env['hr.payslip.run'].create({
    'name': 'Nómina %s' % period_start.strftime('%B %Y'),
    'date_start': period_start,
    'date_end': period_end,
})
slips = env['hr.payslip']
for emp in employees:
    # Generar entradas de trabajo del periodo (normales + horas extra aprobadas)
    try:
        emp.version_id.generate_work_entries(period_start, period_end, force=True)
    except Exception as e:
        print('  AVISO generate_work_entries %s: %s' % (emp.name, e))
    slips |= env['hr.payslip'].create({
        'name': 'Nómina %s' % emp.name,
        'employee_id': emp.id,
        'struct_id': struct_base.id,
        'date_from': period_start,
        'date_to': period_end,
        'payslip_run_id': run.id,
    })
slips.compute_sheet()

# ════════════════════════════════════════════════════════════════════════════
# 8. VERIFICACION: OVERTIME (dias trabajados) -> attachment [HE-ASISTENCIA]
#    -> input HEL -> regla salarial HEL (pago 35%)
# ════════════════════════════════════════════════════════════════════════════
Attachment = env['hr.salary.attachment']
TAG = '[HE-ASISTENCIA]'
print('%-24s %8s %10s %9s %12s %12s' % (
    'Empleado', 'HE(h)', 'Attach(h)', 'HEL in', 'HEL pago', 'NET'))
line()
ok = True
for slip in slips:
    def wd_hours(code):
        wl = slip.worked_days_line_ids.filtered(lambda r: r.code == code)
        return sum(wl.mapped('number_of_hours'))
    def input_amt(code):
        il = slip.input_line_ids.filtered(lambda r: r.code == code)
        return sum(il.mapped('amount'))
    def rule_amt(code):
        rl = slip.line_ids.filtered(lambda r: r.code == code)
        return sum(rl.mapped('total'))

    ot_h = wd_hours('OVERTIME')
    att = Attachment.search([
        ('employee_ids', 'in', slip.employee_id.id),
        ('date_start', '=', slip.date_from),
        ('date_end', '=', slip.date_to),
        ('description', '=like', TAG + '%'),
    ])
    att_h = sum(att.mapped('monthly_amount'))
    hel_in = input_amt('HEL')
    hel_pay = rule_amt('HEL')
    net = rule_amt('NET')
    print('%-24s %8.2f %10.2f %9.2f %12s %12s' % (
        slip.employee_id.name[:24], ot_h, att_h, hel_in,
        '{:,.2f}'.format(hel_pay), '{:,.2f}'.format(net)))

    exp_ot = emp_ot_days[slip.employee_id.id] * 3  # ~3h/dia (solo para el mensaje)
    if exp_ot > 0:
        # Debe haber horas OVERTIME, attachment etiquetado, input y pago HEL
        if not (ot_h > 0 and abs(att_h - ot_h) < 0.01 and abs(hel_in - ot_h) < 0.01 and hel_pay > 0):
            ok = False
            print('     ✗ FALLO: se esperaban ~%d h extra con puente HEL activo' % exp_ot)
    else:
        # Control: sin asistencia extra no debe crearse attachment ni input HEL
        if ot_h > 0 or att_h > 0 or hel_in > 0:
            ok = False
            print('     ✗ FALLO: empleado control no deberia tener horas extra')

# ── Idempotencia: recomputar no debe duplicar el attachment [HE-ASISTENCIA] ──
line()
target = slips.filtered(lambda s: emp_ot_days[s.employee_id.id] > 0)[:1]
if target:
    before = Attachment.search_count([
        ('employee_ids', 'in', target.employee_id.id),
        ('date_start', '=', target.date_from),
        ('date_end', '=', target.date_to),
        ('description', '=like', TAG + '%'),
    ])
    target.compute_sheet()
    after = Attachment.search_count([
        ('employee_ids', 'in', target.employee_id.id),
        ('date_start', '=', target.date_from),
        ('date_end', '=', target.date_to),
        ('description', '=like', TAG + '%'),
    ])
    print('Idempotencia (%s): attachments antes=%d despues=%d %s' % (
        target.employee_id.name, before, after,
        'OK' if before == after == 1 else '✗ FALLO'))
    if not (before == after == 1):
        ok = False

line('#')
if ok:
    print(' OK: horas extra por asistencia -> input HEL -> pago 35%. Commiteando...')
    env.cr.commit()
else:
    print(' ERROR: alguna verificacion fallo. Revisar reglas/parametros.')
    print(' Se commitea igual para poder inspeccionar via web.')
    env.cr.commit()
PYEOF

STATUS=$?
echo
if [[ $STATUS -eq 0 ]]; then
  echo "======================================================"
  echo " DB lista: $DB_NAME"
  echo " URL      : http://localhost:${ODOO_PORT:-8069}"
  echo " Login    : admin / admin"
  echo " Ver: Nómina → Recibos (pestaña Días Trabajados: línea Horas Extra),"
  echo "      Nómina → ... → Retenciones/Embargos [HE-ASISTENCIA],"
  echo "      Asistencias → Config → Reglas de horas extra."
  echo " Re-sembrar sin reinstalar: $0 --db=$DB_NAME --skip-install"
  echo "======================================================"
else
  echo "ERROR: el sembrado fallo (exit $STATUS). DB conservada para inspeccion: $DB_NAME"
fi
exit $STATUS
