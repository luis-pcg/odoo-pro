#!/bin/bash
# replicate_stock_analytic_migration.sh
#
# Demuestra, sobre bases reales, que los datos analiticos de OCA `stock_analytic`
# sobreviven al cambio a `stock_analytic_distribution_features` en Odoo 19.
#
# Monta un `stock_analytic` de mentira dentro del contenedor (mismos nombres
# tecnicos que el de OCA: analytic_distribution en stock.move, stock.move.line y
# stock.scrap via analytic.mixin, mas el valor `stock_move` del dominio de
# aplicabilidad), lo instala, siembra datos como los que tendria Escala Solar en
# 17.0/18.0, y luego compara dos caminos:
#
#   CONTROL : alguien desinstala `stock_analytic` a mano para limpiar el estado
#             inconsistente -> Odoo dropea las tres columnas. Perdida total.
#   ARREGLO : se actualiza `l10n_do_banks` con --upgrade-path, y la entrada que
#             se agrego en
#             upgrade-util/src/l10n_do_banks/19.0.1.0.0/pre-module-merge.py
#             llama a
#             `util.merge_module(cr, 'stock_analytic', 'stock_analytic_distribution_features')`
#             -> el modulo OCA desaparece, el nuevo queda instalado y las
#                columnas, el jsonb y las partidas analiticas siguen intactas.
#
# Por que funciona: los nombres de campo, modelo y columna son identicos entre
# los dos modulos, asi que no hay nada que convertir; merge_module solo reasigna
# los metadatos (ir_model_data, constraints, relaciones, traducciones), borra la
# fila del modulo viejo y force-instala el nuevo.
#
# Nota sobre Odoo 19: un modulo que esta en la base pero ya no en el disco NO se
# desinstala solo; queda en estado inconsistente y Odoo lo registra como error al
# arrancar. La perdida ocurre cuando alguien lo desinstala para limpiar ese error.
#
# Uso:
#   ./replicate_stock_analytic_migration.sh
#   ./replicate_stock_analytic_migration.sh --keep-dbs
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

BASE_DB="v19_sam_base"
LOSS_DB="v19_sam_control"
FIXED_DB="v19_sam_fixed"
KEEP_DBS=false
for arg in "$@"; do
  case "$arg" in
    --keep-dbs) KEEP_DBS=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"
ADDONS_PATH="$(grep '^addons_path' "$SCRIPT_DIR/conf/odoo.conf" | sed 's/^addons_path = //')"
SIM_DIR="/tmp/oca_sim_stock_analytic"
UPGRADE_SRC="/tmp/oca_sim_upgrade_util/src"

echo "======================================================"
echo " Migracion de datos OCA stock_analytic -> stock_analytic_distribution_features"
echo " Contenedor : $CONTAINER"
echo " Bases      : $BASE_DB (origen), $LOSS_DB (control), $FIXED_DB (arreglo)"
echo "======================================================"

psql_q() { docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $1 -tAc \"$2\""; }

kill_conns() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \
     \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1' AND pid <> pg_backend_pid()\"" >/dev/null 2>&1
}

# ── 1. Modulo OCA simulado dentro del contenedor ─────────────────────────────
echo "→ [1/5] Escribiendo el stock_analytic simulado en $SIM_DIR..."
docker exec "$CONTAINER" bash -lc "
set -e
rm -rf $SIM_DIR && mkdir -p $SIM_DIR/stock_analytic/models
cat > $SIM_DIR/stock_analytic/__manifest__.py <<'EOF'
{
    'name': 'Stock Analytic (OCA simulation)',
    'version': '19.0.1.2.0',
    'license': 'AGPL-3',
    'author': 'OCA',
    'category': 'Inventory',
    'depends': ['stock_account', 'analytic'],
    'installable': True,
}
EOF
echo 'from . import models' > $SIM_DIR/stock_analytic/__init__.py
echo 'from . import stock_analytic' > $SIM_DIR/stock_analytic/models/__init__.py
cat > $SIM_DIR/stock_analytic/models/stock_analytic.py <<'EOF'
from odoo import fields, models


class StockMove(models.Model):
    _name = 'stock.move'
    _inherit = ['stock.move', 'analytic.mixin']


class StockMoveLine(models.Model):
    _name = 'stock.move.line'
    _inherit = ['stock.move.line', 'analytic.mixin']


class StockScrap(models.Model):
    _name = 'stock.scrap'
    _inherit = ['stock.scrap', 'analytic.mixin']


class AccountAnalyticApplicability(models.Model):
    _inherit = 'account.analytic.applicability'

    business_domain = fields.Selection(
        selection_add=[('stock_move', 'Stock Move')],
        ondelete={'stock_move': 'cascade'},
    )
EOF
" || { echo 'ERROR escribiendo el modulo simulado' >&2; exit 1; }

echo "→ Copiando upgrade-util al contenedor ($UPGRADE_SRC)..."
docker exec "$CONTAINER" bash -lc "rm -rf $(dirname $UPGRADE_SRC) && mkdir -p $(dirname $UPGRADE_SRC)"
docker cp "$SCRIPT_DIR/upgrade-util/src" "$CONTAINER:$UPGRADE_SRC" >/dev/null \
  || { echo 'ERROR copiando upgrade-util' >&2; exit 1; }

# ── 2. Base origen: OCA instalado + datos ────────────────────────────────────
echo "→ [2/5] Creando $BASE_DB con el modulo OCA + l10n_do_banks..."
kill_conns "$BASE_DB"
docker exec "$CONTAINER" bash -lc "
export PGPASSWORD=$DB_PASS
dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $BASE_DB
createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $BASE_DB
odoo -c /etc/odoo/odoo.conf -d $BASE_DB $ODOO_DB_FLAGS \
  --addons-path='$ADDONS_PATH,$SIM_DIR' -i stock_analytic,project_stock_account,l10n_do_banks \
  --stop-after-init --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" >/dev/null 2>&1 || { echo 'ERROR instalando el modulo OCA simulado' >&2; exit 1; }

echo "→ Sembrando conduce, desecho y partidas analiticas historicas..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $BASE_DB $ODOO_DB_FLAGS \
    --addons-path='$ADDONS_PATH,$SIM_DIR' --no-http --max-cron-threads=0 --workers=0 --log-level=error
" <<'PYEOF' 2>&1 | grep -E "SNAPSHOT|  "
import logging
logging.disable(logging.WARNING)

company = env.ref('base.main_company')
plan = env['account.analytic.plan'].create({'name': 'Proyectos'})
col = plan._column_name()
obra_a, obra_b = env['account.analytic.account'].create([
    {'code': 'PROY-001', 'name': 'Planta Solar Bavaro', 'plan_id': plan.id},
    {'code': 'PROY-002', 'name': 'Techo Solar Santiago', 'plan_id': plan.id},
])
categ = env['product.category'].create({
    'name': 'Materiales Solares',
    'property_cost_method': 'standard',
    'property_valuation': 'periodic',
})
uom = env.ref('uom.product_uom_unit')
panel = env['product.product'].create({
    'name': 'Panel solar 550W', 'default_code': 'SOL-PANEL', 'is_storable': True,
    'categ_id': categ.id, 'uom_id': uom.id, 'standard_price': 12500.0,
})
wh = env['stock.warehouse'].search([], limit=1)
env['stock.quant']._update_available_quantity(panel, wh.lot_stock_id, 100)

pick = env['stock.picking'].create({
    'picking_type_id': wh.out_type_id.id,
    'location_id': wh.lot_stock_id.id,
    'location_dest_id': env.ref('stock.stock_location_customers').id,
    'origin': 'Conduce imputado en 17.0 con OCA stock_analytic',
})
mv = env['stock.move'].create({
    'product_id': panel.id, 'product_uom_qty': 4, 'product_uom': uom.id,
    'picking_id': pick.id, 'location_id': pick.location_id.id,
    'location_dest_id': pick.location_dest_id.id,
    'analytic_distribution': {str(obra_a.id): 60, str(obra_b.id): 40},
})
pick.action_confirm()
pick.action_assign()
mv.quantity = 4
mv.move_line_ids.analytic_distribution = {str(obra_a.id): 60, str(obra_b.id): 40}
mv.picked = True
pick.button_validate()

scrap = env['stock.scrap'].create({
    'product_id': panel.id, 'product_uom_id': uom.id, 'scrap_qty': 1,
    'location_id': wh.lot_stock_id.id,
    'analytic_distribution': {str(obra_b.id): 100},
})
scrap.action_validate()

# Partidas analiticas como las creaba el flujo OCA: nacidas del apunte de valoracion
env['account.analytic.line'].create([
    {'name': 'OCA valuation 1', 'amount': -30000.0, 'unit_amount': 2.0, col: obra_a.id, 'company_id': company.id},
    {'name': 'OCA valuation 2', 'amount': -20000.0, 'unit_amount': 1.0, col: obra_b.id, 'company_id': company.id},
])
env['account.analytic.applicability'].create({
    'business_domain': 'stock_move', 'analytic_plan_id': plan.id, 'applicability': 'optional',
})
env.cr.commit()

c = env.cr
print('SNAPSHOT ANTES DEL CAMBIO')
c.execute("SELECT count(*) FROM stock_move WHERE analytic_distribution <> '{}'::jsonb")
print('  stock_move con distribucion   :', c.fetchone()[0])
c.execute("SELECT count(*) FROM stock_move_line WHERE analytic_distribution <> '{}'::jsonb")
print('  stock_move_line               :', c.fetchone()[0])
c.execute("SELECT count(*) FROM stock_scrap WHERE analytic_distribution <> '{}'::jsonb")
print('  stock_scrap                   :', c.fetchone()[0])
c.execute("SELECT analytic_distribution FROM stock_move WHERE analytic_distribution <> '{}'::jsonb")
print('  jsonb del movimiento          :', c.fetchall())
c.execute("SELECT sum(amount), count(*) FROM account_analytic_line")
print('  partidas analiticas           :', c.fetchall())
PYEOF

# ── 3. Copias ────────────────────────────────────────────────────────────────
echo "→ [3/5] Clonando la base origen para los dos caminos..."
for db in "$LOSS_DB" "$FIXED_DB" "$BASE_DB"; do kill_conns "$db"; done
sleep 1
docker exec "$CONTAINER" bash -lc "
export PGPASSWORD=$DB_PASS
dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $LOSS_DB
dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $FIXED_DB
createdb -h $DB_HOST -p $DB_PORT -U $DB_USER -T $BASE_DB $LOSS_DB
createdb -h $DB_HOST -p $DB_PORT -U $DB_USER -T $BASE_DB $FIXED_DB
" || { echo 'ERROR clonando las bases' >&2; exit 1; }

# ── 4. CONTROL ───────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " CONTROL — alguien desinstala stock_analytic a mano"
echo "======================================================"
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $LOSS_DB $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=critical
" <<'PYEOF' 2>&1 | grep -E "  "
import logging
logging.disable(logging.WARNING)
env['ir.module.module'].search([('name', '=', 'stock_analytic')]).module_uninstall()
env.cr.commit()
env.cr.execute("""
    SELECT coalesce(string_agg(table_name, ', '), 'NINGUNA')
      FROM information_schema.columns
     WHERE column_name = 'analytic_distribution'
       AND table_name IN ('stock_move', 'stock_move_line', 'stock_scrap')
""")
print('  columnas que sobreviven       :', env.cr.fetchone()[0])
PYEOF

# ── 5. ARREGLO ───────────────────────────────────────────────────────────────
echo ""
echo "======================================================"
echo " ARREGLO — upgrade de l10n_do_banks (upgrade-util: merge_module)"
echo "======================================================"
echo "→ [4/5] Rebobinando l10n_do_banks a 17.0.1.0.0 para que cruce 19.0.1.0.0..."
docker exec "$CONTAINER" bash -lc "
export PGPASSWORD=$DB_PASS
psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d $FIXED_DB -tAc \
  \"UPDATE ir_module_module SET latest_version='17.0.1.0.0' WHERE name='l10n_do_banks'\"
" >/dev/null 2>&1

echo "→ Actualizando l10n_do_banks con --upgrade-path (corre pre-module-merge.py)..."
docker exec "$CONTAINER" bash -lc "
odoo -c /etc/odoo/odoo.conf -d $FIXED_DB $ODOO_DB_FLAGS --upgrade-path=$UPGRADE_SRC \
  -u l10n_do_banks --stop-after-init --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" 2>&1 | grep -iE "Module merged|Traceback|CRITICAL" | head -6 | sed 's/^/  /'

echo "→ [5/5] Verificando..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $FIXED_DB $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=critical
" <<'PYEOF' 2>&1 | grep -E "  "
import logging
logging.disable(logging.WARNING)

c = env.cr
c.execute("""
    SELECT coalesce(string_agg(table_name, ', '), 'NINGUNA')
      FROM information_schema.columns
     WHERE column_name = 'analytic_distribution'
       AND table_name IN ('stock_move', 'stock_move_line', 'stock_scrap')
""")
print('  columnas que sobreviven       :', c.fetchone()[0])
c.execute("SELECT count(*) FROM stock_move WHERE analytic_distribution <> '{}'::jsonb")
print('  stock_move con distribucion   :', c.fetchone()[0])
c.execute("SELECT count(*) FROM stock_move_line WHERE analytic_distribution <> '{}'::jsonb")
print('  stock_move_line               :', c.fetchone()[0])
c.execute("SELECT count(*) FROM stock_scrap WHERE analytic_distribution <> '{}'::jsonb")
print('  stock_scrap                   :', c.fetchone()[0])
c.execute("SELECT analytic_distribution FROM stock_move WHERE analytic_distribution <> '{}'::jsonb")
print('  jsonb del movimiento          :', c.fetchall())
c.execute("SELECT sum(amount), count(*) FROM account_analytic_line")
print('  partidas analiticas           :', c.fetchall())
c.execute("""
    SELECT count(*) FROM ir_model_fields_selection s
      JOIN ir_model_fields f ON f.id = s.field_id
     WHERE f.model = 'account.analytic.applicability' AND s.value = 'stock_move'
""")
print('  valor de dominio stock_move   :', c.fetchone()[0])
print('  aplicabilidad configurada     :',
      env['account.analytic.applicability'].search_count([('business_domain', '=', 'stock_move')]))
c.execute("SELECT name || '=' || state FROM ir_module_module WHERE name LIKE 'stock_analytic%' ORDER BY name")
print('  modulos                       :', [r[0] for r in c.fetchall()])
PYEOF

echo ""
echo "======================================================"
echo " Esperado: CONTROL -> NINGUNA (perdida total)"
echo "           ARREGLO -> las tres columnas, el jsonb 60/40 y las 2 partidas"
echo "                      historicas intactas, sin duplicados"
echo "======================================================"

if ! $KEEP_DBS; then
  echo "→ Limpiando bases de la prueba..."
  for db in "$BASE_DB" "$LOSS_DB" "$FIXED_DB"; do
    kill_conns "$db"
    docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $db" >/dev/null 2>&1
  done
  docker exec "$CONTAINER" bash -lc "rm -rf $SIM_DIR $(dirname $UPGRADE_SRC)"
else
  echo "Bases conservadas: $BASE_DB, $LOSS_DB, $FIXED_DB (--keep-dbs)"
fi
