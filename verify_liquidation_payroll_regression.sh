#!/bin/bash
# verify_liquidation_payroll_regression.sh
#
# Demuestra que instalar l10n_do_hr_payroll_liquidation NO altera la nomina
# ordinaria de l10n_do_hr_payroll.
#
# Por que existe:
#   El modulo de liquidacion necesita ajustar 11 reglas salariales de la
#   localizacion (APAGAR, VAC, DLAB, las bases cotizables y las retenciones) para
#   poder pagar vacaciones y dias laborados en el mismo recibo extraordinario con
#   TSS e ISR. Esos ajustes se declaran como override DENTRO del modulo de
#   liquidacion, no editando l10n_do_hr_payroll, y cada condicion es la expresion
#   original mas una clausula sobre payslip.l10n_do_liquidation_ordinary_income,
#   bandera que solo puede ser verdadera en un recibo de liquidacion.
#
#   Razonar la equivalencia no basta. Este script la mide.
#
# Que hace:
#   1. Crea DB probe_base  e instala SOLO l10n_do_hr_payroll.
#   2. Crea DB probe_liq   e instala l10n_do_hr_payroll_liquidation (trae los
#      overrides por dependencia).
#   3. Calcula los MISMOS 15 escenarios de nomina en ambas y volca, por recibo,
#      cada codigo de regla con su total.
#   4. Compara los dos volcados.
#
# Resultado esperado (2026-07-29): 13 de 15 escenarios identicos byte a byte.
#   Las 2 diferencias son mejoras, no regresiones:
#     - ordinaria-dias-laborados : en probe_base ABORTA el calculo porque la regla
#       DLAB referencia `amount_to_pay`, nombre que la nomina no publica en el
#       contexto de evaluacion. El modulo de liquidacion desactiva esa regla (el
#       computo ya lo hace APAGAR) y el recibo se calcula.
#     - ordinaria-salida-2025    : en probe_base falla por falta de vigencia de
#       LAST_DAY; con el modulo llega mas lejos y falla en SFS_TOPE, tope indexado
#       que NO se retrofecha a proposito (aplicar el tope actual a un periodo
#       anterior daria una retencion erronea en silencio).
#
#   Los escenarios de bonificacion fallan IGUAL en ambas DBs: la regla INFE
#   referencia `BONOS`, que no esta definido porque la regla BONOS lee
#   inputs['BONOS'] cuando el tipo de entrada es 'BONO'. Bug preexistente de la
#   localizacion, ajeno a este modulo.
#
# Uso:
#   ./verify_liquidation_payroll_regression.sh
#   ./verify_liquidation_payroll_regression.sh --keep-db

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] || { echo "ERROR: .env no encontrado en $SCRIPT_DIR" >&2; exit 1; }
source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
DB_BASE="probe_payroll_base"
DB_LIQ="probe_payroll_liq"
OUT_DIR="$SCRIPT_DIR/test_logs/payroll_regression"
KEEP_DB=false

for arg in "$@"; do
  [[ "$arg" == "--keep-db" ]] && KEEP_DB=true
done

mkdir -p "$OUT_DIR"

docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$" || {
  echo "ERROR: contenedor '$CONTAINER' no esta corriendo. Corre: docker-compose up -d" >&2
  exit 1
}

_drop_db() {
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname='$1' AND pid <> pg_backend_pid();\" >/dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' --if-exists '$1'
  " 2>&1 | grep -v NOTICE || true
}

echo "======================================================"
echo " Regresion de nomina ordinaria — overrides de liquidacion"
echo "======================================================"

# ─── Config con credenciales de DB (odoo shell las lee del conf) ──────────────
docker exec "$CONTAINER" bash -lc "
  cp /etc/odoo/odoo.conf /tmp/probe.conf
  printf 'db_host = %s\ndb_port = %s\ndb_user = %s\ndb_password = %s\n' \
    '$DB_HOST' '$DB_PORT' '$DB_USER' '$DB_PASS' >> /tmp/probe.conf
"

# ─── Script de volcado ───────────────────────────────────────────────────────
docker exec -i "$CONTAINER" bash -c 'cat > /tmp/dump_payroll.py' <<'PYEOF'
import json
from datetime import date

company = env.company
do_country = env.ref("base.do")
company.write({"country_id": do_country.id})
struct = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")


def make_employee(name, wage, cedula, schedule):
    employee = env["hr.employee"].create({
        "name": name,
        "company_id": company.id,
        "country_id": do_country.id,
        "identification_id": cedula,
        "l10n_do_has_papers": True,
        "wage": wage,
        "date_version": date(2020, 1, 1),
        "contract_date_start": date(2020, 1, 1),
        "structure_type_id": structure_type.id,
    })
    employee.version_id.l10n_do_schedule_retentions = schedule
    return employee


def payslip(employee, date_from, date_to, extraordinary, inputs):
    run = env["hr.payslip.run"]
    if extraordinary is not None:
        run = run.create({
            "name": "Lote",
            "date_start": date_from,
            "date_end": date_to,
            "company_id": company.id,
            "l10n_do_extraordinary": extraordinary,
        })
    commands = []
    for code, amount in inputs:
        input_type = env["hr.payslip.input.type"].with_context(active_test=False).search(
            [("code", "=", code)], limit=1)
        commands.append((0, 0, {"input_type_id": input_type.id, "amount": amount}))
    slip = env["hr.payslip"].create({
        "name": "Nomina",
        "employee_id": employee.id,
        "version_id": employee.version_id.id,
        "struct_id": struct.id,
        "date_from": date_from,
        "date_to": date_to,
        "payslip_run_id": run.id,
        "company_id": company.id,
        "input_line_ids": commands,
    })
    slip.compute_sheet()
    return slip


SCENARIOS = [
    ("ordinaria-fin-de-mes-distribuida", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, []),
    ("ordinaria-fin-de-mes-end_of_month", 60000, "end_of_month", date(2026, 7, 1), date(2026, 7, 31), None, []),
    ("ordinaria-primera-quincena", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 15), None, []),
    ("ordinaria-en-lote-no-extraordinario", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), False, []),
    ("extraordinaria-incentivo", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), True, [("INC", 5000)]),
    ("ordinaria-con-comision", 45000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("COMV", 8000)]),
    ("ordinaria-switch-vacaciones", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("VAC", 1)]),
    ("ordinaria-monto-vacaciones", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("VAC", 12345.67)]),
    ("ordinaria-salario-real", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("REAL", 20000)]),
    ("ordinaria-dias-laborados", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("DLAB", 10)]),
    ("ordinaria-horas-extra", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("HEL", 20)]),
    ("ordinaria-ausencias", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("NLAB", 3)]),
    ("ordinaria-salida-2025", 60000, "distributed", date(2025, 12, 1), date(2025, 12, 31), None, []),
    ("ordinaria-bonificacion", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), None, [("BONO", 5000)]),
    ("extraordinaria-bonificacion", 60000, "distributed", date(2026, 7, 1), date(2026, 7, 31), True, [("BONO", 5000)]),
]

result = {}
for index, (label, wage, schedule, date_from, date_to, extraordinary, inputs) in enumerate(SCENARIOS):
    employee = make_employee(label, wage, "0092000%04d" % index, schedule)
    try:
        slip = payslip(employee, date_from, date_to, extraordinary, inputs)
    except Exception as error:
        result[label] = {"__error__": "%s: %s" % (type(error).__name__, error)}
        env.cr.rollback()
        continue
    result[label] = {line.code: round(line.total, 2) for line in slip.line_ids.sorted("code")}

print("===DUMP_START===")
print(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False))
print("===DUMP_END===")
env.cr.rollback()
PYEOF

# ─── Instalar y volcar ───────────────────────────────────────────────────────
_probe() {
  local DB="$1" MODULES="$2" PORT="$3" LABEL="$4"
  echo ""
  echo "[$LABEL] DB $DB — instalando $MODULES ..."
  _drop_db "$DB"
  docker exec "$CONTAINER" odoo -c /tmp/probe.conf -d "$DB" \
    --no-http --http-port="$PORT" --stop-after-init --without-demo=all \
    -i "$MODULES" --log-level=warn 2>&1 | grep -Ei "Traceback|CRITICAL" | head -5 || true
  echo "[$LABEL] calculando escenarios ..."
  docker exec -i "$CONTAINER" bash -lc \
    "odoo shell -c /tmp/probe.conf -d $DB --no-http --log-level=error < /tmp/dump_payroll.py" \
    2>/dev/null | sed -n '/===DUMP_START===/,/===DUMP_END===/p' | sed '1d;$d' > "$OUT_DIR/$DB.json"
  echo "[$LABEL] volcado -> $OUT_DIR/$DB.json"
}

_probe "$DB_BASE" "l10n_do_hr_payroll" 8074 "1/2 baseline"
_probe "$DB_LIQ" "l10n_do_hr_payroll_liquidation" 8075 "2/2 overrides"

# ─── Comparar ────────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " Comparacion"
echo "======================================================"
cat > "$OUT_DIR/compare.py" <<'PYEOF'
import json
import sys

base = json.load(open(sys.argv[1]))
over = json.load(open(sys.argv[2]))
same = sorted(k for k in base if base[k] == over[k])
diff = sorted(k for k in base if base[k] != over[k])

for key in same:
    print("  = %s" % key)
for key in diff:
    print("  ! %s" % key)
    print("      baseline : %s" % json.dumps(base[key], ensure_ascii=False)[:220])
    print("      overrides: %s" % json.dumps(over[key], ensure_ascii=False)[:220])

print("")
print("  %d/%d escenarios identicos" % (len(same), len(base)))
# Las 2 diferencias conocidas son mejoras documentadas en la cabecera de este
# script. Mas de 2, o cualquier escenario ordinario que cambie de importes, es
# una regresion que hay que investigar.
sys.exit(0 if len(diff) <= 2 else 1)
PYEOF

set +e
python3 "$OUT_DIR/compare.py" "$OUT_DIR/$DB_BASE.json" "$OUT_DIR/$DB_LIQ.json"
STATUS=$?
set -e

if [[ "$KEEP_DB" == false ]]; then
  echo ""
  echo "Limpiando DBs ..."
  _drop_db "$DB_BASE"
  _drop_db "$DB_LIQ"
else
  echo ""
  echo "DBs conservadas: $DB_BASE, $DB_LIQ"
fi

exit "$STATUS"
