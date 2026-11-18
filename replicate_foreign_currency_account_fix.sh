#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
DB_NAME="${1:-v19_fx_account_fix}"
SEED="$SCRIPT_DIR/replicate_foreign_currency_account_fix_seed.py"
VERIFY="$SCRIPT_DIR/replicate_foreign_currency_account_fix_verify.py"
ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"
PSQL="PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -P pager=off"

shell() {
  docker exec -i "$CONTAINER" bash -lc "odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS --no-http --max-cron-threads=0 --workers=0 --log-level=error"
}

echo "→ Recreating $DB_NAME (account + l10n_do)"
docker exec "$CONTAINER" bash -lc "
  PGPASSWORD=$DB_PASS dropdb --force --if-exists -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME &&
  PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME &&
  odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS -i account,l10n_do --without-demo=all \
    --stop-after-init --max-cron-threads=0 --workers=0 --log-level=error"

echo "→ Seeding the Escala Solar scenario"
shell < "$SEED"

echo "→ Odoo blocks the currency change through the ORM (bug reproduced)"
shell <<'PYEOF'
from odoo.exceptions import UserError
caja = env["account.account"].search([("code", "=", "110199002")])
try:
    caja.currency_id = env.ref("base.USD")
    print("NOT REPRODUCED")
except UserError as e:
    print("REPRODUCED:", e)
env.cr.rollback()
PYEOF

docker cp "$SCRIPT_DIR/fix_foreign_currency_accounts.sql" "$CONTAINER:/tmp/fix_foreign_currency_accounts.sql"

echo "→ SQL dry run"
docker exec "$CONTAINER" bash -lc "$PSQL -f /tmp/fix_foreign_currency_accounts.sql"

echo "→ Verify dry run left nothing applied"
docker exec "$CONTAINER" bash -lc "$PSQL -tAc \"SELECT COUNT(*) FROM account_account WHERE currency_id IS NOT NULL AND code_store->>'1' LIKE '%99%'\""

echo "→ SQL apply"
docker exec "$CONTAINER" bash -lc "$PSQL -v apply=true -f /tmp/fix_foreign_currency_accounts.sql"

echo "→ Functional verification through the ORM"
shell < "$VERIFY"

echo "→ Second apply is a no-op"
docker exec "$CONTAINER" bash -lc "$PSQL -v apply=true -f /tmp/fix_foreign_currency_accounts.sql" | grep -E "^(UPDATE|SELECT|COMMITTED)"
