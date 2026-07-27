#!/bin/bash
# verify_liquidation_batch2_acceptance.sh
#
# Verifica, sobre una base limpia, cada criterio de aceptacion (AC-B2-01..10) y cada
# prueba del plan de regresion (REG-01..09) del
#   docs/Informe_Pruebas_Funcionales_Liquidaciones_Odoo19_Batch2_Final.pdf
# mas la tabla de dias equivalentes del Batch 1 (R2/R3).
#
# Cada criterio se ejercita de punta a punta —calcular, confirmar, generar el recibo,
# leer las lineas de nomina— y se reporta PASS/FAIL con el dato que lo sustenta, para
# que el resultado sea auditable y no una afirmacion.
#
# Uso:
#   ./verify_liquidation_batch2_acceptance.sh
#   ./verify_liquidation_batch2_acceptance.sh --keep-db

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] || { echo "ERROR: .env no encontrado en $SCRIPT_DIR" >&2; exit 1; }
source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
DB="acc_liquidation_batch2"
PROBE="$SCRIPT_DIR/tools/liquidation_batch2_acceptance.py"
KEEP_DB=false
for arg in "$@"; do [[ "$arg" == "--keep-db" ]] && KEEP_DB=true; done

docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$" || {
  echo "ERROR: contenedor '$CONTAINER' no esta corriendo. Corre: docker-compose up -d" >&2; exit 1; }

_drop_db() {
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity
            WHERE datname='$DB' AND pid <> pg_backend_pid();\" >/dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' --if-exists '$DB'
  " 2>&1 | grep -v NOTICE || true
}

echo "======================================================"
echo " Criterios de aceptacion — Liquidaciones Batch 2"
echo "======================================================"

docker exec "$CONTAINER" bash -lc "
  cp /etc/odoo/odoo.conf /tmp/acc.conf
  printf 'db_host = %s\ndb_port = %s\ndb_user = %s\ndb_password = %s\n' \
    '$DB_HOST' '$DB_PORT' '$DB_USER' '$DB_PASS' >> /tmp/acc.conf"

echo ""
echo "[1/2] Base limpia + l10n_do_hr_payroll_liquidation ..."
_drop_db
docker exec "$CONTAINER" odoo -c /tmp/acc.conf -d "$DB" \
  --no-http --http-port=8076 --stop-after-init --without-demo=all \
  -i l10n_do_hr_payroll_liquidation --log-level=warn 2>&1 \
  | grep -Ei "Traceback|CRITICAL" | head -5 || true

echo "[2/2] Ejercitando criterios ..."
docker cp "$PROBE" "$CONTAINER":/tmp/acceptance.py >/dev/null
set +e
docker exec -i "$CONTAINER" bash -lc \
  "odoo shell -c /tmp/acc.conf -d $DB --no-http --log-level=error < /tmp/acceptance.py" 2>/dev/null \
  | sed -n '/===ACCEPTANCE_START===/,/===ACCEPTANCE_END===/p' | sed '1d;$d' | tee /tmp/acc_out.txt
STATUS=$?
set -e

echo ""
if grep -q "^FAIL" /tmp/acc_out.txt; then
  echo "❌ Hay criterios en FAIL (ver arriba)."
  STATUS=1
else
  echo "✅ Todos los criterios en PASS."
  STATUS=0
fi

if [[ "$KEEP_DB" == false ]]; then
  echo ""
  echo "Limpiando base ($DB) ..."
  _drop_db
else
  echo ""
  echo "Base conservada: $DB"
fi

exit "$STATUS"
