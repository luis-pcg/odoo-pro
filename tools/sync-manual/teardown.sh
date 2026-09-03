#!/bin/bash
# Stop the three manual servers. Add --drop-db to delete their databases too.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

stop_servers
echo "Servidores detenidos."

for arg in "$@"; do
  if [[ "$arg" == "--drop-db" ]]; then
    for inst in "${INSTANCES[@]}"; do
      drop_db "$(db_of "$inst")"
      echo "Base $(db_of "$inst") eliminada."
    done
  fi
done
