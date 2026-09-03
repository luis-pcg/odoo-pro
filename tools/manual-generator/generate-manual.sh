#!/bin/bash
# generate-manual.sh — Generador de manuales de usuario para Odoo Pro v19
#
# 1. Crea una base limpia  test_v19_<modulo>
# 2. Instala el modulo (y sus dependencias)
# 3. (opcional) Siembra datos de ejemplo con configs/<modulo>.seed.py
# 4. Toma capturas de los flujos con Playwright (Chrome del sistema)
# 5. Arma docs/manuals/<modulo>/{README.md,manual.html,manual.pdf}
#
# Uso:
#   ./generate-manual.sh --module=report_zpl_direct_print
#   ./generate-manual.sh --module=report_zpl_direct_print --keep-db --headed
#   ./generate-manual.sh --module=<modulo> --config=configs/<otro>.json --name=manual-usuario
#
# --config y --name permiten un segundo manual del mismo modulo (por ejemplo uno
# corto para usuarios finales) en la misma carpeta, sin pisar al primero.
#
# Para documentar un modulo nuevo: crea configs/<modulo>.json (y opcional
# configs/<modulo>.seed.py) y corre el script con --module=<modulo>.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ─── Config desde .env ───────────────────────────────────────────────────────
if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "ERROR: .env no encontrado en $ROOT_DIR" >&2; exit 1
fi
source "$ROOT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
ODOO_PORT="${ODOO_PORT:-8069}"

MODULE=""
EXTRA_MODULES=""
KEEP_DB=false
HEADED=""
BASE_URL_OVERRIDE=""
CAPTURE_PORT="8071"
CONFIG_OVERRIDE=""
MANUAL_NAME="manual"

for arg in "$@"; do
  case "$arg" in
    --module=*)   MODULE="${arg#--module=}" ;;
    --extra-modules=*) EXTRA_MODULES="${arg#--extra-modules=}" ;;
    --keep-db)    KEEP_DB=true ;;
    --headed)     HEADED="--headed" ;;
    --base-url=*) BASE_URL_OVERRIDE="${arg#--base-url=}" ;;
    --port=*)     CAPTURE_PORT="${arg#--port=}" ;;
    --config=*)   CONFIG_OVERRIDE="${arg#--config=}" ;;
    --name=*)     MANUAL_NAME="${arg#--name=}" ;;
  esac
done

[[ -z "$MODULE" ]] && { echo "ERROR: falta --module=<nombre>" >&2; exit 1; }

CONFIG="${CONFIG_OVERRIDE:-$SCRIPT_DIR/configs/${MODULE}.json}"
SEED="$SCRIPT_DIR/configs/${MODULE}.seed.py"
[[ ! -f "$CONFIG" ]] && { echo "ERROR: no existe $CONFIG" >&2; exit 1; }

# Optional extra modules to install alongside the documented one (e.g. Dominican
# accounting for a full flow). Read from the config's "extra_modules" list.
EXTRA_MODULES="$(python3 -c "import json;print(','.join(json.load(open('$CONFIG')).get('extra_modules',[])))" 2>/dev/null || true)"
INSTALL_LIST="$MODULE"
[[ -n "$EXTRA_MODULES" ]] && INSTALL_LIST="$MODULE,$EXTRA_MODULES"

DB="test_v19_${MODULE}"
OUT_DIR="$ROOT_DIR/docs/manuals/${MODULE}"
IMG_DIR="$OUT_DIR/img"

# The main Odoo server usually runs with a restrictive `dbfilter`, so it will
# not serve our test database. To stay non-invasive (no edits to the user's
# conf), the generator spins up its own throwaway Odoo HTTP server bound only to
# the test DB. If --base-url is given, that server is used instead.
EPHEMERAL_NAME="manualgen_${MODULE}"
if [[ -n "$BASE_URL_OVERRIDE" ]]; then
  CAPTURE_URL="$BASE_URL_OVERRIDE"
else
  CAPTURE_URL="http://localhost:${CAPTURE_PORT}"
fi

mkdir -p "$IMG_DIR"

echo "======================================================"
echo " Generador de manual — Odoo Pro v19"
echo "======================================================"
echo " Modulo     : $MODULE"
echo " Base       : $DB"
echo " Contenedor : $CONTAINER"
echo " URL captura: $CAPTURE_URL"
echo " Salida     : $OUT_DIR"
echo "======================================================"

# ─── Verificar contenedor ────────────────────────────────────────────────────
if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -q "^${CONTAINER}$"; then
  echo "ERROR: el contenedor '$CONTAINER' no esta corriendo." >&2
  echo "       Arranca Docker Desktop y luego: docker-compose up -d" >&2
  exit 1
fi

# Always remove the throwaway capture server on exit.
_cleanup() { docker rm -f "$EPHEMERAL_NAME" >/dev/null 2>&1 || true; }
trap _cleanup EXIT

_drop_db() {
  docker exec "$CONTAINER" bash -c "
    PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity
           WHERE datname = '$DB' AND pid <> pg_backend_pid();\" >/dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      --if-exists '$DB' 2>/dev/null || true" 2>/dev/null || true
}

# ─── 1+2. Crear base e instalar modulo ───────────────────────────────────────
echo "[1/4] Creando base limpia e instalando '$INSTALL_LIST'..."
_drop_db "$DB"
docker exec "$CONTAINER" odoo \
  -d "$DB" \
  --db_host="$DB_HOST" --db_port="$DB_PORT" \
  --db_user="$DB_USER" --db_password="$DB_PASS" \
  --without-demo=all --log-level=warn --stop-after-init --no-http \
  -i "$INSTALL_LIST" \
  2>&1 | grep -E "loading module|modules loaded|ERROR|Module.*failed" || true

# ─── 3. Sembrar datos de ejemplo ─────────────────────────────────────────────
if [[ -f "$SEED" ]]; then
  echo "[2/4] Sembrando datos de ejemplo ($MODULE.seed.py)..."
  docker exec -i "$CONTAINER" odoo shell \
    -d "$DB" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --log-level=error --no-http < "$SEED" 2>&1 | grep -E "SEED OK|Error|Traceback" || true
else
  echo "[2/4] Sin seed (configs/${MODULE}.seed.py no existe). Continuo."
fi

# ─── 3b. Servidor Odoo efimero (solo si no se paso --base-url) ───────────────
if [[ -z "$BASE_URL_OVERRIDE" ]]; then
  echo "[3/4] Levantando servidor Odoo efimero en :$CAPTURE_PORT (db-filter al test DB)..."
  IMAGE="$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')"
  NETWORK="$(docker inspect "$CONTAINER" \
    --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')"
  # Share the main container's /var/lib/odoo volume: the test DB's filestore
  # (incl. generated web assets) lives there; without it every asset 404s/500s
  # and the web client renders an empty page.
  DATA_VOL="$(docker inspect "$CONTAINER" \
    --format '{{range .Mounts}}{{if eq .Destination "/var/lib/odoo"}}{{.Name}}{{end}}{{end}}')"
  DATA_MOUNT=()
  [[ -n "$DATA_VOL" ]] && DATA_MOUNT=(-v "$DATA_VOL:/var/lib/odoo")
  docker rm -f "$EPHEMERAL_NAME" >/dev/null 2>&1 || true
  # --user root: the shared filestore is written by root (docker exec installs),
  # the image's default 'odoo' user cannot create asset files there.
  docker run -d --rm --name "$EPHEMERAL_NAME" \
    --user root \
    --network "$NETWORK" \
    -p "${CAPTURE_PORT}:8069" \
    -e DB_PORT_5432_TCP_ADDR="$DB_HOST" \
    -e DB_PORT_5432_TCP_PORT="$DB_PORT" \
    -e DB_ENV_POSTGRES_USER="$DB_USER" \
    -e DB_ENV_POSTGRES_PASSWORD="$DB_PASS" \
    -v "$ROOT_DIR/enterprise:/mnt/extra-addons-enterprise:delegated" \
    -v "$ROOT_DIR/odoo-pro:/mnt/extra-addons-pro:delegated" \
    -v "$ROOT_DIR/conf:/etc/odoo:delegated" \
    "${DATA_MOUNT[@]}" \
    --entrypoint odoo \
    "$IMAGE" \
    -d "$DB" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --db-filter="^${DB}$" --http-port=8069 --workers=0 --max-cron-threads=0 \
    >/dev/null

  echo "   Esperando HTTP del servidor efimero..."
  for i in $(seq 1 60); do
    code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "${CAPTURE_URL}/web/login" 2>/dev/null || true)"
    [[ "$code" =~ ^(200|303)$ ]] && break
    docker ps --format '{{.Names}}' | grep -q "^${EPHEMERAL_NAME}$" || {
      echo "ERROR: el servidor efimero murio. Logs:" >&2
      docker logs "$EPHEMERAL_NAME" 2>&1 | tail -20 >&2 || true
      exit 1
    }
    sleep 2
  done
fi

# ─── 4. Capturas con Playwright ──────────────────────────────────────────────
echo "[3b/4] Capturando pantallas y armando el manual con Playwright..."
if [[ ! -d "$SCRIPT_DIR/node_modules/playwright" ]]; then
  echo "   Instalando dependencias de Node (playwright)..."
  ( cd "$SCRIPT_DIR" && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund )
fi
# capture.mjs writes the whole manual: img/, README.md, manual.html and
# manual.pdf. --out is the manual folder, not the image folder: the images go
# in <out>/img on their own.
node "$SCRIPT_DIR/capture.mjs" \
  --config="$CONFIG" \
  --base-url="$CAPTURE_URL" \
  --db="$DB" \
  --login=admin --password=admin \
  --out="$OUT_DIR" \
  --name="$MANUAL_NAME" \
  $HEADED

# Stop the throwaway server as soon as captures are done.
docker rm -f "$EPHEMERAL_NAME" >/dev/null 2>&1 || true

# ─── Limpieza ────────────────────────────────────────────────────────────────
if [[ "$KEEP_DB" == "false" ]]; then
  echo "Limpiando base ($DB)..."
  _drop_db "$DB"
else
  echo "Base '$DB' conservada (--keep-db)."
fi

echo ""
MD_NAME="README.md"
[[ "$MANUAL_NAME" != "manual" ]] && MD_NAME="${MANUAL_NAME}.md"
echo "✅ Manual generado: $OUT_DIR/${MANUAL_NAME}.pdf"
echo "   Markdown       : $OUT_DIR/$MD_NAME"
echo "   HTML           : $OUT_DIR/${MANUAL_NAME}.html"
echo "   Capturas       : $IMG_DIR"
