#!/bin/bash
# run_tests.sh — Odoo Pro v17 Test Runner
#
# Replica condiciones de GH Actions para correr tests localmente.
#
# Uso:
#   ./run_tests.sh                        # todos los módulos (modo debug, por módulo)
#   ./run_tests.sh --ci                   # replica GH Actions exacto (1 invocación)
#   ./run_tests.sh --keep-db              # conservar DB al finalizar
#   ./run_tests.sh --module=l10n_do_sale  # solo ese módulo
#   ./run_tests.sh --no-demo              # sin demo data (más rápido, menos realista)
#
# Alineado con GH Actions (.github/workflows/tests.yaml):
#   - Módulos: depth=1 (solo root de odoo-pro, igual que get_modules depth=1)
#   - Demo data: ON por defecto (igual que GH, sin --without-demo)
#   - --ci: instala todo + corre tests en UNA sola invocación (igual que GH)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Config desde .env ───────────────────────────────────────────────────────
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo "ERROR: .env no encontrado en $SCRIPT_DIR" >&2; exit 1
fi
source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v17"
TEST_DB="odoo_test"           # igual que GH Actions
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
HTTP_PORT="8070"
KEEP_DB=false
WITH_DEMO=true   # ON por defecto — igual que GH Actions
ONLY_MODULE=""
CI_MODE=false    # --ci: una sola invocación odoo (réplica exacta de GH)

for arg in "$@"; do
  case "$arg" in
    --keep-db)    KEEP_DB=true ;;
    --no-demo)    WITH_DEMO=false ;;
    --ci)         CI_MODE=true ;;
    --module=*)   ONLY_MODULE="${arg#--module=}" ;;
  esac
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$SCRIPT_DIR/test_logs"
INSTALL_LOG="$LOG_DIR/install.log"
CI_LOG="$LOG_DIR/ci_run.log"
MODULES_FILE="$LOG_DIR/modules.txt"
MODULES_LOG_DIR="$LOG_DIR/modules"
RESULTS_DIR="$LOG_DIR/.results"
REPORT="$SCRIPT_DIR/test_report.md"

mkdir -p "$LOG_DIR"

# ─── Banner ──────────────────────────────────────────────────────────────────
echo "======================================================"
echo " Odoo Pro v17 — Test Runner"
echo "======================================================"
echo " Contenedor : $CONTAINER"
echo " Test DB    : $TEST_DB"
echo " Modo       : $([ "$CI_MODE" = true ] && echo 'CI (réplica GH Actions)' || echo 'Debug (por módulo)')"
echo " Demo data  : $([ "$WITH_DEMO" = true ] && echo 'ON (igual que GH)' || echo 'OFF')"
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
echo "[1/4] Descubriendo módulos en odoo-pro (depth=1, igual que GH Actions)..."

# Solo root de /mnt/extra-addons-pro — igual que get_modules(depth=1) en GH.
# store-addons y OCA se usan como dependencias (están en addons_path de odoo.conf)
# pero NO se testean directamente, igual que en CI.
MODULES_RAW=$(docker exec -i "$CONTAINER" python3 - <<'PYEOF'
import ast
import os

scan_paths = [
    '/mnt/extra-addons-pro',
]
skip_names = {'OCA', 'store-addons', '.git', '__pycache__', 'Dockerfile', 'README.md'}
modules_all = []
modules_not_installable = []
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
        manifest_path = os.path.join(mod_path, '__manifest__.py')
        if not os.path.isfile(manifest_path):
            continue
        if name in seen:
            continue
        seen.add(name)

        try:
            with open(manifest_path, encoding='utf-8') as f:
                manifest = ast.literal_eval(f.read())
        except Exception:
            manifest = {}

        if not manifest.get('installable', True):
            modules_not_installable.append(name)
            continue

        modules_all.append(name)
        tests_dir = os.path.join(mod_path, 'tests')
        if os.path.isdir(tests_dir) and os.path.isfile(os.path.join(tests_dir, '__init__.py')):
            modules_with_tests.append(name)

print('ALL=' + ','.join(modules_all))
print('WITH_TESTS=' + ','.join(modules_with_tests))
print('NOT_INSTALLABLE=' + ','.join(modules_not_installable))
PYEOF
)

ALL_MODULES=$(echo "$MODULES_RAW"     | grep '^ALL='             | cut -d= -f2-)
TEST_MODULES=$(echo "$MODULES_RAW"    | grep '^WITH_TESTS='      | cut -d= -f2-)
NOT_INSTALLABLE=$(echo "$MODULES_RAW" | grep '^NOT_INSTALLABLE=' | cut -d= -f2-)

if [[ -n "$ONLY_MODULE" ]]; then
  if ! echo "$TEST_MODULES" | tr ',' '\n' | grep -q "^${ONLY_MODULE}$"; then
    echo "ERROR: '$ONLY_MODULE' no encontrado en root de odoo-pro o sin tests." >&2; exit 1
  fi
  TEST_MODULES="$ONLY_MODULE"
fi

ALL_COUNT=$(echo "$ALL_MODULES"     | tr ',' '\n' | grep -c .)
TEST_COUNT=$(echo "$TEST_MODULES"   | tr ',' '\n' | grep -c .)
SKIP_COUNT=$(echo "$NOT_INSTALLABLE" | tr ',' '\n' | grep -c . 2>/dev/null || echo 0)

echo "   Módulos instalables : $ALL_COUNT"
echo "   Con tests            : $TEST_COUNT"
echo "   No instalables       : $SKIP_COUNT  (excluidos)"
[[ -n "$ONLY_MODULE" ]] && echo "   Filtrado a           : $ONLY_MODULE"
echo ""

echo "ALL_MODULES=$ALL_MODULES"           > "$MODULES_FILE"
echo "TEST_MODULES=$TEST_MODULES"         >> "$MODULES_FILE"
echo "NOT_INSTALLABLE=$NOT_INSTALLABLE"   >> "$MODULES_FILE"

[[ -z "$ALL_MODULES" ]] && { echo "ERROR: No se encontraron módulos." >&2; exit 1; }

# ─── Instalar requirements.txt — igual que GH Actions ───────────────────────
# GH Actions hace: for req_file in $(find /workspace -name 'requirements.txt'); do pip3 install -r $req_file; done
echo "[PRE] Instalando dependencias Python (requirements.txt)..."
docker exec "$CONTAINER" bash -c "
  find /mnt/extra-addons-pro -name 'requirements.txt' 2>/dev/null | while read req; do
    echo \"  pip: \$req\"
    # Filtrar líneas git+url: git no está en container (GH Actions sí lo tiene)
    grep -v '@.*git+' \"\$req\" > /tmp/_req_filtered.txt
    pip3 install --no-cache-dir -q -r /tmp/_req_filtered.txt 2>&1 \
      | grep -v '^Requirement already' \
      | grep -v '^WARNING: Running pip as' || true
  done
  rm -f /tmp/_req_filtered.txt
  echo '  Listo.'
"
echo ""

# ─── Modo CI: réplica exacta de GH Actions ───────────────────────────────────
# Una sola invocación odoo: install + test en un comando.
# Equivalente a lo que hace GH Actions.
if [[ "$CI_MODE" == "true" ]]; then
  echo "══════════════════════════════════════════════════════"
  echo "  MODO CI — réplica exacta de GH Actions"
  echo "  Una invocación: install + test todos los módulos"
  echo "══════════════════════════════════════════════════════"
  echo ""

  # Generar test tags: /module1,/module2,... igual que GH
  TEST_TAGS_CI=$(echo "$TEST_MODULES" | tr ',' '\n' | sed 's/^/\//' | paste -sd ',' -)
  echo "   Test tags: $TEST_TAGS_CI"
  echo ""

  DEMO_CI=""
  [[ "$WITH_DEMO" == "false" ]] && DEMO_CI="--without-demo=all"

  _drop_db "$TEST_DB"

  echo "[CI] Instalando + corriendo tests..."
  echo "     Log: $CI_LOG"
  echo ""

  CI_START=$(date +%s)

  docker exec "$CONTAINER" odoo \
    -d "$TEST_DB" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --http-port="$HTTP_PORT" \
    --log-level=test \
    --test-enable --stop-after-init --no-http \
    $DEMO_CI \
    -i "$ALL_MODULES" \
    --test-tags "$TEST_TAGS_CI" \
    2>&1 | tee "$CI_LOG" | grep --line-buffered \
      -E "loading module|TEST.*odoo\.tests|failed.*of.*tests|passed|ERROR|FAIL:|odoo\.modules\.loading" || true

  CI_DURATION=$(( $(date +%s) - CI_START ))

  # Resultado rápido en consola
  echo ""
  RESULT_LINE=$(grep -E "[0-9]+ failed, [0-9]+ error\(s\) of [0-9]+ tests" "$CI_LOG" | tail -1 || true)
  if [[ -n "$RESULT_LINE" ]]; then
    echo " $RESULT_LINE"
  else
    echo " ⚠️   No se encontró línea de resultado — revisa $CI_LOG"
  fi
  echo " Tiempo total: ${CI_DURATION}s ($(( CI_DURATION / 60 ))m $(( CI_DURATION % 60 ))s)"
  echo ""

  # ─── Obtener autores git por módulo ────────────────────────────────────────
  echo "Obteniendo autores git..."
  MODULE_AUTHORS=""
  ALL_MODS_COMBINED="$ALL_MODULES"
  [[ -n "$NOT_INSTALLABLE" ]] && ALL_MODS_COMBINED="$ALL_MODS_COMBINED,$NOT_INSTALLABLE"
  IFS=',' read -ra ALL_MOD_ARRAY <<< "$ALL_MODS_COMBINED"
  for MOD in "${ALL_MOD_ARRAY[@]}"; do
    [[ -z "$MOD" ]] && continue
    AUTHOR=$(git -C "$SCRIPT_DIR/odoo-pro" log -1 --format="%an" \
      -- "$MOD/" 2>/dev/null | head -1 | tr ',' ';')
    [[ -z "$AUTHOR" ]] && AUTHOR="-"
    MODULE_AUTHORS="${MODULE_AUTHORS}${MOD}:${AUTHOR},"
  done
  echo "MODULE_AUTHORS=$MODULE_AUTHORS" >> "$MODULES_FILE"
  echo "   Listo."
  echo ""

  # ─── Generar reporte ───────────────────────────────────────────────────────
  echo "Generando reporte CI..."
  PDF_REPORT="${REPORT%.md}.pdf"

  if python3 "$SCRIPT_DIR/parse_test_log.py" \
    --ci-log           "$CI_LOG" \
    --modules-file     "$MODULES_FILE" \
    --output           "$REPORT" \
    --timestamp        "$TIMESTAMP" \
    --install-duration 0 \
    --test-duration    "$CI_DURATION"; then

    echo ""
    echo "╔══════════════════════════════════════════════════════════════╗"
    echo "║                   REPORTE CI GENERADO ✅                     ║"
    echo "╠══════════════════════════════════════════════════════════════╣"
    printf  "║  Markdown : %-48s ║\n" "$REPORT"
    [[ -f "$PDF_REPORT" ]] && printf "║  PDF      : %-48s ║\n" "$PDF_REPORT"
    echo "╠══════════════════════════════════════════════════════════════╣"
    echo "║  FLUJO DE TRABAJO                                            ║"
    echo "║  ./run_tests.sh --ci             # replicar GH Actions       ║"
    echo "║  ./run_tests.sh --module=NOMBRE  # depurar módulo específico ║"
    echo "╚══════════════════════════════════════════════════════════════╝"
  else
    echo "❌ ERROR: parse_test_log.py falló. Log en $CI_LOG"
  fi
  echo ""

  if [[ "$KEEP_DB" == "false" ]]; then
    echo "Limpiando DB ($TEST_DB)..."
    _drop_db "$TEST_DB"
  else
    echo "DB '$TEST_DB' conservada (--keep-db)."
  fi
  exit 0
fi

# ─── Modo Debug (default): instalar + correr por módulo ─────────────────────

# ─── 2. Instalar todos los módulos ───────────────────────────────────────────
echo "[2/4] Instalando $ALL_COUNT módulos en '$TEST_DB'..."
echo "   Log : $INSTALL_LOG"
echo ""

_drop_db "$TEST_DB"

DEMO_FLAG=""
[[ "$WITH_DEMO" == "false" ]] && DEMO_FLAG="--without-demo=all"

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

# ─── 2b. Segunda pasada — resuelve orden de dependencias ─────────────────────
echo "[2b/4] Segunda pasada de instalación (resuelve orden de dependencias)..."
docker exec "$CONTAINER" odoo \
  -d "$TEST_DB" \
  --db_host="$DB_HOST" --db_port="$DB_PORT" \
  --db_user="$DB_USER" --db_password="$DB_PASS" \
  --http-port="$HTTP_PORT" \
  --log-level=warn --stop-after-init --no-http \
  $DEMO_FLAG \
  -i "$ALL_MODULES" \
  >> "$INSTALL_LOG" 2>&1 | grep --line-buffered \
    -E "loading module|modules loaded|Module.*failed|ERROR" || true
echo "   Segunda pasada completada."
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

  MOD_AUTHOR=$(git -C "$SCRIPT_DIR/odoo-pro" log -1 --format="%an" \
    -- "$MODULE/" \
    2>/dev/null | head -1)
  [[ -z "$MOD_AUTHOR" ]] && MOD_AUTHOR="-"

  MOD_STATE=$(docker exec "$CONTAINER" bash -c \
    "PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
     -d '$TEST_DB' -tAq \
     -c \"SELECT state FROM ir_module_module WHERE name='$MODULE'\" 2>/dev/null" \
    | tr -d '[:space:]')
  if [[ "$MOD_STATE" == "installed" ]]; then
    INSTALL_FLAG="-u"
  else
    INSTALL_FLAG="-i"
  fi

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
    "$INSTALL_FLAG" "$MODULE" \
    > "$MOD_LOG" 2>&1 || true

  DUR=$(( $(date +%s) - T0 ))

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
    PASS) printf ' ✅ PASS  - %-18s (%ds)\n' "$MOD_AUTHOR" "$DUR" ;;
    FAIL) printf ' ❌ FAIL  - %-18s (%ds)\n' "$MOD_AUTHOR" "$DUR" ;;
    SKIP) printf ' ⚠️  SKIP  - %-18s (%ds)\n' "$MOD_AUTHOR" "$DUR" ;;
  esac
done

TEST_DURATION=$(( $(date +%s) - TEST_START ))

echo ""
echo "   ═══════════════════════════════════════════════════════"
echo "   ✅ $PASS_COUNT pasaron  ❌ $FAIL_COUNT fallaron  ⚠️  $SKIP_COUNT sin tests"
echo "   Tiempo tests : ${TEST_DURATION}s ($(( TEST_DURATION / 60 ))m $(( TEST_DURATION % 60 ))s)"
echo "   ═══════════════════════════════════════════════════════"
echo ""

# ─── Obtener autores git por módulo ─────────────────────────────────────────
echo "Obteniendo autores git..."
MODULE_AUTHORS=""
ALL_MODS_COMBINED="$ALL_MODULES"
[[ -n "$NOT_INSTALLABLE" ]] && ALL_MODS_COMBINED="$ALL_MODS_COMBINED,$NOT_INSTALLABLE"

IFS=',' read -ra ALL_MOD_ARRAY <<< "$ALL_MODS_COMBINED"
for MOD in "${ALL_MOD_ARRAY[@]}"; do
  [[ -z "$MOD" ]] && continue
  AUTHOR=$(git -C "$SCRIPT_DIR/odoo-pro" log -1 --format="%an" \
    -- "$MOD/" \
    2>/dev/null | head -1 | tr ',' ';')
  [[ -z "$AUTHOR" ]] && AUTHOR="-"
  MODULE_AUTHORS="${MODULE_AUTHORS}${MOD}:${AUTHOR},"
done
echo "MODULE_AUTHORS=$MODULE_AUTHORS" >> "$MODULES_FILE"
echo "   Listo."
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

# ─── 5. Generar reporte (Markdown + PDF) ────────────────────────────────────
echo "[5/5] Generando reporte..."

PDF_REPORT="${REPORT%.md}.pdf"

if python3 "$SCRIPT_DIR/parse_test_log.py" \
  --install-log      "$INSTALL_LOG" \
  --modules-log-dir  "$MODULES_LOG_DIR" \
  --modules-file     "$MODULES_FILE" \
  --output           "$REPORT" \
  --timestamp        "$TIMESTAMP" \
  --install-duration "$INSTALL_DURATION" \
  --test-duration    "$TEST_DURATION"; then

  echo ""
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║                   REPORTE GENERADO ✅                        ║"
  echo "╠══════════════════════════════════════════════════════════════╣"
  printf  "║  Markdown : %-48s ║\n" "$REPORT"
  [[ -f "$PDF_REPORT" ]] && printf "║  PDF      : %-48s ║\n" "$PDF_REPORT"
  echo "╠══════════════════════════════════════════════════════════════╣"
  echo "║  FLUJO DE TRABAJO                                            ║"
  echo "║  ./run_tests.sh --ci             # replicar GH Actions       ║"
  echo "║  ./run_tests.sh --module=NOMBRE  # depurar módulo específico ║"
  echo "║  ./run_tests.sh --keep-db        # conservar DB              ║"
  echo "║  ./run_tests.sh --no-demo        # sin demo data             ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
else
  echo ""
  echo "❌ ERROR: parse_test_log.py falló. Logs en $LOG_DIR"
  echo "   Reprocesar: python3 $SCRIPT_DIR/parse_test_log.py \\"
  echo "     --install-log $INSTALL_LOG --modules-log-dir $MODULES_LOG_DIR \\"
  echo "     --modules-file $MODULES_FILE --output $REPORT \\"
  echo "     --timestamp $TIMESTAMP --install-duration $INSTALL_DURATION \\"
  echo "     --test-duration $TEST_DURATION"
fi
