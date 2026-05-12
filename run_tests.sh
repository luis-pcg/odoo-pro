#!/bin/bash
# run_tests.sh — Corre todos los tests de odoo-pro v19
# Uso: ./run_tests.sh [--keep-db]
#
# Fases:
#   1. Descubrir módulos (odoo-pro root + OCA/* + store-addons)
#   2. Instalar todos en DB de test fresca
#   3. Correr tests (solo módulos con dir tests/, excluye core/enterprise)
#   4. Generar reporte MD

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ─── Cargar variables de entorno ─────────────────────────────────────────────
if [[ ! -f "$SCRIPT_DIR/.env" ]]; then
  echo "ERROR: .env no encontrado en $SCRIPT_DIR" >&2
  exit 1
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

for arg in "$@"; do
  [[ "$arg" == "--keep-db" ]] && KEEP_DB=true
done

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOG_DIR="$SCRIPT_DIR/test_logs"
INSTALL_LOG="$LOG_DIR/install_${TIMESTAMP}.log"
TEST_LOG="$LOG_DIR/test_${TIMESTAMP}.log"
MODULES_FILE="$LOG_DIR/modules_${TIMESTAMP}.txt"
REPORT="$SCRIPT_DIR/test_report_${TIMESTAMP}.md"

mkdir -p "$LOG_DIR"

echo "======================================================"
echo " Odoo Pro v19 — Test Runner"
echo "======================================================"
echo " Contenedor : $CONTAINER"
echo " Test DB    : $TEST_DB"
echo " Timestamp  : $TIMESTAMP"
echo " Logs       : $LOG_DIR"
echo "======================================================"
echo ""

# ─── Verificar que el container esté corriendo ───────────────────────────────
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: Contenedor '$CONTAINER' no está corriendo." >&2
  echo "Corre: docker-compose up -d" >&2
  exit 1
fi

# ─── 1. Descubrir módulos ────────────────────────────────────────────────────
echo "[1/4] Descubriendo módulos en odoo-pro..."

# Corre dentro del container para usar los paths reales de /mnt/
MODULES_RAW=$(docker exec "$CONTAINER" python3 - <<'PYEOF'
import os, sys

# Paths a escanear (excluye core Odoo y enterprise)
scan_paths = [
    '/mnt/extra-addons-pro',
    '/mnt/extra-addons-pro/store-addons',
]

# Agregar todos los subdirs de OCA
oca_base = '/mnt/extra-addons-pro/OCA'
if os.path.isdir(oca_base):
    for sub in sorted(os.listdir(oca_base)):
        full = os.path.join(oca_base, sub)
        if os.path.isdir(full):
            scan_paths.append(full)

# Directorios que NO son módulos (están en raíz de extra-addons-pro)
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
        init_file = os.path.join(tests_dir, '__init__.py')
        if os.path.isdir(tests_dir) and os.path.isfile(init_file):
            modules_with_tests.append(name)

print('ALL=' + ','.join(modules_all))
print('WITH_TESTS=' + ','.join(modules_with_tests))
PYEOF
)

ALL_MODULES=$(echo "$MODULES_RAW" | grep '^ALL=' | cut -d= -f2-)
TEST_MODULES=$(echo "$MODULES_RAW" | grep '^WITH_TESTS=' | cut -d= -f2-)

ALL_COUNT=$(echo "$ALL_MODULES" | tr ',' '\n' | grep -c .)
TEST_COUNT=$(echo "$TEST_MODULES" | tr ',' '\n' | grep -c .)

echo "   Módulos encontrados : $ALL_COUNT"
echo "   Con tests           : $TEST_COUNT"
echo ""

# Guardar lista para referencia
echo "ALL_MODULES=$ALL_MODULES" > "$MODULES_FILE"
echo "TEST_MODULES=$TEST_MODULES" >> "$MODULES_FILE"

if [[ -z "$ALL_MODULES" ]]; then
  echo "ERROR: No se encontraron módulos." >&2
  exit 1
fi

# ─── 2. Limpiar DB de test previa ────────────────────────────────────────────
echo "[2/4] Preparando DB de tests limpia ($TEST_DB)..."

docker exec "$CONTAINER" bash -c "
  PGPASSWORD='$DB_PASS' psql \
    -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
    -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TEST_DB';\" \
    postgres > /dev/null 2>&1 || true
  PGPASSWORD='$DB_PASS' dropdb \
    -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
    --if-exists '$TEST_DB' 2>/dev/null || true
" 2>/dev/null || true

echo "   DB anterior eliminada."
echo ""

# ─── 3. Instalar todos los módulos ───────────────────────────────────────────
echo "[3/4] Instalando $ALL_COUNT módulos (esto puede tardar varios minutos)..."
echo "   Log: $INSTALL_LOG"
echo ""

INSTALL_START=$(date +%s)

docker exec "$CONTAINER" odoo \
  -d "$TEST_DB" \
  --db_host="$DB_HOST" \
  --db_port="$DB_PORT" \
  --db_user="$DB_USER" \
  --db_password="$DB_PASS" \
  --http-port="$HTTP_PORT" \
  --stop-after-init \
  --no-http \
  -i "$ALL_MODULES" \
  2>&1 | tee "$INSTALL_LOG"

INSTALL_EXIT=${PIPESTATUS[0]}
INSTALL_END=$(date +%s)
INSTALL_DURATION=$((INSTALL_END - INSTALL_START))

echo ""
if [[ $INSTALL_EXIT -ne 0 ]]; then
  echo "AVISO: Odoo retornó código $INSTALL_EXIT en fase de instalación."
  echo "       Algunos módulos pueden haber fallado. Continuando con tests..."
fi
echo "   Instalación completada en ${INSTALL_DURATION}s"
echo ""

# ─── 4. Correr tests ─────────────────────────────────────────────────────────
echo "[4/4] Corriendo tests de $TEST_COUNT módulos..."
echo "   --test-tags: solo módulos pro (excluye core/enterprise)"
echo "   Log: $TEST_LOG"
echo ""

TEST_START=$(date +%s)

docker exec "$CONTAINER" odoo \
  -d "$TEST_DB" \
  --db_host="$DB_HOST" \
  --db_port="$DB_PORT" \
  --db_user="$DB_USER" \
  --db_password="$DB_PASS" \
  --http-port="$HTTP_PORT" \
  --test-enable \
  --stop-after-init \
  --no-http \
  --test-tags "$TEST_MODULES" \
  -u "$TEST_MODULES" \
  2>&1 | tee "$TEST_LOG"

TEST_EXIT=${PIPESTATUS[0]}
TEST_END=$(date +%s)
TEST_DURATION=$((TEST_END - TEST_START))

echo ""
echo "   Tests completados en ${TEST_DURATION}s"
echo ""

# ─── 5. Limpiar DB si no se pidió conservar ──────────────────────────────────
if [[ "$KEEP_DB" == "false" ]]; then
  echo "Limpiando DB de tests..."
  docker exec "$CONTAINER" bash -c "
    PGPASSWORD='$DB_PASS' psql \
      -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$TEST_DB';\" \
      postgres > /dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb \
      -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      --if-exists '$TEST_DB' 2>/dev/null || true
  " 2>/dev/null || true
else
  echo "DB '$TEST_DB' conservada (--keep-db)."
fi
echo ""

# ─── 6. Generar reporte ──────────────────────────────────────────────────────
echo "Generando reporte..."

python3 "$SCRIPT_DIR/parse_test_log.py" \
  --install-log "$INSTALL_LOG" \
  --test-log    "$TEST_LOG" \
  --modules-file "$MODULES_FILE" \
  --output      "$REPORT" \
  --timestamp   "$TIMESTAMP" \
  --install-duration "$INSTALL_DURATION" \
  --test-duration    "$TEST_DURATION"

echo ""
echo "======================================================"
echo " Reporte generado: $REPORT"
echo "======================================================"
