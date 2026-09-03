#!/bin/bash
# Builds the payroll-sync bench: a master database holding the module, and a
# client instance running nothing but the payroll localisation.
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

REBUILD=1
[[ "${1:-}" == "--no-rebuild" ]] && REBUILD=0

if [[ $REBUILD -eq 1 ]]; then
  echo "[1/5] Rebuilding both databases"
  stop_servers
  drop_db "$MASTER_DB"
  drop_db "$CLIENT_DB"
  odoo_cli "$MASTER_DB" -i l10n_do_hr_payroll_sync --without-demo=all --stop-after-init \
    --http-port=8199 --log-level=warn >/dev/null
  odoo_cli "$CLIENT_DB" -i l10n_do_hr_payroll --without-demo=all --stop-after-init \
    --http-port=8199 --log-level=warn >/dev/null
else
  echo "[1/5] Reusing the existing databases"
  stop_servers
fi

echo "[2/5] Granting the remote groups and minting the API key on the client"
put_args '{"name": "payroll sync e2e"}'
CLIENT_KEY="$(run_py "$CLIENT_DB" setup_client.py | sed -n 's/^KEY=//p' | tail -1)"
[[ -n "$CLIENT_KEY" ]] || { echo "could not mint the client api key"; exit 1; }

echo "[3/5] Registering the client on the master"
put_args "$(printf '{"url": "%s", "db": "%s", "key": "%s", "login": "admin", "name": "E2E client"}' \
  "$CLIENT_INTERNAL_URL" "$CLIENT_DB" "$CLIENT_KEY")"
PROJECT_ID="$(run_py "$MASTER_DB" setup_master.py | sed -n 's/^PROJECT_ID=//p' | tail -1)"
[[ -n "$PROJECT_ID" ]] || { echo "could not register the client"; exit 1; }

echo "[4/5] Starting the client server on :$CLIENT_PORT"
start_server "$CLIENT_NAME" "$CLIENT_DB" "$CLIENT_PORT"
wait_http "$CLIENT_URL" || { echo "the client never answered"; exit 1; }

echo "[5/5] Storing the credentials"
cat > "$(dirname "${BASH_SOURCE[0]}")/creds.env" <<EOC
CLIENT_KEY=$CLIENT_KEY
PROJECT_ID=$PROJECT_ID
EOC

echo
echo "Master database : $MASTER_DB (no server, everything runs through odoo shell)"
echo "Client instance : $CLIENT_URL  ($CLIENT_DB, only l10n_do_hr_payroll installed)"
echo "project.project : id $PROJECT_ID"
