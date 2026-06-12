#!/bin/bash
# setup_v19_l10n_do_hr_payroll.sh
#
# Crea y configura una base de datos NUEVA (no de test, sin datos demo) para
# trabajar la nomina dominicana (l10n_do_hr_payroll) en Odoo 19:
#
#   1. Crea la DB v19_l10n_do_hr_payroll e instala l10n_do_hr_payroll
#      (arrastra hr_payroll, hr_payroll_account, l10n_do_hr, l10n_do_banks).
#   2. Configura la compania: pais RD, moneda DOP, tipo de riesgo laboral.
#   3. Configura calendario laboral RD de 44h (L-V 8h + sabado 4h).
#   4. Crea departamentos, AFP y ARS.
#   5. Crea 10 empleados dominicanos con cedula, NSS, contrato vigente
#      (hr.version), salarios variados que cubren los tramos de ISR.
#   6. Sanity check: genera un lote de nomina del mes anterior, calcula las 10
#      nominas e imprime BASIC / AFP / SFS / ISR / NET por empleado.
#
# Los datos se COMMITEAN (la DB queda lista para usar via web).
#
# Uso:
#   ./setup_v19_l10n_do_hr_payroll.sh                  # crea DB nueva
#   ./setup_v19_l10n_do_hr_payroll.sh --db=mi_db       # nombre personalizado
#   ./setup_v19_l10n_do_hr_payroll.sh --recreate       # borra y recrea si existe
#   ./setup_v19_l10n_do_hr_payroll.sh --skip-install   # DB ya instalada, solo siembra
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="l10n_do_hr_payroll"

DB_NAME="v19_l10n_do_hr_payroll"
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
echo " Setup nomina dominicana — $MODULE"
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

echo "→ Configurando compania, calendario y empleados..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
from datetime import date

import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

today = date.today()
# Mes anterior completo para el lote de nomina
period_end = today.replace(day=1) - __import__('datetime').timedelta(days=1)
period_start = period_end.replace(day=1)

# ════════════════════════════════════════════════════════════════════════════
# 1. COMPANIA: pais RD, moneda DOP, riesgo laboral
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
}
company.write(vals)
try:
    company.currency_id = dop.id
    print('Compania: %s | pais=%s moneda=%s riesgo=%s' % (
        company.name, company.country_id.code, company.currency_id.name,
        company.l10n_do_occupational_risk_type_id.name))
except Exception as e:
    env.cr.rollback()
    company.write(vals)
    print('AVISO: no se pudo cambiar la moneda a DOP (%s). Resto de config aplicada.' % e)

# RNC (sin validacion de checksum para no romper si base_vat esta activo)
try:
    company.partner_id.with_context(no_vat_validation=True).vat = '131-79391-6'
except Exception:
    pass

# ════════════════════════════════════════════════════════════════════════════
# 2. CALENDARIO LABORAL RD 44h: L-V 8h (8-12 / 13-17) + sabado 4h (8-12)
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
    'attendance_ids': attendances,
})
company.resource_calendar_id = calendar_rd
print('Calendario: %s (%.0fh/semana)' % (calendar_rd.name, calendar_rd.full_time_required_hours or 44))

# ════════════════════════════════════════════════════════════════════════════
# 3. TIPO DE ESTRUCTURA / ESTRUCTURA BASE DEL MODULO
# ════════════════════════════════════════════════════════════════════════════
structure_type = env.ref('l10n_do_hr_payroll.structure_type_employee')
structure_type.write({
    'default_resource_calendar_id': calendar_rd.id,
    'default_schedule_pay': 'monthly',
})
struct_base = env.ref('l10n_do_hr_payroll.hr_payroll_structure_base')

# Salary Journal: hr.payslip.journal_id es related readonly a struct_id.journal_id;
# la estructura del modulo se carga sin journal (el default solo aplica a las
# estructuras estandar). Sin esto el payslip no se puede guardar/contabilizar.
salary_journal = env['account.journal'].search(
    [('code', '=', 'SLR'), ('company_id', '=', company.id)], limit=1)
if not salary_journal:
    salary_journal = env['account.journal'].create({
        'name': 'Nómina', 'code': 'NOM', 'type': 'general', 'company_id': company.id})
for struct in env['hr.payroll.structure'].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal
print('Estructura: %s (tipo: %s, %d reglas, diario: %s)' % (
    struct_base.name, structure_type.name, len(struct_base.rule_ids),
    struct_base.journal_id.name))

# ════════════════════════════════════════════════════════════════════════════
# 4. DEPARTAMENTOS, AFP, ARS
# ════════════════════════════════════════════════════════════════════════════
Dept = env['hr.department']
departments = {
    'admin': Dept.create({'name': 'Administración'}),
    'ventas': Dept.create({'name': 'Ventas'}),
    'ops': Dept.create({'name': 'Operaciones'}),
}
Partner = env['res.partner']
afp = Partner.create({'name': 'AFP Popular', 'is_company': True, 'country_id': do.id})
ars = Partner.create({'name': 'ARS Universal', 'is_company': True, 'country_id': do.id})
print('Departamentos: %s | AFP: %s | ARS: %s' % (
    ', '.join(d.name for d in departments.values()), afp.name, ars.name))

# ════════════════════════════════════════════════════════════════════════════
# 5. 10 EMPLEADOS con contrato vigente (hr.version)
#    Salarios cubren tramos ISR 2026: exento (<34,685/mes), 15%, 20%, 25%
# ════════════════════════════════════════════════════════════════════════════
contract_start = date(today.year - 1, 1, 1)
EMPLOYEES = [
    # nombre, cedula, NSS, sexo, nacimiento, depto, salario
    ('Juan Pérez Rodríguez',     '00112345678', '10001', 'male',   '1988-03-15', 'admin',  18000),
    ('María Gómez Santana',      '00223456789', '10002', 'female', '1992-07-22', 'admin',  22000),
    ('Pedro Martínez Cruz',      '00334567890', '10003', 'male',   '1985-11-08', 'ops',    28000),
    ('Ana Rodríguez Féliz',      '00445678901', '10004', 'female', '1990-01-30', 'ventas', 33000),
    ('Luis Fernández Castillo',  '00556789012', '10005', 'male',   '1983-05-12', 'ops',    38000),
    ('Carmen Díaz Polanco',      '00667890123', '10006', 'female', '1995-09-18', 'ventas', 45000),
    ('José Ramírez Guzmán',      '00778901234', '10007', 'male',   '1987-12-03', 'ops',    60000),
    ('Rosa Sánchez Medina',      '00889012345', '10008', 'female', '1991-04-25', 'admin',  85000),
    ('Miguel Torres Vargas',     '00990123456', '10009', 'male',   '1980-08-14', 'ventas', 120000),
    ('Laura Jiménez Reyes',      '00101234567', '10010', 'female', '1986-02-09', 'admin',  175000),
]

Employee = env['hr.employee']
employees = env['hr.employee']
for name, cedula, nss, gender, birthday, dept, wage in EMPLOYEES:
    emp = Employee.create({
        'name': name,
        'company_id': company.id,
        'country_id': do.id,
        'identification_id': cedula,
        'l10n_do_social_security_number': nss,
        'l10n_do_has_papers': True,
        'l10n_do_afp_partner_id': afp.id,
        'l10n_do_ars_partner_id': ars.id,
        'sex': gender,
        'birthday': birthday,
        'department_id': departments[dept].id,
        'resource_calendar_id': calendar_rd.id,
        # campos de contrato (en v19 hr.contract vive en hr.version,
        # el empleado genera su version_id con estos campos)
        'date_version': contract_start,
        'contract_date_start': contract_start,
        'wage': wage,
        'structure_type_id': structure_type.id,
    })
    emp.version_id.write({'l10n_do_schedule_retentions': 'end_of_month'})
    employees |= emp
    print('  + %-28s ced=%s NSS=%s %s RD$%s' % (
        name, cedula, nss, departments[dept].name, '{:,.0f}'.format(wage)))
print('Empleados creados: %d' % len(employees))

# ════════════════════════════════════════════════════════════════════════════
# 6. SANITY CHECK: lote de nomina del mes anterior, calcular las 10 nominas
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
    slips |= env['hr.payslip'].create({
        'name': 'Nómina %s' % emp.name,
        'employee_id': emp.id,
        'struct_id': struct_base.id,
        'date_from': period_start,
        'date_to': period_end,
        'payslip_run_id': run.id,
    })
slips.compute_sheet()

# Codigos del modulo: SVDSE = AFP empleado, SFSE = SFS empleado
print('%-28s %12s %10s %10s %10s %12s' % ('Empleado', 'BASIC', 'AFP', 'SFS', 'ISR', 'NET'))
line()
ok = True
for slip in slips:
    def amt(code):
        l = slip.line_ids.filtered(lambda r: r.code == code)
        return sum(l.mapped('total'))
    basic, net = amt('BASIC'), amt('NET')
    print('%-28s %12s %10s %10s %10s %12s' % (
        slip.employee_id.name[:28],
        '{:,.2f}'.format(basic), '{:,.2f}'.format(amt('SVDSE')),
        '{:,.2f}'.format(amt('SFSE')), '{:,.2f}'.format(amt('ISR')),
        '{:,.2f}'.format(net)))
    if not basic or not net:
        ok = False

line('#')
if ok:
    print(' OK: las 10 nominas calcularon BASIC y NET. Commiteando datos...')
    env.cr.commit()
else:
    print(' ERROR: alguna nomina calculo en 0. Revisar reglas/parametros.')
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
  echo " Re-sembrar sin reinstalar: $0 --db=$DB_NAME --skip-install"
  echo "======================================================"
else
  echo "ERROR: el sembrado fallo (exit $STATUS). DB conservada para inspeccion: $DB_NAME"
fi
exit $STATUS
