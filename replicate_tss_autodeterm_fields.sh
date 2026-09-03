#!/bin/bash
# replicate_tss_autodeterm_fields.sh
#
# Reproduce los 3 hallazgos reportados sobre el TXT de Autodeterminacion
# Mensual (AM) de la TSS generado por `tss_report` en Odoo 19:
#
#   1. Las vacaciones de ley no se suman al campo "Otras Remuneraciones"
#      (pos. 218-233), aunque si entran en Salario_SS (pos. 170-185).
#   2. "Salario cotizable INFOTEP" (pos. 293-308) queda en Salario_SS - 1.00
#      en vez de excluir las vacaciones.
#   3. "Salario cotizable INFOTEP" se reporta con monto aun cuando es igual a
#      Salario_SS; el layout v6 pag. 22 exige cero en ese caso.
#
# Material de referencia: docs/tss_file/
#   02_Nomina_Simulada_TSS.xlsx  (nomina ficticia + comparativo)
#   03_AM_999999999_072026_EJEMPLO_ODOO.txt   (comportamiento actual)
#   04_AM_999999999_072026_ESPERADO_TSS.txt   (comportamiento esperado)
#
# Uso:
#   ./replicate_tss_autodeterm_fields.sh              # crea DB e instala
#   ./replicate_tss_autodeterm_fields.sh --skip-install  # solo re-siembra
#   ./replicate_tss_autodeterm_fields.sh --recreate
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="tss_report"

DB_NAME="v19_tss_autodeterm"
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
echo " Replicacion hallazgos TXT Autodeterminacion TSS"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo "======================================================"

db_exists() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" \
    | grep -q 1
}

if ! $SKIP_INSTALL; then
  if db_exists; then
    if $RECREATE; then
      echo "→ DB $DB_NAME existe, eliminando (--recreate)..."
      docker exec "$CONTAINER" bash -lc "
        PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
          \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid()\" >/dev/null
        PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
      " || { echo 'ERROR eliminando la DB' >&2; exit 1; }
    else
      echo "ERROR: la DB $DB_NAME ya existe. Usa --recreate o --skip-install." >&2
      exit 1
    fi
  fi

  echo "→ Creando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULE sin datos demo (varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --stop-after-init --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
fi

echo "→ Sembrando nomina simulada y generando el TXT..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import base64
import logging
from datetime import date

logging.disable(logging.WARNING)

def line(c='-', n=110): print(c * n)

PERIOD_START = date(2026, 7, 1)
PERIOD_END = date(2026, 7, 31)

company = env.ref('base.main_company')
do = env.ref('base.do')
dop = env.ref('base.DOP')
dop.active = True
company.write({
    'name': 'Empresa Simulada TSS SRL',
    'country_id': do.id,
    'city': 'Santo Domingo',
    'l10n_do_occupational_risk_type_id': env.ref('l10n_do_hr_payroll.risk_type_1').id,
})
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
# RNC 999999999 -> el encabezado del TXT queda "EAM  999999999072026"
company.partner_id.with_context(no_vat_validation=True).vat = '999999999'

# ── Calendario RD 44h ──────────────────────────────────────────────────────
attendances = []
for dow in range(5):
    attendances.append((0, 0, {'name': 'Mañana', 'dayofweek': str(dow),
                               'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}))
    attendances.append((0, 0, {'name': 'Tarde', 'dayofweek': str(dow),
                               'hour_from': 13, 'hour_to': 17, 'day_period': 'afternoon'}))
attendances.append((0, 0, {'name': 'Sabado', 'dayofweek': '5',
                           'hour_from': 8, 'hour_to': 12, 'day_period': 'morning'}))
calendar_rd = env['resource.calendar'].create({
    'name': 'Jornada RD 44 horas', 'company_id': company.id,
    'hours_per_day': 8, 'attendance_ids': attendances,
})
company.resource_calendar_id = calendar_rd

structure_type = env.ref('l10n_do_hr_payroll.structure_type_employee')
structure_type.write({'default_resource_calendar_id': calendar_rd.id,
                      'default_schedule_pay': 'monthly'})
struct_base = env.ref('l10n_do_hr_payroll.hr_payroll_structure_base')
salary_journal = env['account.journal'].search(
    [('type', '=', 'general'), ('company_id', '=', company.id)], limit=1)
if not salary_journal:
    salary_journal = env['account.journal'].create(
        {'name': 'Nómina', 'code': 'NOM', 'type': 'general', 'company_id': company.id})
for struct in env['hr.payroll.structure'].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal

# Las entradas manuales se borran en compute cuando el tipo esta marcado como
# "available_in_attachments" (bug conocido A de salary-inputs-not-computing).
# Para esta replicacion las desmarcamos: el objeto de prueba son los campos del
# TXT, no la captura de entradas.
INPUT_CODES = ['VAC', 'INC', 'REPA']
input_types = env['hr.payslip.input.type'].search([('code', 'in', INPUT_CODES)])
input_types.write({'available_in_attachments': False})
IT = {it.code: it for it in input_types}

payroll_key = env.ref('l10n_do_hr_report_base.l10n_do_payroll_key_001')
afp = env['res.partner'].create({'name': 'AFP Simulada', 'is_company': True, 'country_id': do.id})
ars = env['res.partner'].create({'name': 'ARS Simulada', 'is_company': True, 'country_id': do.id})

# ── 5 empleados de la nomina simulada (docs/tss_file/02_Nomina_Simulada_TSS.xlsx)
#    nombre, apellido, cedula, sexo, nacimiento, salario, inputs, caso
EMPLOYEES = [
    ('Laura',   'Mendez',   '99900000001', 'female', date(1995, 3, 12), 49250.0, {},
     'Sin vacaciones. Salario_SS == INFOTEP -> INFOTEP debe ir en 0'),
    ('Mateo',   'Vargas',   '99900000002', 'male',   date(1992, 7, 23), 52000.0, {'VAC': 1.0},
     'Vacaciones sin otras remuneraciones'),
    ('Camila',  'Reyes',    '99900000003', 'female', date(1990, 11, 4), 80000.0, {'VAC': 1.0, 'INC': 20000.0},
     'Vacaciones + incentivo'),
    ('Diego',   'Castillo', '99900000004', 'male',   date(1997, 5, 16), 60000.0, {'INC': 10000.0},
     'Incentivo sin vacaciones'),
    ('Valeria', 'Santos',   '99900000005', 'female', date(1994, 8, 29), 30000.0, {'REPA': 6500.0},
     'Regalia pascual (codigo 01)'),
]

contract_start = date(2024, 1, 1)
Employee = env['hr.employee']
employees = env['hr.employee']
emp_inputs = {}
for first, last, cedula, sex, birthday, wage, inputs, case in EMPLOYEES:
    emp = Employee.create({
        'name': '%s %s' % (first, last),
        'first_name': first,
        'first_last_name': last,
        'company_id': company.id,
        'country_id': do.id,
        'identification_id': cedula,
        'l10n_do_has_papers': True,
        'l10n_do_afp_partner_id': afp.id,
        'l10n_do_ars_partner_id': ars.id,
        'sex': sex,
        'birthday': birthday,
        'resource_calendar_id': calendar_rd.id,
        'date_version': contract_start,
        'contract_date_start': contract_start,
        'wage': wage,
        'structure_type_id': structure_type.id,
    })
    emp.version_id.write({
        'l10n_do_schedule_retentions': 'end_of_month',
        'l10n_do_payroll_key_id': payroll_key.id,
        'l10n_do_income_type': '0001',
    })
    employees |= emp
    emp_inputs[emp.id] = inputs

# ── Lote 07/2026 ───────────────────────────────────────────────────────────
run = env['hr.payslip.run'].create({
    'name': 'Nómina Julio 2026',
    'date_start': PERIOD_START,
    'date_end': PERIOD_END,
})
slips = env['hr.payslip']
for emp in employees:
    slip = env['hr.payslip'].create({
        'name': 'Nómina %s' % emp.name,
        'employee_id': emp.id,
        'struct_id': struct_base.id,
        'date_from': PERIOD_START,
        'date_to': PERIOD_END,
        'payslip_run_id': run.id,
    })
    for code, amount in emp_inputs[emp.id].items():
        env['hr.payslip.input'].create({
            'payslip_id': slip.id,
            'input_type_id': IT[code].id,
            'amount': amount,
        })
    slips |= slip

slips.compute_sheet()

# ── Lineas relevantes por empleado ─────────────────────────────────────────
line('=')
print(' Lineas de nomina 07/2026')
line('=')
CODES = ['BASE', 'APAGAR', 'VAC', 'INC', 'REPA', 'SALTSS', 'COTINF']
print('%-18s' % 'Empleado' + ''.join('%12s' % c for c in CODES))
line()
for slip in slips:
    def amt(code, s=slip):
        return sum(s.line_ids.filtered(lambda r: r.code == code).mapped('total'))
    print('%-18s' % slip.employee_id.name[:18] + ''.join('%12s' % '{:,.2f}'.format(amt(c)) for c in CODES))

# ── Valores que el builder lleva al TXT ────────────────────────────────────
builder = env['tss.report.wizard'].create({'payslip_run_ids': [(6, 0, [run.id])]})
line('=')
print(' Valores calculados por el builder (l10n.do.tss.txt.builder)')
line('=')
print('%-18s %14s %14s %14s %14s' % ('Empleado', 'Salario_SS', 'Salario_ISR', 'Otras_Remun', 'INFOTEP'))
line()
for slip in slips:
    print('%-18s %14s %14s %14s %14s' % (
        slip.employee_id.name[:18],
        builder._get_period_salary(slip),
        builder._get_period_isr_salary(slip),
        builder._get_period_remuneration(slip),
        builder._get_infotep_salary(slip),
    ))

# ── TXT generado ───────────────────────────────────────────────────────────
filename, content = builder._tss_build()
txt = base64.b64decode(content).decode('utf-8')
line('=')
print(' TXT generado: %s' % filename)
line('=')
for row in txt.replace('\r\n', '\n').split('\n'):
    print(repr(row))

# ── Recorte de los campos numericos por posicion (layout v6) ───────────────
FIELDS = [
    ('Salario_SS',   170, 185),
    ('Aporte_vol',   186, 201),
    ('Salario_ISR',  202, 217),
    ('Otras_Remun',  218, 233),
    ('Ingr_exento',  261, 276),
    ('INFOTEP',      293, 308),
    ('Tipo_ingreso', 309, 312),
]
line('=')
print(' Campos por posicion del TXT generado')
line('=')
print('%-10s' % 'Empleado' + ''.join('%16s' % f[0] for f in FIELDS))
line()
rows = [r for r in txt.replace('\r\n', '\n').split('\n') if r.startswith('D')]
BY_DOC = {e[2]: e[0] for e in EMPLOYEES}
for row in rows:
    name = BY_DOC.get(row[5:30].strip(), '?')
    print('%-10s' % name + ''.join('%16s' % row[f[1] - 1:f[2]].lstrip('0') for f in FIELDS))

env.cr.rollback()
print()
print('Replicacion completada (rollback: la DB queda sin la nomina simulada).')
print('Para conservarla, cambiar el rollback final por env.cr.commit().')
PYEOF

STATUS=$?
echo
[[ $STATUS -eq 0 ]] || echo "ERROR: la replicacion fallo (exit $STATUS)."
exit $STATUS
