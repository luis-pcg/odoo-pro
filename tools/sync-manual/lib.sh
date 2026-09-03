#!/bin/bash
# Shared plumbing for the three-instance payroll-sync manual environment.
# Sourced by setup.sh / generate.sh; not meant to be executed on its own.
#
#   padre  -> the master: the only one with l10n_do_hr_payroll_sync installed
#   hija1  -> a client: only l10n_do_hr_payroll, it installs nothing extra
#   hija2  -> another client, same thing
#
# Everything runs in its own container on the shared docker network, so the
# traffic captured in the manual is real RPC between three live databases.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$ROOT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

INSTANCES=(padre hija1 hija2)

db_of()        { echo "manual_$1"; }
container_of() { echo "syncmanual_$1"; }

port_of() {
  case "$1" in
    padre) echo 8101 ;;
    hija1) echo 8102 ;;
    hija2) echo 8103 ;;
  esac
}

# The master carries the sync module; the clients carry nothing but payroll.
modules_of() {
  case "$1" in
    padre) echo "l10n_do_hr_payroll_sync" ;;
    *)     echo "l10n_do_hr_payroll" ;;
  esac
}

role_of() {
  case "$1" in
    padre) echo "master" ;;
    *)     echo "client" ;;
  esac
}

company_of() {
  case "$1" in
    padre) echo "PROGRESSA (Casa Matriz)" ;;
    hija1) echo "Distribuidora Acme, SRL" ;;
    hija2) echo "Ferretería Bella Vista, SRL" ;;
  esac
}

# Host URL: what the browser (and the manual reader) uses.
url_of() { echo "http://localhost:$(port_of "$1")"; }

# Internal URL: what the instances use to reach each other inside the docker
# network. The host port mapping does not exist from inside a container.
internal_url_of() { echo "http://$(container_of "$1"):8069"; }

odoo_cli() {
  local inst="$1"; shift
  docker exec "$CONTAINER" odoo \
    -d "$(db_of "$inst")" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    "$@"
}

odoo_shell() {
  # Reads the python snippet from stdin.
  local inst="$1"; shift
  docker exec -i "$CONTAINER" odoo shell \
    -d "$(db_of "$inst")" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --log-level=error --no-http "$@"
}

run_py() {
  # run_py <instance> <script-name>; echoes the script's stdout
  local inst="$1" script="$2"
  odoo_shell "$inst" < "$HERE/py/$script" 2>/dev/null | tr -d '\r'
}

put_args() {
  # Hands a JSON argument file to the next `odoo shell` snippet: the container
  # cannot see host environment variables, so arguments travel through a file.
  printf '%s' "$1" | docker exec -i "$CONTAINER" tee /tmp/sync_manual_args.json >/dev/null
}

psql_q() {
  # LC_ALL=C keeps the image's missing locales from drowning the output.
  local db="$1" sql="$2"
  docker exec -e LC_ALL=C -i "$DB_HOST" psql -U "$DB_USER" -d "$db" -At -F'|' -c "$sql" 2>/dev/null
}

drop_db() {
  local db="$1"
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      --if-exists '$db'" >/dev/null 2>&1 || true
}

start_server() {
  local inst="$1"
  local name db port image network data_vol
  name="$(container_of "$inst")"; db="$(db_of "$inst")"; port="$(port_of "$inst")"
  image="$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')"
  network="$(docker inspect "$CONTAINER" \
    --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')"
  data_vol="$(docker inspect "$CONTAINER" \
    --format '{{range .Mounts}}{{if eq .Destination "/var/lib/odoo"}}{{.Name}}{{end}}{{end}}')"
  local mount=()
  [[ -n "$data_vol" ]] && mount=(-v "$data_vol:/var/lib/odoo")

  docker rm -f "$name" >/dev/null 2>&1 || true
  # No cron threads: every delivery in the manual is triggered on purpose, so
  # the screenshots always show the state the text describes.
  docker run -d --rm --name "$name" \
    --user root \
    --network "$network" \
    -p "${port}:8069" \
    -e DB_PORT_5432_TCP_ADDR="$DB_HOST" \
    -e DB_PORT_5432_TCP_PORT="$DB_PORT" \
    -e DB_ENV_POSTGRES_USER="$DB_USER" \
    -e DB_ENV_POSTGRES_PASSWORD="$DB_PASS" \
    -v "$ROOT_DIR/enterprise:/mnt/extra-addons-enterprise:delegated" \
    -v "$ROOT_DIR/odoo-pro:/mnt/extra-addons-pro:delegated" \
    -v "$ROOT_DIR/conf:/etc/odoo:delegated" \
    "${mount[@]}" \
    --entrypoint odoo \
    "$image" \
    -d "$db" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --db-filter="^${db}$" --http-port=8069 --workers=0 --max-cron-threads=0 \
    >/dev/null
}

wait_http() {
  local url="$1" tries="${2:-60}" code
  for _ in $(seq 1 "$tries"); do
    code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "${url}/web/login" 2>/dev/null || true)"
    [[ "$code" =~ ^(200|303)$ ]] && return 0
    sleep 2
  done
  return 1
}

stop_servers() {
  for inst in "${INSTANCES[@]}"; do
    docker rm -f "$(container_of "$inst")" >/dev/null 2>&1 || true
  done
}
