#!/bin/bash
# replicate_salary_inputs_not_computing.sh
#
# Reproduce el reporte "No computan las entradas salariales" del modulo
# l10n_do_hr_payroll en Odoo 19.
#
# Causa investigada:
#   - En v19 los 43 input types del modulo se migraron con
#     available_in_attachments="True" (en 17.0 NINGUNO lo tenia).
#   - El override de hr.payslip._compute_input_line_ids
#     (l10n_do_hr_payroll/models/l10n_do_hr_salary_attachment.py:121) elimina
#     TODAS las lineas de input cuyo tipo este en
#     search([("available_in_attachments","=",True)]) y las recrea SOLO desde
#     salary_attachment_ids.
#   - El override de compute_sheet (mismo archivo, linea ~165) FUERZA
#     self._compute_input_line_ids() en cada calculo.
#   => Una entrada salarial capturada manualmente en la nomina (COMV, INC,
#      HEL, etc.) que NO tenga un salary.attachment de respaldo es borrada al
#      calcular, por lo que las reglas salariales que la leen (inputs['CODE'])
#      no computan.
#
# Este script:
#   1. Crea una DB limpia e instala l10n_do_hr_payroll.
#   2. Siembra empleado + contrato + nomina con la estructura base y las reglas
#      basica/base/comisiones (igual que el test test_hr_rule_commissions).
#   3. Agrega manualmente el input COMV=5000, calcula y comprueba si sobrevive.
#   4. Prueba la hipotesis del fix: pone available_in_attachments=False en el
#      tipo COMV, recalcula y comprueba que ahora si computa.
#
# Uso:
#   ./replicate_salary_inputs_not_computing.sh                 # crea DB, instala, reproduce
#   ./replicate_salary_inputs_not_computing.sh --keep          # no borra la DB al terminar
#   ./replicate_salary_inputs_not_computing.sh --db=mi_db      # nombre de DB personalizado
#   ./replicate_salary_inputs_not_computing.sh --skip-install  # DB ya instalada, solo reproduce
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

DB_NAME="test_salary_inputs_repro"
KEEP_DB=false
SKIP_INSTALL=false
for arg in "$@"; do
  case "$arg" in
    --keep)         KEEP_DB=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    --db=*)         DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Repro: 'No computan las entradas salariales' — $MODULE"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo "======================================================"

# ── Helper: espera a que Postgres responda (Docker Desktop macOS agota puertos) ──
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

if ! $SKIP_INSTALL; then
  echo "→ Esperando a Postgres..."
  wait_for_db || exit 1

  echo "→ Recreando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS dropdb   -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME
    PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
  " || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULE (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --stop-after-init --without-demo=False \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
fi

echo "→ Sembrando datos y reproduciendo el comportamiento..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 2>/dev/null
" <<'PYEOF'
from datetime import date

def line(c='-'): print(c * 60)

# ── 1. Estructura salarial: copia de la base con SOLO la regla de comisiones
#       (COM solo lee inputs['COMV'], no depende de parametros TSS/ISR ni de
#       otras reglas). ─────────────────────────────────────────────────────────
structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
base_struct = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
struct = base_struct.copy({"rule_ids": False})
struct.write({"rule_ids": [
    (4, env.ref("l10n_do_hr_payroll.hr_rule_commissions").id),
]})

# ── 2. Empleado (en v19 hr.contract se fusiono en hr.version; el empleado
#       auto-genera su version_id a partir de estos campos). ───────────────────
employee = env["hr.employee"].create({
    "name": "Empleado Repro Inputs",
    "country_id": env.ref("base.do").id,
    "identification_id": "99999999",
    "date_version": date(2020, 1, 1),
    "contract_date_start": date(2020, 1, 1),
    "contract_date_end": date(2020, 12, 31),
    "wage": 6000.0,
    "structure_type_id": structure_type.id,
})

input_type_comv = env.ref("l10n_do_hr_payroll.hr_payslip_input_type_comisiones_venta")  # code COMV

def build_payslip():
    slip = env["hr.payslip"].create({
        "name": "Nomina Repro",
        "employee_id": employee.id,
        "struct_id": struct.id,
        "date_from": date(2020, 2, 1),
        "date_to": date(2020, 2, 29),
    })
    env["hr.payslip.input"].create({
        "payslip_id": slip.id,
        "input_type_id": input_type_comv.id,
        "amount": 5000,
    })
    return slip

def report(slip, titulo):
    line('=')
    print(' ' + titulo)
    line('=')
    inputs_comv = slip.input_line_ids.filtered(lambda i: i.code == "COMV")
    com_line = slip.line_ids.filtered(lambda l: l.code == "COM")
    print(" input COMV en input_line_ids : %s (amount=%s)" % (
        bool(inputs_comv), inputs_comv.mapped("amount")))
    print(" linea regla COM              : %s (amount=%s)" % (
        bool(com_line), com_line.mapped("amount")))
    return bool(inputs_comv), com_line.amount if com_line else 0.0

# ── 3. ESCENARIO BUG: COMV con available_in_attachments=True (estado actual) ──
print("\n>>> available_in_attachments del tipo COMV =", input_type_comv.available_in_attachments)
slip = build_payslip()
print("\n[Antes de compute_sheet] input_line_ids COMV =",
      bool(slip.input_line_ids.filtered(lambda i: i.code == "COMV")),
      slip.input_line_ids.filtered(lambda i: i.code == "COMV").mapped("amount"))
slip.compute_sheet()
bug_input, bug_com = report(slip, "ESCENARIO ACTUAL (available_in_attachments=True)")

# ── 4. ESCENARIO FIX: poner available_in_attachments=False y recalcular ───────
input_type_comv.available_in_attachments = False
slip2 = build_payslip()
slip2.compute_sheet()
fix_input, fix_com = report(slip2, "HIPOTESIS DE FIX (available_in_attachments=False)")

# ── 5. Veredicto ─────────────────────────────────────────────────────────────
env.cr.rollback()  # no persistir cambios de prueba
line('#')
print(" VEREDICTO")
line('#')
reproduced = (not bug_input) and bug_com == 0.0
fixed = fix_input and fix_com == 5000.0
print(" Bug reproducido (input borrado, COM=0)     : %s" % reproduced)
print(" Fix valida (input sobrevive, COM=5000)     : %s" % fixed)
if reproduced and fixed:
    print("\n >>> CONFIRMADO: available_in_attachments=True borra las entradas")
    print("     salariales manuales al calcular; con False computan correctamente.")
elif not reproduced:
    print("\n >>> NO reproducido: la entrada COMV sobrevivio con el estado actual.")
    print("     Revisar otra causa.")
PYEOF

STATUS=$?

if ! $KEEP_DB && ! $SKIP_INSTALL; then
  echo "→ Eliminando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME" || true
else
  echo "→ DB conservada: $DB_NAME (usa --skip-install para re-ejecutar sin reinstalar)"
fi

exit $STATUS
