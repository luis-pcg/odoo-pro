#!/bin/bash
# verify_input_type_country_payroll.sh
#
# Demuestra que el fix de l10n_do_hr_payroll 19.0.1.1.0 (country_id en los input
# types + migrations/19.0.1.1.0/pre-migrate.py) NO altera las reglas de nomina.
#
# Reutiliza el volcado de 15 escenarios de verify_liquidation_payroll_regression.sh:
# por cada recibo, cada codigo de regla con su total.
#
#   1. DB probe_itc_payroll instalada con el codigo ANTERIOR (data sin country_id)
#      -> volcado "antes".
#   2. La misma DB actualizada con el codigo de la rama -> volcado "despues".
#   3. Comparacion. Cualquier diferencia de importes es una regresion.
#   4. Si existe la DB verify_itc_s2 (la foto de TISSAGE ya migrada: duplicados,
#      xmlid reapuntados, huerfanos borrados), tambien se volca y se compara contra
#      el "despues" para probar que una instancia rescatada calcula igual.
#
# Uso:
#   ./verify_input_type_country_payroll.sh
#   ./verify_input_type_country_payroll.sh --keep
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

REPO="$SCRIPT_DIR/odoo-pro"
DATA_FILE="$REPO/l10n_do_hr_payroll/data/hr_payslip_input_type.xml"
MANIFEST="$REPO/l10n_do_hr_payroll/__manifest__.py"
DB="probe_itc_payroll"
DB_RESCUED="verify_itc_s2"
OUT_DIR="$SCRIPT_DIR/test_logs/input_type_country"
KEEP=false
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done
mkdir -p "$OUT_DIR"

BACKUP_DIR="$(mktemp -d)"
cp "$DATA_FILE" "$BACKUP_DIR/data.xml"
cp "$MANIFEST" "$BACKUP_DIR/manifest.py"
restore_new_code() { cp "$BACKUP_DIR/data.xml" "$DATA_FILE"; cp "$BACKUP_DIR/manifest.py" "$MANIFEST"; }
trap restore_new_code EXIT
use_old_code() {
  git -C "$REPO" show origin/19.0:l10n_do_hr_payroll/data/hr_payslip_input_type.xml > "$DATA_FILE"
  sed -i '' 's/"version": "[^"]*"/"version": "19.0.1.0.12"/' "$MANIFEST"
}

# conf con credenciales, igual que verify_liquidation_payroll_regression.sh
docker exec "$CONTAINER" bash -lc "
  cp /etc/odoo/odoo.conf /tmp/probe.conf
  printf 'db_host = %s\ndb_port = %s\ndb_user = %s\ndb_password = %s\n' \
    '$DB_HOST' '$DB_PORT' '$DB_USER' '$DB_PASS' >> /tmp/probe.conf
"
# el volcado vive en el script de regresion de liquidacion: se extrae tal cual
sed -n "/^docker exec -i \"\$CONTAINER\" bash -c 'cat > \/tmp\/dump_payroll.py'/,/^PYEOF$/p" \
  "$SCRIPT_DIR/verify_liquidation_payroll_regression.sh" | sed '1d;$d' \
  | docker exec -i "$CONTAINER" bash -c 'cat > /tmp/dump_payroll.py'
docker exec "$CONTAINER" bash -lc "wc -l /tmp/dump_payroll.py"

drop_db() {
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
      \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1' AND pid <> pg_backend_pid()\" >/dev/null
    PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $1
  " 2>&1 | grep -v NOTICE || true
}

dump() {  # $1 db, $2 etiqueta de salida
  docker exec -i "$CONTAINER" bash -lc \
    "odoo shell -c /tmp/probe.conf -d $1 --no-http --log-level=error < /tmp/dump_payroll.py" \
    2>/dev/null | sed -n '/===DUMP_START===/,/===DUMP_END===/p' | sed '1d;$d' > "$OUT_DIR/$2.json"
  python3 -c "import json,sys;d=json.load(open('$OUT_DIR/$2.json'));print('  volcado $2: %s escenarios, %s con error' % (len(d), sum(1 for v in d.values() if '__error__' in v)))"
}

echo "======================================================"
echo " Regresion de nomina — fix country_id de los input types"
echo "======================================================"

echo "→ instalando con el codigo anterior..."
drop_db "$DB"
docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB" || exit 1
use_old_code
docker exec "$CONTAINER" bash -lc "odoo -c /tmp/probe.conf -d $DB --no-http --http-port=8076 --stop-after-init --without-demo=all -i l10n_do_hr_payroll --log-level=warn" 2>&1 | grep -Ei "Traceback|CRITICAL" | head -5
echo "→ volcado ANTES"
dump "$DB" antes

restore_new_code
echo "→ actualizando con el codigo de la rama..."
docker exec "$CONTAINER" bash -lc "odoo -c /tmp/probe.conf -d $DB --no-http --http-port=8076 --stop-after-init -u l10n_do_hr_payroll --log-level=warn" 2>&1 | grep -Ei "Traceback|CRITICAL" | head -5
echo "→ volcado DESPUES"
dump "$DB" despues

if docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_RESCUED'\"" | grep -q 1; then
  echo "→ volcado de la instancia rescatada ($DB_RESCUED)"
  dump "$DB_RESCUED" rescatada
fi

echo
echo "======================================================"
echo " Comparacion"
echo "======================================================"
python3 - "$OUT_DIR" <<'PYEOF'
import json, os, sys
out = sys.argv[1]
def load(name):
    path = os.path.join(out, name + '.json')
    return json.load(open(path)) if os.path.exists(path) and os.path.getsize(path) else None

before, after, rescued = load('antes'), load('despues'), load('rescatada')
status = 0
def compare(label, a, b):
    global status
    if not a or not b:
        print('  %s: falta un volcado' % label); status = 1; return
    diff = sorted(k for k in a if a.get(k) != b.get(k))
    print('  %s: %d/%d escenarios identicos' % (label, len(a) - len(diff), len(a)))
    for key in diff:
        print('    ! %s' % key)
        print('        antes  : %s' % json.dumps(a[key], ensure_ascii=False)[:200])
        print('        despues: %s' % json.dumps(b.get(key), ensure_ascii=False)[:200])
    if diff:
        status = 1

compare('antes vs despues del fix', before, after)
if rescued:
    compare('despues vs instancia rescatada', after, rescued)
errors = sorted(k for k, v in (after or {}).items() if '__error__' in v)
if errors:
    print('  escenarios que ya fallaban antes del fix (bugs preexistentes de la localizacion):')
    for key in errors:
        same = before and '__error__' in before.get(key, {})
        print('    %s %s -> %s' % ('=' if same else '!', key, after[key]['__error__'][:120]))
        if not same:
            status = 1
print()
print('RESULTADO: %s' % ('PASA' if status == 0 else 'REVISAR'))
sys.exit(status)
PYEOF
STATUS=$?
$KEEP || drop_db "$DB"
exit $STATUS
