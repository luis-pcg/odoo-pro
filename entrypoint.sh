#!/bin/bash

set -e

if [ -v PASSWORD_FILE ]; then
    PASSWORD="$(< $PASSWORD_FILE)"
fi

# set the postgres database host, port, user and password according to the environment
# and pass them as arguments to the odoo process if not present in the config file
: ${HOST:=${DB_PORT_5432_TCP_ADDR:='db'}}
: ${PORT:=${DB_PORT_5432_TCP_PORT:=5432}}
: ${USER:=${DB_ENV_POSTGRES_USER:=${POSTGRES_USER:='odoo'}}}
: ${PASSWORD:=${DB_ENV_POSTGRES_PASSWORD:=${POSTGRES_PASSWORD:='odoo'}}}

DB_ARGS=()
function check_config() {
    param="$1"
    value="$2"
    if grep -q -E "^\s*\b${param}\b\s*=" "$ODOO_RC" ; then       
        value=$(grep -E "^\s*\b${param}\b\s*=" "$ODOO_RC" |cut -d " " -f3|sed 's/["\n\r]//g')
    fi;
    DB_ARGS+=("--${param}")
    DB_ARGS+=("${value}")
}
check_config "db_host" "$HOST"
check_config "db_port" "$PORT"
check_config "db_user" "$USER"
check_config "db_password" "$PASSWORD"

# Fija web.base.url = http://localhost:$ODOO_PORT (y web.base.url.freeze = True)
# en todas las bases de datos existentes, para que los logins no lo reescriban
# con el host de la peticion (p. ej. el gateway de docker 172.20.0.1).
function fix_web_base_url() {
    [ -n "${ODOO_PORT:-}" ] || return 0
    local url="http://localhost:${ODOO_PORT}"
    local dbs db
    dbs=$(PGPASSWORD="$PASSWORD" psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -tAc \
        "SELECT datname FROM pg_database WHERE NOT datistemplate AND datname <> 'postgres'" 2>/dev/null) || return 0
    for db in $dbs; do
        if PGPASSWORD="$PASSWORD" psql -h "$HOST" -p "$PORT" -U "$USER" -d "$db" -q 2>/dev/null <<EOSQL
DO \$\$
BEGIN
    IF to_regclass('public.ir_config_parameter') IS NULL THEN
        RETURN;
    END IF;
    UPDATE ir_config_parameter SET value = '${url}', write_date = now() WHERE key = 'web.base.url';
    IF NOT FOUND THEN
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('web.base.url', '${url}', now(), now());
    END IF;
    UPDATE ir_config_parameter SET value = 'True', write_date = now() WHERE key = 'web.base.url.freeze';
    IF NOT FOUND THEN
        INSERT INTO ir_config_parameter (key, value, create_date, write_date)
        VALUES ('web.base.url.freeze', 'True', now(), now());
    END IF;
END
\$\$;
EOSQL
        then
            echo "web.base.url -> ${url} (freeze=True) en '${db}'"
        fi
    done
    return 0
}

case "$1" in
    -- | odoo)
        shift
        if [[ "$1" == "scaffold" ]] ; then
            exec /usr/bin/python3 -m debugpy --listen 0.0.0.0:3001 /usr/bin/odoo "$@" "${DB_ARGS[@]}"
        else
            wait-for-psql.py ${DB_ARGS[@]} --timeout=30
            fix_web_base_url
            exec /usr/bin/python3 -m debugpy --listen 0.0.0.0:3001 /usr/bin/odoo "$@" "${DB_ARGS[@]}"
        fi
        ;;
    -*)
        wait-for-psql.py ${DB_ARGS[@]} --timeout=30
        fix_web_base_url
        exec /usr/bin/python3 -m debugpy --listen 0.0.0.0:3001 /usr/bin/odoo "$@" "${DB_ARGS[@]}"
        ;;
    *)
        exec "$@"
esac

exit 1