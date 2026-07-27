#!/bin/bash
# setup_v19_l10n_do_hr_payroll_liquidation.sh
#
# Crea y configura una base de datos NUEVA (sin datos demo) con TODO lo necesario
# para el flujo completo de Liquidación por Desvinculación en Odoo 19:
#
#   1. Crea la DB v19_l10n_do_hr_payroll_liquidation e instala
#      l10n_do_hr_payroll_liquidation + l10n_do_accounting
#      (arrastra hr_payroll, l10n_do_hr_payroll, l10n_do, etc.).
#   2. Siembra (con el MISMO seed del generador de manual):
#      - Compañía RD: país, moneda DOP, riesgo laboral, RNC + plan contable DO.
#      - Calendario laboral RD 44h, estructura base con diario de nómina.
#      - Dos empleados FULL configurados (cédula, NSS, contrato/versión, salario,
#        causa de salida): Juan Pérez (RD$60,000, 3a 8m) y Ana Ruiz (RD$30,000, 3m).
#      - Historial de 12 nóminas validadas de Juan (para "Cargar Historial").
#      - Liquidación de Juan CALCULADA + CONFIRMADA vía asistente de lote
#        (genera la nómina de liquidación sin retenciones); Ana en CALCULADO.
#   3. Deja el admin en admin/admin y COMMITEA (DB lista para usar via web).
#
# Uso:
#   ./setup_v19_l10n_do_hr_payroll_liquidation.sh                # crea DB nueva
#   ./setup_v19_l10n_do_hr_payroll_liquidation.sh --db=mi_db     # nombre propio
#   ./setup_v19_l10n_do_hr_payroll_liquidation.sh --recreate     # borra y recrea
#   ./setup_v19_l10n_do_hr_payroll_liquidation.sh --skip-install # solo sembrar
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="l10n_do_hr_payroll_liquidation,l10n_do_accounting"
SEED="$SCRIPT_DIR/tools/manual-generator/configs/l10n_do_hr_payroll_liquidation.seed.py"

DB_NAME="v19_l10n_do_hr_payroll_liquidation"
RECREATE=false
SKIP_INSTALL=false
for arg in "$@"; do
  case "$arg" in
    --recreate)     RECREATE=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    --db=*)         DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

[[ -f "$SEED" ]] || { echo "ERROR: no existe el seed $SEED" >&2; exit 1; }
ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Setup liquidación dominicana — flujo completo"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo " Módulos    : $MODULES"
echo "======================================================"

wait_for_db() {
  docker exec "$CONTAINER" bash -lc "
    for i in \$(seq 1 30); do
      if PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
        echo 'Postgres OK (intento '\$i')'; exit 0
      fi
      sleep 2
    done
    echo 'ERROR: Postgres no respondio tras 30 intentos' >&2; exit 1
  "
}

db_exists() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" \
    | grep -q 1
}

if ! $SKIP_INSTALL; then
  echo "→ Esperando a Postgres..."
  wait_for_db || exit 1

  if db_exists; then
    if $RECREATE; then
      echo "→ DB $DB_NAME existe, eliminando (--recreate)..."
      docker exec "$CONTAINER" bash -lc "
        PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
          \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid()\" >/dev/null
        PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
      " || { echo 'ERROR eliminando la DB' >&2; exit 1; }
    else
      echo "ERROR: la DB $DB_NAME ya existe. Usa --recreate para reemplazarla o --skip-install para solo sembrar." >&2
      exit 1
    fi
  fi

  echo "→ Creando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULES sin datos demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los modulos' >&2; exit 1; }
fi

echo "→ Sembrando (mismo seed del generador de manual)..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" < "$SEED"
STATUS=$?

if [[ $STATUS -eq 0 ]]; then
  echo "→ Fijando admin/admin..."
  docker exec -i "$CONTAINER" bash -lc "
    odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      --no-http --max-cron-threads=0 --workers=0 --log-level=error
  " <<'PYEOF'
env.ref('base.user_admin').password = 'admin'
env.cr.commit()
print('admin/admin listo')
PYEOF
fi

echo
if [[ $STATUS -eq 0 ]]; then
  echo "======================================================"
  echo " DB lista: $DB_NAME"
  echo " URL      : http://localhost:${ODOO_PORT:-8092}/odoo  (admin/admin)"
  echo " Nómina → Recibos → Liquidaciones"
  echo " Re-sembrar sin reinstalar: $0 --db=$DB_NAME --skip-install"
  echo "======================================================"
else
  echo "ERROR: el sembrado fallo (exit $STATUS). DB conservada para inspeccion: $DB_NAME"
fi
exit $STATUS
