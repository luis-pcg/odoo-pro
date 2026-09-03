#!/bin/bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

stop_servers
if [[ "${1:-}" == "--drop-db" ]]; then
  drop_db "$MASTER_DB"
  drop_db "$CLIENT_DB"
  rm -f "$(dirname "${BASH_SOURCE[0]}")/creds.env"
  echo "Databases dropped."
else
  echo "Servers stopped. Add --drop-db to remove the databases too."
fi
