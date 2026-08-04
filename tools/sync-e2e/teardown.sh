#!/bin/bash
# Stop the two test servers. Add --drop-db to also delete the databases.

source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib.sh"

stop_servers
echo "Servers stopped."

for arg in "$@"; do
  if [[ "$arg" == "--drop-db" ]]; then
    drop_db "$MASTER_DB"
    drop_db "$CLIENT_DB"
    echo "Databases $MASTER_DB and $CLIENT_DB dropped."
  fi
done
