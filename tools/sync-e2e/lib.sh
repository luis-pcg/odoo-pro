#!/bin/bash
# Shared plumbing for the payroll-sync end-to-end environment.
# Sourced by setup.sh / run-tests.sh; not meant to be executed on its own.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

MASTER_DB="sync_master"
CLIENT_DB="sync_client"
MASTER_PORT=8074
CLIENT_PORT=8075
MASTER_NAME="payrollsync_master"
CLIENT_NAME="payrollsync_client"

# Inside the docker network the two servers reach each other by container name
# on the internal port, not through the host port mapping.
MASTER_INTERNAL_URL="http://${MASTER_NAME}:8069"
CLIENT_INTERNAL_URL="http://${CLIENT_NAME}:8069"
MASTER_URL="http://localhost:${MASTER_PORT}"
CLIENT_URL="http://localhost:${CLIENT_PORT}"

odoo_cli() {
  local db="$1"; shift
  docker exec "$CONTAINER" odoo \
    -d "$db" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    "$@"
}

put_args() {
  # put_args '<json>' — hands parameters to the python helpers, which read
  # /tmp/sync_e2e_args.json inside the container.
  docker exec -i "$CONTAINER" bash -c "cat > /tmp/sync_e2e_args.json" <<<"$1"
}

run_py() {
  # run_py <db> <helper.py> — executes a helper from py/ through odoo shell.
  local db="$1" script="$2"
  odoo_shell "$db" < "$(dirname "${BASH_SOURCE[0]}")/py/$script"
}

odoo_shell() {
  # Reads the python snippet from stdin.
  local db="$1"; shift
  docker exec -i "$CONTAINER" odoo shell \
    -d "$db" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --log-level=error --no-http "$@"
}

psql_q() {
  # LC_ALL=C: the image has no locales installed and every exec otherwise
  # prints a wall of perl locale warnings that drown the actual output.
  local db="$1"; shift
  docker exec -e LC_ALL=C -e LANG=C "$CONTAINER" bash -c \
    "PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' -d '$db' -tAc \"$1\"" \
    2>/dev/null
}

drop_db() {
  local db="$1"
  docker exec "$CONTAINER" bash -c "
    PGPASSWORD='$DB_PASS' psql -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' postgres \
      -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity
           WHERE datname = '$db' AND pid <> pg_backend_pid();\" >/dev/null 2>&1 || true
    PGPASSWORD='$DB_PASS' dropdb -h '$DB_HOST' -p '$DB_PORT' -U '$DB_USER' \
      --if-exists '$db' 2>/dev/null || true" 2>/dev/null || true
}

start_server() {
  # start_server <container-name> <db> <host-port>
  local name="$1" db="$2" port="$3"
  local image network data_vol
  image="$(docker inspect "$CONTAINER" --format '{{.Config.Image}}')"
  network="$(docker inspect "$CONTAINER" \
    --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{end}}' | awk '{print $1}')"
  data_vol="$(docker inspect "$CONTAINER" \
    --format '{{range .Mounts}}{{if eq .Destination "/var/lib/odoo"}}{{.Name}}{{end}}{{end}}')"
  local mount=()
  [[ -n "$data_vol" ]] && mount=(-v "$data_vol:/var/lib/odoo")

  docker rm -f "$name" >/dev/null 2>&1 || true
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
  # wait_http <url> [tries]
  local url="$1" tries="${2:-60}" code
  for _ in $(seq 1 "$tries"); do
    code="$(curl -sS -m 5 -o /dev/null -w '%{http_code}' "${url}/web/login" 2>/dev/null || true)"
    [[ "$code" =~ ^(200|303)$ ]] && return 0
    sleep 2
  done
  return 1
}

stop_servers() {
  # Only the client runs a server: the master pushes, it is never called.
  docker rm -f "$MASTER_NAME" "$CLIENT_NAME" >/dev/null 2>&1 || true
}
