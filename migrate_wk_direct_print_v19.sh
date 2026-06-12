#!/bin/bash
# migrate_wk_direct_print_v19.sh
#
# Migra una base de datos v19 de los modulos legados de impresion directa de
# Webkul (wk_odoo_directly_print_reports y, si esta, product_label_for_zebra_printer)
# al modulo nuevo report_direct_print.
#
# El trabajo pesado lo hacen los hooks del modulo nuevo:
#   pre_init_hook  -> snapshot de las tablas legadas + desinstalacion limpia
#                     de los modulos legados via upgrade-util
#   post_init_hook -> recreacion de impresoras / plantillas / configuracion
#                     de reportes desde los snapshots
#
# Este script solo orquesta: pre-chequeo, instalacion, post-chequeo.
# Requiere que upgrade-util este en el upgrade-path del Odoo del contenedor.
#
# Uso:
#   ./migrate_wk_direct_print_v19.sh --db=mi_db             # migra
#   ./migrate_wk_direct_print_v19.sh --db=mi_db --dry-run   # solo pre-chequeo
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="report_direct_print"
LEGACY_MODULES="wk_odoo_directly_print_reports product_label_for_zebra_printer"
LEGACY_TABLES="wk_printer_printer report_template"
SNAPSHOT_TABLES="_report_direct_print_migr_printers _report_direct_print_migr_templates _report_direct_print_migr_reports"

DB_NAME=""
DRY_RUN=false
for arg in "$@"; do
  case "$arg" in
    --db=*)    DB_NAME="${arg#--db=}" ;;
    --dry-run) DRY_RUN=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done
if [[ -z "$DB_NAME" ]]; then
  echo "ERROR: falta --db=NOMBRE (base de datos a migrar)" >&2
  echo "Uso: $0 --db=NOMBRE [--dry-run]" >&2
  exit 2
fi

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Migracion impresion directa -> $MODULE"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
$DRY_RUN && echo " Modo       : DRY-RUN (solo pre-chequeo)"
echo "======================================================"

# ── Helpers psql (mismo patron de acceso que setup_v19_l10n_do_hr_payroll.sh) ──
psql_value() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $DB_NAME -tAc \"$1\""
}

db_exists() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" \
    | grep -q 1
}

table_exists() {
  [[ "$(psql_value "SELECT to_regclass('public.$1') IS NOT NULL")" == "t" ]]
}

table_count() {
  if table_exists "$1"; then
    psql_value "SELECT count(*) FROM $1"
  else
    echo "n/a (tabla no existe)"
  fi
}

column_exists() {
  [[ "$(psql_value "SELECT count(*) FROM information_schema.columns WHERE table_name='$1' AND column_name='$2'")" == "1" ]]
}

module_state() {
  local state
  state="$(psql_value "SELECT state FROM ir_module_module WHERE name='$1'")"
  echo "${state:-no registrado}"
}

configured_reports_count() {
  if column_exists ir_actions_report report_user_action; then
    psql_value "SELECT count(*) FROM ir_actions_report WHERE report_user_action='send_to_printer'"
  else
    echo "n/a (columna no existe)"
  fi
}

if ! db_exists; then
  echo "ERROR: la base de datos $DB_NAME no existe en $DB_HOST:$DB_PORT" >&2
  exit 1
fi

# ══════════════════════════════════════════════════════════════════════════
# 1. PRE-CHEQUEO: que datos legados hay antes de tocar nada
# ══════════════════════════════════════════════════════════════════════════
echo
echo "── PRE-CHEQUEO (datos legados en $DB_NAME) ──"
echo " Impresoras (wk_printer_printer)          : $(table_count wk_printer_printer)"
echo " Plantillas (report_template)             : $(table_count report_template)"
echo " Reportes configurados (send_to_printer)  : $(configured_reports_count)"
for m in $LEGACY_MODULES; do
  echo " Estado modulo $m: $(module_state "$m")"
done
echo " Estado modulo $MODULE: $(module_state "$MODULE")"

if $DRY_RUN; then
  echo
  echo "Modo --dry-run: pre-chequeo completado, no se hicieron cambios."
  exit 0
fi

# ══════════════════════════════════════════════════════════════════════════
# 2. INSTALACION: los hooks hacen snapshot -> desinstalan legado -> restauran
# ══════════════════════════════════════════════════════════════════════════
echo
echo "→ Instalando $MODULE en $DB_NAME (puede tardar)..."
docker exec "$CONTAINER" bash -lc "
  odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    -i $MODULE --stop-after-init --no-http \
    --max-cron-threads=0 --workers=0
" || { echo "ERROR: fallo la instalacion de $MODULE (revisar log de arriba)" >&2; exit 1; }

# ══════════════════════════════════════════════════════════════════════════
# 3. POST-CHEQUEO: datos restaurados y limpieza completa del legado
# ══════════════════════════════════════════════════════════════════════════
echo
echo "── POST-CHEQUEO ──"
FAIL=0

PRINTERS="$(table_count direct_print_printer)"
TEMPLATES="$(table_count direct_print_template)"
CONFIGURED="$(configured_reports_count)"
echo " Impresoras (direct_print_printer)        : $PRINTERS"
echo " Plantillas (direct_print_template)       : $TEMPLATES"
echo " Reportes configurados (send_to_printer)  : $CONFIGURED"

NEW_STATE="$(module_state "$MODULE")"
echo " Estado modulo $MODULE: $NEW_STATE"
if [[ "$NEW_STATE" != "installed" ]]; then
  echo " ERROR: $MODULE no quedo instalado (estado: $NEW_STATE)" >&2
  FAIL=1
fi

# Los modulos legados deben quedar desinstalados (upgrade-util borra incluso
# la fila de ir_module_module, asi que 'no registrado' tambien es valido).
for m in $LEGACY_MODULES; do
  STATE="$(module_state "$m")"
  echo " Estado modulo $m: $STATE"
  if [[ "$STATE" != "uninstalled" && "$STATE" != "no registrado" ]]; then
    echo " ERROR: el modulo legado $m sigue en estado '$STATE'" >&2
    FAIL=1
  fi
done

for t in $LEGACY_TABLES; do
  if table_exists "$t"; then
    echo " ERROR: la tabla legada $t sigue existiendo" >&2
    FAIL=1
  fi
done

for t in $SNAPSHOT_TABLES; do
  if table_exists "$t"; then
    echo " ERROR: quedo la tabla snapshot $t (post_init_hook no la elimino)" >&2
    FAIL=1
  fi
done

echo
echo "======================================================"
if [[ $FAIL -eq 0 ]]; then
  echo " MIGRACION OK en $DB_NAME"
  echo "  - Impresoras restauradas : $PRINTERS"
  echo "  - Plantillas restauradas : $TEMPLATES"
  echo "  - Reportes configurados  : $CONFIGURED"
  echo "  - Modulos legados eliminados sin residuos."
else
  echo " MIGRACION CON ERRORES en $DB_NAME (ver mensajes de arriba)."
  echo " La DB queda como este; revisar logs antes de reintentar."
fi
echo "======================================================"
exit $FAIL
