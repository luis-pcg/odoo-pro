#!/bin/bash
# run_tests.sh — Odoo Pro v19 Test Runner
#
# Instala todos los módulos en una DB y corre los tests módulo por módulo.
#
# Uso:
#   ./run_tests.sh                        # correr todos los módulos
#   ./run_tests.sh --keep-db              # conservar DB al finalizar
#   ./run_tests.sh --module=l10n_do_sale  # solo ese módulo
#   ./run_tests.sh --module=l10n_do_sale --keep-db

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Config desde .env ───────────────────────────────────────────────────────
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo "ERROR: .env no encontrado en $SCRIPT_DIR" >&2; exit 1
fi
source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
TEST_DB="test_v19_report"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
HTTP_PORT="8070"
KEEP_DB=false
WITH_DEMO=false
ONLY_MODULE=""

for arg in "$@"; do
  case "$arg" in
    --keep-db)    KEEP_DB=true ;;
    --demo)       WITH_DEMO=true ;;
    --module=*)   ONLY_MODULE="${arg#--module=}" ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$SCRIPT_DIR/test_logs"
INSTALL_LOG="$LOG_DIR/install.log"
MODULES_FILE="$LOG_DIR/modules.txt"
MODULES_LOG_DIR="$LOG_DIR/modules"
RESULTS_DIR="$LOG_DIR/.results"
REPORT="$SCRIPT_DIR/test_report.md"

mkdir -p "$LOG_DIR"

# ─── Banner ──────────────────────────────────────────────────────────────────
echo "======================================================"
echo " Odoo Pro v19 — Test Runner"
echo "======================================================"
echo " Contenedor : $CONTAINER"
echo " Test DB    : $TEST_DB"
[[ -n "$ONLY_MODULE" ]] && echo " Módulo     : $ONLY_MODULE (solo este)"
echo " Timestamp  : $TIMESTAMP"
echo " Logs       : $LOG_DIR"
echo "======================================================"
echo ""

# ─── Verificar container ─────────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: Contenedor '$CONTAINER' no está corriendo." >&2
  echo "       Corre: docker-compose up -d" >&2; exit 1
fi

# ─── Helper: drop DB ─────────────────────────────────────────────────────────
_drop_db() {
  local DB="$1"
  docker exec "$CONTAINER" bash -c "
    PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity
           WHERE datname = '$DB' AND pid <> pg_backend_pid();\" \
      > /dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      --if-exists '$DB' 2>/dev/null || true" 2>/dev/null || true
}

# ─── 1. Descubrir módulos ────────────────────────────────────────────────────
echo "[1/4] Descubriendo módulos en odoo-pro..."

MODULES_RAW=$(docker exec -i "$CONTAINER" python3 - <<'PYEOF'
import os

scan_paths = [
    '/mnt/extra-addons-pro',
    '/mnt/extra-addons-pro/store-addons',
]
skip_names = {'OCA', 'store-addons', '.git', '__pycache__', 'Dockerfile'}
modules_all = []
modules_with_tests = []
seen = set()

for base_path in scan_paths:
    if not os.path.isdir(base_path):
        continue
    for name in sorted(os.listdir(base_path)):
        if name in skip_names or name.startswith('.'):
            continue
        mod_path = os.path.join(base_path, name)
        if not os.path.isdir(mod_path):
            continue
        if not os.path.isfile(os.path.join(mod_path, '__manifest__.py')):
            continue
        if name in seen:
            continue
        seen.add(name)
        modules_all.append(name)
        tests_dir = os.path.join(mod_path, 'tests')
        if os.path.isdir(tests_dir) and os.path.isfile(os.path.join(tests_dir, '__init__.py')):
            modules_with_tests.append(name)

print('ALL=' + ','.join(modules_all))
print('WITH_TESTS=' + ','.join(modules_with_tests))
PYEOF
)

ALL_MODULES=$(echo "$MODULES_RAW" | grep '^ALL='        | cut -d= -f2-)
TEST_MODULES=$(echo "$MODULES_RAW" | grep '^WITH_TESTS=' | cut -d= -f2-)

if [[ -n "$ONLY_MODULE" ]]; then
  if ! echo "$TEST_MODULES" | tr ',' '\n' | grep -q "^${ONLY_MODULE}$"; then
    echo "ERROR: '$ONLY_MODULE' no encontrado o sin tests." >&2; exit 1
  fi
  TEST_MODULES="$ONLY_MODULE"
fi

ALL_COUNT=$(echo "$ALL_MODULES"  | tr ',' '\n' | grep -c .)
TEST_COUNT=$(echo "$TEST_MODULES" | tr ',' '\n' | grep -c .)

echo "   Módulos total : $ALL_COUNT"
echo "   Con tests     : $TEST_COUNT"
[[ -n "$ONLY_MODULE" ]] && echo "   Filtrado a    : $ONLY_MODULE"
echo ""

echo "ALL_MODULES=$ALL_MODULES"   > "$MODULES_FILE"
echo "TEST_MODULES=$TEST_MODULES" >> "$MODULES_FILE"

[[ -z "$ALL_MODULES" ]] && { echo "ERROR: No se encontraron módulos." >&2; exit 1; }

# ─── 2. Instalar todos los módulos ───────────────────────────────────────────
echo "[2/4] Instalando $ALL_COUNT módulos en '$TEST_DB'..."
echo "   Log : $INSTALL_LOG"
echo ""

_drop_db "$TEST_DB"

DEMO_FLAG="--without-demo=all"
[[ "$WITH_DEMO" == "true" ]] && DEMO_FLAG=""

INSTALL_START=$(date +%s)

docker exec "$CONTAINER" odoo \
  -d "$TEST_DB" \
  --db_host="$DB_HOST" --db_port="$DB_PORT" \
  --db_user="$DB_USER" --db_password="$DB_PASS" \
  --http-port="$HTTP_PORT" \
  --log-level=info --stop-after-init --no-http \
  $DEMO_FLAG \
  -i "$ALL_MODULES" \
  2>&1 | tee "$INSTALL_LOG" | grep --line-buffered \
    -E "loading module|modules loaded|Module.*failed|ERROR|odoo\.modules\.loading" || true

INSTALL_DURATION=$(( $(date +%s) - INSTALL_START ))
echo ""
echo "   Instalación completada en ${INSTALL_DURATION}s"
echo ""

# ─── Configurar país ─────────────────────────────────────────────────────────
echo "   Configurando país: República Dominicana (DO)..."
docker exec "$CONTAINER" bash -c "
  PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' -d '$TEST_DB' -q \
    -c \"UPDATE res_company
         SET country_id  = (SELECT id FROM res_country  WHERE code = 'DO' LIMIT 1),
             currency_id = COALESCE(
               (SELECT id FROM res_currency WHERE name = 'DOP' LIMIT 1), currency_id)
         WHERE id = 1;\" 2>/dev/null" && \
  echo "   País configurado." || echo "   AVISO: no se pudo configurar país."
echo ""

# ─── 3. Correr tests módulo por módulo ───────────────────────────────────────
echo "[3/4] Corriendo tests ($TEST_COUNT módulos, secuencial en '$TEST_DB')..."
echo ""

mkdir -p "$MODULES_LOG_DIR" "$RESULTS_DIR"
rm -f "$RESULTS_DIR"/*.result 2>/dev/null || true

TEST_START=$(date +%s)

IFS=',' read -ra MOD_ARRAY <<< "$TEST_MODULES"
MOD_NUM=0
PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

for MODULE in "${MOD_ARRAY[@]}"; do
  [[ -z "$MODULE" ]] && continue
  MOD_NUM=$((MOD_NUM + 1))
  MOD_LOG="$MODULES_LOG_DIR/${MODULE}.log"

  printf '  [%3d/%3d] %-52s' "$MOD_NUM" "$TEST_COUNT" "$MODULE"

  T0=$(date +%s)

  docker exec "$CONTAINER" odoo \
    -d "$TEST_DB" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --http-port="$HTTP_PORT" \
    --log-level=info \
    --test-enable --stop-after-init --no-http \
    --test-tags "/$MODULE" \
    -u "$MODULE" \
    > "$MOD_LOG" 2>&1 || true

  DUR=$(( $(date +%s) - T0 ))

  # Detectar resultado
  if grep -qE "odoo\.tests\.result:.*[1-9][0-9]* (failed|error)" "$MOD_LOG" 2>/dev/null || \
     grep -qE " ERROR .*odoo\.(tests\.suite|addons\.$MODULE)\..*: (FAIL|ERROR): " "$MOD_LOG" 2>/dev/null; then
    STATUS="FAIL"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  elif grep -qE "odoo\.tests\.stats:.*${MODULE}:" "$MOD_LOG" 2>/dev/null; then
    STATUS="PASS"
    PASS_COUNT=$((PASS_COUNT + 1))
  else
    STATUS="SKIP"
    SKIP_COUNT=$((SKIP_COUNT + 1))
  fi

  echo "$STATUS $DUR" > "$RESULTS_DIR/${MODULE}.result"

  case "$STATUS" in
    PASS) printf ' ✅ PASS  (%ds)\n' "$DUR" ;;
    FAIL) printf ' ❌ FAIL  (%ds)\n' "$DUR" ;;
    SKIP) printf ' ⚠️  SKIP  (%ds)\n' "$DUR" ;;
  esac
done

TEST_DURATION=$(( $(date +%s) - TEST_START ))

echo ""
echo "   ═══════════════════════════════════════════════════════"
echo "   ✅ $PASS_COUNT pasaron  ❌ $FAIL_COUNT fallaron  ⚠️  $SKIP_COUNT sin tests"
echo "   Tiempo tests : ${TEST_DURATION}s ($(( TEST_DURATION / 60 ))m $(( TEST_DURATION % 60 ))s)"
echo "   ═══════════════════════════════════════════════════════"
echo ""

# ─── 4. Limpiar DB ───────────────────────────────────────────────────────────
if [[ "$KEEP_DB" == "false" ]]; then
  echo "Limpiando DB ($TEST_DB)..."
  _drop_db "$TEST_DB"
  echo "   Listo."
else
  echo "DB '$TEST_DB' conservada (--keep-db)."
  echo "   Re-testear un módulo: ./run_tests.sh --module=NOMBRE --keep-db"
fi
echo ""

# ─── 5. Generar reporte ──────────────────────────────────────────────────────
echo "Generando reporte..."

if python3 "$SCRIPT_DIR/parse_test_log.py" \
  --install-log     "$INSTALL_LOG" \
  --modules-log-dir "$MODULES_LOG_DIR" \
  --modules-file    "$MODULES_FILE" \
  --output          "$REPORT" \
  --timestamp       "$TIMESTAMP" \
  --install-duration "$INSTALL_DURATION" \
  --test-duration   "$TEST_DURATION"; then

  echo ""
  echo "================================================================"
  echo " Reporte: $REPORT"
  echo "================================================================"
  echo ""
  echo " CÓMO CORRER"
  echo " ─────────────────────────────────────────────────────────────"
  echo " Todos los módulos:"
  echo "   ./run_tests.sh"
  echo "   ./run_tests.sh --keep-db      # conservar DB al finalizar"
  echo ""
  echo " Módulo específico (debug):"
  echo "   ./run_tests.sh --module=l10n_do_sale"
  echo "   ./run_tests.sh --module=l10n_do_sale --keep-db"
  echo " ─────────────────────────────────────────────────────────────"
else
  echo ""
  echo "ERROR: parse_test_log.py falló. Logs en $LOG_DIR"
  echo "Reprocesar manualmente:"
  echo "  python3 $SCRIPT_DIR/parse_test_log.py \\"
  echo "    --install-log     $INSTALL_LOG \\"
  echo "    --modules-log-dir $MODULES_LOG_DIR \\"
  echo "    --modules-file    $MODULES_FILE \\"
  echo "    --output          $REPORT \\"
  echo "    --timestamp       $TIMESTAMP \\"
  echo "    --install-duration $INSTALL_DURATION \\"
  echo "    --test-duration   $TEST_DURATION"
fi
