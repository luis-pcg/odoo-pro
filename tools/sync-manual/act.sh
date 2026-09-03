#!/bin/bash
# Side effects the manual needs between screenshots.
#
#   ./act.sh run   <instancia> <script.py> ['{"json": "args"}']
#   ./act.sh stop  <instancia>      apaga el contenedor (hija caída)
#   ./act.sh start <instancia>      lo vuelve a levantar y espera al HTTP
#   ./act.sh restart <instancia>    lo recrea: necesario tras cambiar permisos
#   ./act.sh restrict <instancia>   el padre pasa a hablarle con un usuario de
#                                   API sin ajustes técnicos, como un cliente real
#   ./act.sh unrestrict <instancia> vuelve al usuario con todos los permisos
#
# Called by capture.mjs through a flow's "exec" list, so each screenshot is
# taken right after the action it illustrates.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

cmd="${1:-}"; shift || true

case "$cmd" in
  run)
    inst="$1"; script="$2"; json="${3:-{\}}"
    put_args "$json"
    run_py "$inst" "$script"
    ;;
  stop)
    docker rm -f "$(container_of "$1")" >/dev/null 2>&1 || true
    echo "stopped $1"
    ;;
  start|restart)
    start_server "$1"
    wait_http "$(url_of "$1")" || { echo "ERROR: $1 no levantó" >&2; exit 1; }
    echo "$cmd $1"
    ;;
  restrict)
    # Mint the restricted key on the client and point the master at it in one
    # go: capture.mjs cannot carry a value from one exec line to the next.
    inst="$1"
    put_args '{"action": "restricted_api_user"}'
    key="$(run_py "$inst" edit_client.py | sed -n 's/^KEY=//p' | tail -1)"
    [[ -n "$key" ]] || { echo "ERROR: sin llave restringida en $inst" >&2; exit 1; }
    put_args "$(printf '{"action": "set_api_user", "name": "%s", "login": "sync_api", "key": "%s"}' \
      "$(company_of "$inst")" "$key")"
    run_py padre edit_master.py
    ;;
  unrestrict)
    inst="$1"
    source "$HERE/creds.env"
    eval "key=\${API_KEY_${inst}}"
    put_args "$(printf '{"action": "set_api_user", "name": "%s", "login": "admin", "key": "%s"}' \
      "$(company_of "$inst")" "$key")"
    run_py padre edit_master.py
    ;;
  *)
    echo "uso: act.sh {run <instancia> <script.py> [json] | stop|start|restart|restrict|unrestrict <instancia>}" >&2
    exit 2
    ;;
esac
