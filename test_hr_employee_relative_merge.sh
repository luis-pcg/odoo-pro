#!/bin/bash
# test_hr_employee_relative_merge.sh
#
# Prueba del merge OCA hr_employee_relative -> l10n_do_hr que corre upgrade-util en:
#   upgrade-util/src/l10n_do_banks/19.0.1.0.0/end-10-retire-hr-employee-relative.py
#
# QUE PRUEBA Y QUE NO
# -------------------
# El bug reportado no es de datos, es de ORDEN: merge_module() borra la fila de
# ir_module_module, y el grafo de modulos ya se armo (STEP 3 de load_modules) para
# cuando corren los scripts de l10n_do_banks. Como el OCA hr_employee_relative
# sigue en el addons path, entra al grafo y Odoo revienta con MissingError al
# llegarle.
#
# Un upgrade real v17 -> v19 NO es reproducible en estos contenedores: Odoo hace
# 17 -> 18 -> 19 con los scripts de su plataforma de upgrade, de la cual
# upgrade-util es solo la parte publica. Un `-u all` directo sobre una base v17
# muere antes, convirtiendo columnas de `base` a jsonb.
#
# Asi que este arnes reproduce el MECANISMO sobre una base v19: instala de verdad
# l10n_do_hr + l10n_do_banks + el OCA hr_employee_relative, y luego rebobina
# ir_module_module.latest_version de base/l10n_do_banks/l10n_do_hr a sus valores
# v17 para que los directorios de migracion coincidan y los scripts corran con el
# grafo armado igual que en produccion.
#
# Los dos modos corren con el OCA en el addons path, que es la condicion real
# (odoo-pro/OCA/hr es un submodulo de OCA, no se puede tocar).
#   CONTROL  -> merge_module desde un pre- de l10n_do_banks: le borra la fila que
#               el snapshot del grafo todavia referencia -> MissingError.
#   FIX      -> end-10-retire-hr-employee-relative.py: el modulo se carga normal y
#               en la etapa end- pasa a 'to remove'; el STEP 5 de Odoo corre su
#               propio module_uninstall() y recarga el registry sin el.
#
# Uso:
#   ./test_hr_employee_relative_merge.sh                  # corre el fix
#   ./test_hr_employee_relative_merge.sh --control        # corre la variante con el bug
#   ./test_hr_employee_relative_merge.sh --keep-fixture   # reusa el fixture existente
#   ./test_hr_employee_relative_merge.sh --fixture-only   # solo arma el fixture
#
# NO toca ninguna base existente: solo crea/borra las bases de prueba.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

V19_CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

FIXTURE_DB="test_hr_relative_fixture"
UPGRADE_DB="test_hr_relative_fix"
FIXTURE_MODULES="l10n_do_hr,l10n_do_banks,hr_employee_relative"

OCA_SRC="$SCRIPT_DIR/odoo-pro/OCA/hr/hr_employee_relative"
TEST_ADDONS="/opt/test-addons"
UPGRADE_UTIL_SRC="$SCRIPT_DIR/upgrade-util"
UPGRADE_UTIL_DEST="/opt/upgrade-util-test"
LOG_DIR="$SCRIPT_DIR/test_logs"

# Versiones v17 a las que se rebobina el clon para que corran los scripts de migracion.
V17_BASE="17.0.1.3"
V17_BANKS="17.0.1.2.0"
V17_DO_HR="17.0.1.0.2"

KEEP_FIXTURE=false
FIXTURE_ONLY=false
CONTROL=false
for arg in "$@"; do
  case "$arg" in
    --keep-fixture) KEEP_FIXTURE=true ;;
    --fixture-only) FIXTURE_ONLY=true ;;
    --control)      CONTROL=true; UPGRADE_DB="test_hr_relative_ctl" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done
LOG_HOST="$LOG_DIR/hr_relative_$($CONTROL && echo control || echo fix).log"

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"
CONF_ADDONS="$(docker exec "$V19_CONTAINER" bash -lc "grep '^addons_path' /etc/odoo/odoo.conf | cut -d= -f2- | tr -d ' '")"
ADDONS_PATH="$CONF_ADDONS"
UPG_ADDONS_PATH="$CONF_ADDONS"

# ── helpers ──────────────────────────────────────────────────────────────────
psql_db() {  # psql_db <db> <sql>
  docker exec "$V19_CONTAINER" bash -lc \
    "PGPASSWORD='$DB_PASS' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $1 -tAc \"$2\"" 2>/dev/null
}
psql_admin() {
  docker exec "$V19_CONTAINER" bash -lc \
    "PGPASSWORD='$DB_PASS' psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"$1\"" 2>/dev/null
}
db_exists() { [[ "$(psql_admin "SELECT 1 FROM pg_database WHERE datname='$1'")" == "1" ]]; }
kill_conns() {
  psql_admin "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1' AND pid <> pg_backend_pid()" >/dev/null
}
drop_db() { kill_conns "$1"; psql_admin "DROP DATABASE IF EXISTS \\\"$1\\\"" >/dev/null; }

PASS=0; FAIL=0
check() {  # check <descripcion> <esperado> <obtenido>
  if [[ "$2" == "$3" ]]; then
    printf '  \033[32mOK  \033[0m %-56s %s\n' "$1" "$3"; PASS=$((PASS+1))
  else
    printf '  \033[31mFAIL\033[0m %-56s esperado=%s obtenido=%s\n' "$1" "$2" "$3"; FAIL=$((FAIL+1))
  fi
}

echo "======================================================================"
echo " Test merge hr_employee_relative -> l10n_do_hr"
echo " fixture : $FIXTURE_DB"
echo " corrida : $UPGRADE_DB"
$CONTROL && echo " modo    : CONTROL (merge_module en pre-, se espera MissingError)" \
         || echo " modo    : FIX (end-10-retire-hr-employee-relative.py)"
echo "======================================================================"

# ── 1. FIXTURE v19 ───────────────────────────────────────────────────────────
if $KEEP_FIXTURE && db_exists "$FIXTURE_DB"; then
  echo; echo "[1/4] Fixture: reusando $FIXTURE_DB"
else
  echo; echo "[1/4] Fixture: creando $FIXTURE_DB con -i $FIXTURE_MODULES"
  drop_db "$FIXTURE_DB"
  psql_admin "CREATE DATABASE \\\"$FIXTURE_DB\\\"" >/dev/null
  docker exec "$V19_CONTAINER" bash -lc \
    "odoo -c /etc/odoo/odoo.conf -d $FIXTURE_DB $ODOO_DB_FLAGS --addons-path='$ADDONS_PATH' \
      -i $FIXTURE_MODULES --without-demo=all --no-http --stop-after-init --log-level=warn" \
    || { echo "ERROR: fallo la instalacion del fixture" >&2; exit 1; }

  echo "      Sembrando empleado + parientes"
  docker exec -i "$V19_CONTAINER" bash -lc \
    "odoo shell -c /etc/odoo/odoo.conf -d $FIXTURE_DB $ODOO_DB_FLAGS --addons-path='$ADDONS_PATH' --no-http --log-level=warn" <<'PYSEED'
rel = env.ref("hr_employee_relative.relation_child")
emp = env["hr.employee"].create({"name": "Empleado Prueba Parientes"})
env["hr.employee.relative"].create([
    {"employee_id": emp.id, "relation_id": rel.id, "name": "Hija Uno", "date_of_birth": "2015-04-01"},
    {"employee_id": emp.id, "relation_id": rel.id, "name": "Hijo Dos", "date_of_birth": "2018-09-12"},
])
env.cr.commit()
print("SEED_OK relatives=%s" % env["hr.employee.relative"].search_count([]))
PYSEED
fi

FIX_RELATIVES="$(psql_db "$FIXTURE_DB" "SELECT count(*) FROM hr_employee_relative")"
FIX_OCA_XMLIDS="$(psql_db "$FIXTURE_DB" "SELECT count(*) FROM ir_model_data WHERE module='hr_employee_relative'")"
FIX_STATE="$(psql_db "$FIXTURE_DB" "SELECT state FROM ir_module_module WHERE name='hr_employee_relative'")"
echo "      parientes=$FIX_RELATIVES  xmlids_del_OCA=$FIX_OCA_XMLIDS  estado_OCA=$FIX_STATE"
[[ "$FIX_RELATIVES" == "0" || -z "$FIX_RELATIVES" ]] && { echo "ERROR: fixture sin parientes" >&2; exit 1; }
[[ "$FIX_STATE" == "installed" ]] || { echo "ERROR: el OCA no quedo instalado en el fixture" >&2; exit 1; }
$FIXTURE_ONLY && { echo; echo "Fixture listo. Fin (--fixture-only)."; exit 0; }

# ── 2. CLON + rebobinado de versiones ────────────────────────────────────────
echo; echo "[2/4] Clonando -> $UPGRADE_DB y rebobinando versiones a v17"
drop_db "$UPGRADE_DB"
kill_conns "$FIXTURE_DB"
psql_admin "CREATE DATABASE \\\"$UPGRADE_DB\\\" TEMPLATE \\\"$FIXTURE_DB\\\"" >/dev/null \
  || { echo "ERROR: no se pudo clonar" >&2; exit 1; }
OCA_RELATIONS="'relation_spouse','relation_significant_other','relation_child','relation_parent','relation_sibling','relation_cousin','relation_grandparent','relation_grandchild'"
psql_db "$UPGRADE_DB" "
  UPDATE ir_module_module SET latest_version='$V17_BASE'  WHERE name='base';
  UPDATE ir_module_module SET latest_version='$V17_BANKS' WHERE name='l10n_do_banks';
  UPDATE ir_module_module SET latest_version='$V17_DO_HR' WHERE name='l10n_do_hr';
  -- El fixture instala los dos modulos frescos en v19, asi que los relation_* de
  -- OCA quedan duplicados bajo l10n_do_hr. En una base v17 real l10n_do_hr solo
  -- define los suyos (father_in_law, uncle, ...), asi que se borran los duplicados
  -- para reproducir ese estado; si no, el pre-migrate.py de l10n_do_hr choca con
  -- ir_model_data_module_name_uniq_index al reasignar el xml id.
  DELETE FROM hr_employee_relative_relation r
   USING ir_model_data d
   WHERE d.model='hr.employee.relative.relation' AND d.res_id=r.id
     AND d.module='l10n_do_hr' AND d.name IN ($OCA_RELATIONS);
  DELETE FROM ir_model_data
   WHERE module='l10n_do_hr' AND model='hr.employee.relative.relation'
     AND name IN ($OCA_RELATIONS);" >/dev/null
echo "      base=$V17_BASE  l10n_do_banks=$V17_BANKS  l10n_do_hr=$V17_DO_HR"
echo "      relation_* duplicados de l10n_do_hr eliminados (estado v17)"
PRE_MODID="$(psql_db "$UPGRADE_DB" "SELECT id FROM ir_module_module WHERE name='hr_employee_relative'")"
echo "      ir_module_module.id del OCA = $PRE_MODID"

# ── 3. upgrade-util recortado dentro del contenedor ──────────────────────────
echo; echo "[3/4] Copiando upgrade-util al contenedor y recortandolo"
docker exec "$V19_CONTAINER" rm -rf "$UPGRADE_UTIL_DEST"
docker cp "$UPGRADE_UTIL_SRC" "$V19_CONTAINER:$UPGRADE_UTIL_DEST" >/dev/null
# Se dejan solo los scripts relevantes: los de base, y de l10n_do_banks unicamente
# pre-views-delete.py (que borra la vista reubicada). El resto son migraciones de
# datos de produccion que no aplican a una base v19 minima.
docker exec "$V19_CONTAINER" bash -lc "
  cd $UPGRADE_UTIL_DEST/src
  rm -rf l10n_do_hr_payroll mail product_sequence sale_discount_display_amount spreadsheet
  find l10n_do_banks -type f -name '*.py' \
    ! -name 'end-10-retire-hr-employee-relative.py' \
    ! -name 'pre-views-delete.py' -delete
"
if $CONTROL; then
  echo "      CONTROL: quitando el fix y plantando merge_module en un pre-"
  docker exec "$V19_CONTAINER" rm -f "$UPGRADE_UTIL_DEST/src/l10n_do_banks/19.0.1.0.0/end-10-retire-hr-employee-relative.py"
  docker exec "$V19_CONTAINER" bash -lc "cat > $UPGRADE_UTIL_DEST/src/l10n_do_banks/19.0.1.0.0/pre-01-control-merge.py <<'PY'
from odoo.addons.base.maintenance.migrations import util


def migrate(cr, version):
    # En staging los scripts de base no corren en esta pasada, asi que
    # AUTO_DISCOVERY_UPGRADE es False. Se replica para aislar la variable de orden.
    util.ENVIRON[\"AUTO_DISCOVERY_UPGRADE\"] = False
    util.merge_module(cr, \"hr_employee_relative\", \"l10n_do_hr\")
PY"
fi
# En staging los scripts de base no corren en esta pasada, asi que
# AUTO_DISCOVERY_UPGRADE es False y merge_module llega a force_install_module sin
# abortar. Se replica esa condicion para no medir un efecto colateral del arnes.
docker exec "$V19_CONTAINER" bash -lc "cat > $UPGRADE_UTIL_DEST/src/base/0.0.0/post-99-test-reset-autodiscovery-flag.py <<'PY'
from odoo.addons.base.maintenance.migrations import util


def migrate(cr, version):
    util.ENVIRON[\"AUTO_DISCOVERY_UPGRADE\"] = False
PY"
echo "      scripts de base : $(docker exec "$V19_CONTAINER" bash -lc "ls $UPGRADE_UTIL_DEST/src/base | tr '\n' ' '")"
echo "      scripts de banks: $(docker exec "$V19_CONTAINER" bash -lc "ls $UPGRADE_UTIL_DEST/src/l10n_do_banks/19.0.1.0.0 | tr '\n' ' '")"

# ── 4. UPGRADE ───────────────────────────────────────────────────────────────
echo; echo "[4/4] Corriendo el upgrade"
mkdir -p "$LOG_DIR"
docker exec "$V19_CONTAINER" bash -lc \
  "odoo -c /etc/odoo/odoo.conf -d $UPGRADE_DB $ODOO_DB_FLAGS --addons-path='$UPG_ADDONS_PATH' \
    -u all --upgrade-path=$UPGRADE_UTIL_DEST/src \
    --without-demo=all --no-http --stop-after-init --log-level=info" \
  > "$LOG_HOST" 2>&1
UPG_RC=$?
echo "      exit code = $UPG_RC   log = $LOG_HOST"

# ── 5. ASSERTS ───────────────────────────────────────────────────────────────
echo; echo "[5/5] Verificaciones"
MISSING_ERR=no
grep -q "MissingError" "$LOG_HOST" && MISSING_ERR=si

if $CONTROL; then
  echo "  (control: se ESPERA que reviente igual que en staging)"
  check "el upgrade falla"                        "no-cero" "$([[ $UPG_RC -ne 0 ]] && echo no-cero || echo cero)"
  check "MissingError en el log"                  "si"      "$MISSING_ERR"
  check "MissingError sobre ir.module.module"     "si" \
    "$(grep -q "ir.module.module($PRE_MODID," "$LOG_HOST" && echo si || echo no)"
  echo "  --- traza ---"
  grep -n "Loading module hr_employee_relative\|MissingError\|ir.module.module(" "$LOG_HOST" | tail -4 | sed 's/^/        /'
else
  check "el upgrade termina bien"                 "0"   "$UPG_RC"
  check "sin MissingError en el log"              "no"  "$MISSING_ERR"
  check "Odoo corre su propio uninstall"          "si" \
    "$(grep -q "Reloading registry once more after uninstalling modules" "$LOG_HOST" && echo si || echo no)"
  check "el OCA queda desinstalado"               "uninstalled" \
    "$(psql_db "$UPGRADE_DB" "SELECT state FROM ir_module_module WHERE name='hr_employee_relative'")"
  check "l10n_do_hr sigue instalado"              "installed" \
    "$(psql_db "$UPGRADE_DB" "SELECT state FROM ir_module_module WHERE name='l10n_do_hr'")"
  check "tabla hr_employee_relative existe"       "t" \
    "$(psql_db "$UPGRADE_DB" "SELECT to_regclass('public.hr_employee_relative') IS NOT NULL")"
  check "parientes preservados"                   "$FIX_RELATIVES" \
    "$(psql_db "$UPGRADE_DB" "SELECT count(*) FROM hr_employee_relative")"
  check "el modelo ya no es de nadie mas que l10n_do_hr" "1" \
    "$(psql_db "$UPGRADE_DB" "SELECT count(DISTINCT module) FROM ir_model_data WHERE model='ir.model' AND name='model_hr_employee_relative'")"
  check "dueño del modelo"                        "l10n_do_hr" \
    "$(psql_db "$UPGRADE_DB" "SELECT DISTINCT module FROM ir_model_data WHERE model='ir.model' AND name='model_hr_employee_relative'")"
  check "no queda ir_model_data del OCA"          "0" \
    "$(psql_db "$UPGRADE_DB" "SELECT count(*) FROM ir_model_data WHERE module='hr_employee_relative'")"
  check "campo hr.employee.relative_ids vivo"     "1" \
    "$(psql_db "$UPGRADE_DB" "SELECT count(*) FROM ir_model_fields WHERE model='hr.employee' AND name='relative_ids'")"
  check "vista OCA hr_employee_view_form borrada" "0" \
    "$(psql_db "$UPGRADE_DB" "SELECT count(*) FROM ir_model_data WHERE name='hr_employee_view_form' AND module IN ('hr_employee_relative','l10n_do_hr')")"
  check "sin dependencias colgando del OCA"       "0" \
    "$(psql_db "$UPGRADE_DB" "SELECT count(*) FROM ir_module_module_dependency WHERE name='hr_employee_relative'")"
  echo "  --- traza del merge ---"
  grep -n "Module merged\|hr_employee_relative" "$LOG_HOST" | head -6 | sed 's/^/        /'
fi

echo
echo "======================================================================"
echo " PASS=$PASS  FAIL=$FAIL"
echo "======================================================================"
[[ $FAIL -eq 0 ]] || exit 1
