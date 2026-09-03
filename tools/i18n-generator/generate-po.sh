#!/bin/bash
# generate-po.sh — exporta el .po de un modulo con `odoo i18n export`.
# Ver README.md.
#
# Uso: ./generate-po.sh --module=X [--lang=es_DO] [--pot] [--db=] [--out=]
#      [--extra-modules=a,b] [--fresh] [--no-install] [--check] [--strict]
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "ERROR: .env no encontrado en $ROOT_DIR" >&2; exit 1
fi
source "$ROOT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_CONTAINER="odoo-db"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

MODULE=""
EXTRA_MODULES=""
LANG_CODE="es_DO"
DB=""
FRESH=false
DO_INSTALL=true
CHECK_ONLY=false
STRICT=false
OUT_OVERRIDE=""
POT=false

for arg in "$@"; do
  case "$arg" in
    --module=*)        MODULE="${arg#--module=}" ;;
    --extra-modules=*) EXTRA_MODULES="${arg#--extra-modules=}" ;;
    --lang=*)          LANG_CODE="${arg#--lang=}" ;;
    --db=*)            DB="${arg#--db=}" ;;
    --out=*)           OUT_OVERRIDE="${arg#--out=}" ;;
    --pot)             POT=true ;;
    --fresh)           FRESH=true ;;
    --no-install)      DO_INSTALL=false ;;
    --check)           CHECK_ONLY=true ;;
    --strict)          STRICT=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

[[ -z "$MODULE" ]] && { echo "ERROR: falta --module=<nombre>" >&2; exit 1; }

MODULE_DIR=""
for base in "$ROOT_DIR/odoo-pro" "$ROOT_DIR/odoo-pro/store-addons"; do
  [[ -f "$base/$MODULE/__manifest__.py" ]] && MODULE_DIR="$base/$MODULE" && break
done
[[ -z "$MODULE_DIR" ]] && { echo "ERROR: no encuentro el modulo '$MODULE' en odoo-pro" >&2; exit 1; }

CONTAINER_MODULE_DIR="/mnt/extra-addons-pro/${MODULE}"
[[ "$MODULE_DIR" == *"/store-addons/"* ]] && CONTAINER_MODULE_DIR="/mnt/extra-addons-pro/store-addons/${MODULE}"

[[ -z "$DB" ]] && DB="i18n_v19_${MODULE}"

if $POT; then
  EXPORT_LANG="pot"
  OUT_FILE="${OUT_OVERRIDE:-$MODULE_DIR/i18n/${MODULE}.pot}"
else
  EXPORT_LANG="$LANG_CODE"
  OUT_FILE="${OUT_OVERRIDE:-$MODULE_DIR/i18n/${LANG_CODE}.po}"
fi

INSTALL_MODULES="$MODULE"
[[ -n "$EXTRA_MODULES" ]] && INSTALL_MODULES="$MODULE,$EXTRA_MODULES"

CONF="/tmp/odoo_i18n_${MODULE}.conf"
TMP_PO="/tmp/${MODULE}_${EXPORT_LANG}.po"

echo "======================================================"
echo " i18n: exportar el .po con Odoo"
echo " Modulo  : $MODULE"
echo " Idioma  : $EXPORT_LANG"
echo " DB      : $DB"
echo " Salida  : ${OUT_FILE#$ROOT_DIR/}"
echo "======================================================"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: el daemon de Docker no responde. Abre Docker Desktop y reintenta." >&2
  exit 1
fi
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: contenedor '$CONTAINER' no esta corriendo (docker-compose up -d)." >&2
  exit 1
fi

# solo lineas de error del log de Odoo: el "(ERROR/3)" de docutils no es un fallo
_odoo() {
  local log status
  log="$(mktemp -t odoo_i18n_log)"
  docker exec "$CONTAINER" "$@" >"$log" 2>&1
  status=$?
  if grep -qE "^[0-9]{4}-[0-9]{2}-[0-9]{2} .*(ERROR|CRITICAL) " "$log"; then
    grep -E "^[0-9]{4}-[0-9]{2}-[0-9]{2} .*(ERROR|CRITICAL) " "$log" | head -20
    status=1
  fi
  rm -f "$log"
  return $status
}

_db_exists() {
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname='$DB'" 2>/dev/null | grep -q 1
}

_drop_db() {
  docker exec "$DB_CONTAINER" bash -c "
    PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity
           WHERE datname = '$DB' AND pid <> pg_backend_pid();\" >/dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      --if-exists '$DB' 2>/dev/null || true" 2>/dev/null || true
}

# i18n export solo acepta -c y el odoo.conf del contenedor no trae db_host
docker exec "$CONTAINER" bash -lc "sed -e 's|^\[options\]|[options]\ndb_host = $DB_HOST\ndb_port = $DB_PORT\ndb_user = $DB_USER\ndb_password = $DB_PASS|' /etc/odoo/odoo.conf > $CONF" \
  || { echo "ERROR: no pude armar $CONF en el contenedor." >&2; exit 1; }

$FRESH && { echo "[1/5] Borrando '$DB' (--fresh)..."; _drop_db; }

if ! _db_exists; then
  if ! $DO_INSTALL; then
    echo "ERROR: la DB '$DB' no existe y se paso --no-install." >&2; exit 1
  fi
  echo "[1/5] Creando '$DB' e instalando '$INSTALL_MODULES'..."
  _odoo odoo -c "$CONF" -d "$DB" \
    --without-demo=all --log-level=warn --stop-after-init --no-http \
    -i "$INSTALL_MODULES" \
    || { echo "ERROR: la instalacion fallo." >&2; exit 1; }
else
  echo "[1/5] Reusando '$DB'; actualizando '$MODULE'..."
  _odoo odoo -c "$CONF" -d "$DB" \
    --log-level=warn --stop-after-init --no-http -u "$MODULE" \
    || { echo "ERROR: el update fallo (vista o campo roto?)." >&2; exit 1; }
fi

if ! $POT; then
  echo "[2/5] Activando y cargando el idioma $LANG_CODE..."
  docker exec "$CONTAINER" odoo i18n loadlang -c "$CONF" -d "$DB" -l "$LANG_CODE" \
    >/dev/null 2>&1 || { echo "ERROR: loadlang $LANG_CODE fallo." >&2; exit 1; }
fi

if ! $POT && [[ -f "$OUT_FILE" ]]; then
  echo "[3/5] Importando el .po del repo con --overwrite (lo editado manda)..."
  docker exec "$CONTAINER" odoo i18n import -c "$CONF" -d "$DB" \
    -l "$LANG_CODE" -w "${CONTAINER_MODULE_DIR}/i18n/$(basename "$OUT_FILE")" \
    >/dev/null 2>&1 || echo "   aviso: el import fallo, se exporta lo que tenga la base"
else
  echo "[3/5] Sin .po previo en el repo; se exporta lo que traiga la base."
fi

echo "[4/5] odoo i18n export -l $EXPORT_LANG..."
_odoo odoo i18n export -c "$CONF" -d "$DB" \
  -l "$EXPORT_LANG" -o "$TMP_PO" "$MODULE" \
  || { echo "ERROR: el export fallo." >&2; exit 1; }
docker exec "$CONTAINER" test -s "$TMP_PO" \
  || { echo "ERROR: Odoo no escribio $TMP_PO." >&2; exit 1; }

if $CHECK_ONLY; then
  LOCAL_PO="$(mktemp -t "${MODULE}.po")"
else
  mkdir -p "$(dirname "$OUT_FILE")"
  LOCAL_PO="$OUT_FILE"
fi
docker cp "${CONTAINER}:${TMP_PO}" "$LOCAL_PO" >/dev/null
docker exec "$CONTAINER" rm -f "$TMP_PO" "$CONF"

echo "[5/5] Terminos sin traducir:"
python3 "$SCRIPT_DIR/report_untranslated.py" "$LOCAL_PO"
STATUS=$?
$STRICT || STATUS=0

if $CHECK_ONLY; then
  echo ""
  echo "--check: no se escribio nada en el repo ($LOCAL_PO)"
else
  echo ""
  echo "Archivo escrito por Odoo: ${OUT_FILE#$ROOT_DIR/}"
  echo "Traduce los msgstr vacios y vuelve a correr el script para reformatear."
fi
exit $STATUS
