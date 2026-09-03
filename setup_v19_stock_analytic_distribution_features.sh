#!/bin/bash
# setup_v19_stock_analytic_distribution_features.sh
#
# Crea y configura una base de datos NUEVA (sin datos demo) para probar el
# modulo stock_analytic_distribution_features en Odoo 19: la distribucion analitica en
# los conduces (movimientos de inventario), reemplazo de OCA stock_analytic.
#
# Que hace:
#
#   1. Crea la DB v19_stock_analytic_distribution_features e instala
#      stock_analytic_distribution_features + project_stock_account (este ultimo arrastra
#      project/project_stock y provoca el auto_install del puente
#      stock_analytic_distribution_features_project).
#   2. Activa la Contabilidad Analitica en el usuario admin.
#   3. Crea el plan analitico "Proyectos" con dos cuentas (dos obras) y un
#      project.project enganchado a la segunda cuenta (flujo nativo).
#   4. Crea productos almacenables valorados a costo estandar y les pone
#      existencia.
#   5. Genera los escenarios de prueba:
#        A. Conduce validado, distribucion 100 % a una obra.
#        B. Conduce marcado (picked) SIN validar, reparto 60/40  -> costo
#           estimado visible antes de facturar. Este es el caso del cliente.
#        C. Conduce sin distribucion -> no genera partidas analiticas.
#        D. Desecho (scrap) con distribucion.
#        E. Conduce con proyecto + "Costos analiticos" en el tipo de operacion
#           (flujo nativo de Odoo 19, sin distribucion manual).
#        F. Conduce con proyecto Y distribucion manual -> gana la manual, un
#           solo juego de partidas (no hay doble conteo).
#   6. Verifica e imprime, por escenario, las partidas analiticas generadas y
#      el acumulado por cuenta analitica.
#
# Los datos se COMMITEAN (la DB queda lista para navegar por web).
#
# Uso:
#   ./setup_v19_stock_analytic_distribution_features.sh                # crea DB nueva
#   ./setup_v19_stock_analytic_distribution_features.sh --db=mi_db     # nombre propio
#   ./setup_v19_stock_analytic_distribution_features.sh --recreate     # borra y recrea
#   ./setup_v19_stock_analytic_distribution_features.sh --skip-install # solo siembra
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
# project_stock_account arrastra project + project_stock y dispara el
# auto_install de stock_analytic_distribution_features_project.
MODULE="stock_analytic_distribution_features,project_stock_account"

DB_NAME="v19_stock_analytic_distribution_features"
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

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Setup distribucion analitica en conduces"
echo " Modulo     : stock_analytic_distribution_features"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
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

  echo "→ Instalando $MODULE sin datos demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --without-demo=all --stop-after-init \
      --no-http --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
fi

echo "→ Sembrando plan analitico, productos, conduces y desecho..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import logging
logging.disable(logging.WARNING)

def line(c='-'):
    print(c * 78)

company = env.ref('base.main_company')
admin = env.ref('base.user_admin')

# ════════════════════════════════════════════════════════════════════════════
# 1. CONTABILIDAD ANALITICA VISIBLE PARA EL ADMIN
# ════════════════════════════════════════════════════════════════════════════
admin.write({'group_ids': [(4, env.ref('analytic.group_analytic_accounting').id)]})
# Multi-almacen / ubicaciones para que las vistas de conduce muestren todo
admin.write({'group_ids': [(4, env.ref('stock.group_stock_multi_locations').id)]})
print('Contabilidad analitica activada para %s' % admin.login)

# ════════════════════════════════════════════════════════════════════════════
# 2. PLAN ANALITICO + CUENTAS (OBRAS) + PROYECTO NATIVO
# ════════════════════════════════════════════════════════════════════════════
Plan = env['account.analytic.plan']
plan = Plan.search([('name', '=', 'Proyectos')], limit=1) or Plan.create({'name': 'Proyectos'})
plan_column = plan._column_name()

Account = env['account.analytic.account']
def get_account(code, name):
    acc = Account.search([('code', '=', code)], limit=1)
    if not acc:
        acc = Account.create({'code': code, 'name': name, 'plan_id': plan.id,
                              'company_id': company.id})
    return acc

obra_a = get_account('PROY-001', 'Planta Solar Bavaro')
obra_b = get_account('PROY-002', 'Techo Solar Santiago')
obra_c = get_account('PROY-003', 'Parque Solar Azua')
print('Plan analitico: %s (columna %s)' % (plan.name, plan_column))
for a in (obra_a, obra_b, obra_c):
    print('  cuenta %-9s %s' % (a.code, a.name))

Project = env['project.project']
project = Project.search([('name', '=', 'Parque Solar Azua')], limit=1)
if not project:
    project = Project.create({'name': 'Parque Solar Azua'})
project.write({plan_column: obra_c.id})
print('Proyecto nativo: %s -> cuenta %s' % (project.name, obra_c.code))

# ════════════════════════════════════════════════════════════════════════════
# 3. PRODUCTOS ALMACENABLES A COSTO ESTANDAR + EXISTENCIA
# ════════════════════════════════════════════════════════════════════════════
Categ = env['product.category']
categ = Categ.search([('name', '=', 'Materiales Solares')], limit=1)
if not categ:
    categ = Categ.create({
        'name': 'Materiales Solares',
        'property_cost_method': 'standard',
        'property_valuation': 'periodic',
    })

warehouse = env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
stock_location = warehouse.lot_stock_id
customer_location = env.ref('stock.stock_location_customers')
supplier_location = env.ref('stock.stock_location_suppliers')
uom_unit = env.ref('uom.product_uom_unit')

Product = env['product.product']
def get_product(code, name, price):
    p = Product.search([('default_code', '=', code)], limit=1)
    if not p:
        p = Product.create({
            'name': name,
            'default_code': code,
            'is_storable': True,
            'categ_id': categ.id,
            'uom_id': uom_unit.id,
            'standard_price': price,
        })
    p.standard_price = price
    return p

panel = get_product('SOL-PANEL', 'Panel solar 550W', 12500.0)
inversor = get_product('SOL-INV', 'Inversor 5kW', 45000.0)
estructura = get_product('SOL-EST', 'Estructura de montaje', 3200.0)

Quant = env['stock.quant']
for prod, qty in ((panel, 500), (inversor, 60), (estructura, 400)):
    Quant._update_available_quantity(prod, stock_location, qty)
    print('Existencia %-24s %6.0f u  costo %10.2f' % (prod.display_name, qty, prod.standard_price))

# ════════════════════════════════════════════════════════════════════════════
# 4. ESCENARIOS
# ════════════════════════════════════════════════════════════════════════════
Picking = env['stock.picking']
Move = env['stock.move']
type_out = warehouse.out_type_id
type_in = warehouse.in_type_id

def build_picking(origin, lines, picking_type=None, project_rec=None):
    """lines = [(product, qty, distribution|None)]"""
    picking_type = picking_type or type_out
    incoming = picking_type.code == 'incoming'
    src = supplier_location if incoming else stock_location
    dst = stock_location if incoming else customer_location
    vals = {
        'picking_type_id': picking_type.id,
        'location_id': src.id,
        'location_dest_id': dst.id,
        'origin': origin,
    }
    if project_rec:
        vals['project_id'] = project_rec.id
    picking = Picking.create(vals)
    for product, qty, distribution in lines:
        Move.create({
            'product_id': product.id,
            'product_uom_qty': qty,
            'product_uom': product.uom_id.id,
            'picking_id': picking.id,
            'location_id': src.id,
            'location_dest_id': dst.id,
            'analytic_distribution': distribution,
        })
    picking.action_confirm()
    picking.action_assign()
    for move in picking.move_ids:
        move.quantity = move.product_uom_qty
    return picking

def show(title, picking):
    line()
    print('%s  [%s]  estado=%s' % (title, picking.name, picking.state))
    aals = picking.move_ids.analytic_account_line_ids
    if not aals:
        print('   sin partidas analiticas')
        return
    for aal in aals:
        print('   %-24s %-9s %12.2f  %6.2f u  categoria=%s' % (
            aal.product_id.display_name,
            (aal[plan_column].code or '-') if aal[plan_column] else '-',
            aal.amount, aal.unit_amount, aal.category))

# A. Conduce validado, 100 % a una obra
pick_a = build_picking('OBRA PROY-001 / despacho 1', [
    (panel, 20, {str(obra_a.id): 100}),
    (estructura, 20, {str(obra_a.id): 100}),
])
pick_a.move_ids.picked = True
pick_a.button_validate()
show('A. Conduce VALIDADO, 100% a PROY-001', pick_a)

# B. Conduce marcado pero SIN validar, reparto 60/40 (caso del cliente)
pick_b = build_picking('OBRAS PROY-001 + PROY-002 / despacho compartido', [
    (inversor, 4, {str(obra_a.id): 60, str(obra_b.id): 40}),
])
pick_b.move_ids.picked = True
show('B. Conduce SIN VALIDAR (picked), reparto 60/40 -> costo estimado', pick_b)

# C. Conduce sin distribucion
pick_c = build_picking('Despacho sin imputar', [(panel, 5, None)])
pick_c.move_ids.picked = True
pick_c.button_validate()
show('C. Conduce validado SIN distribucion', pick_c)

# D. Desecho con distribucion
Scrap = env['stock.scrap']
scrap = Scrap.create({
    'product_id': panel.id,
    'product_uom_id': panel.uom_id.id,
    'scrap_qty': 2,
    'location_id': stock_location.id,
    'origin': 'Panel roto en obra PROY-002',
    'analytic_distribution': {str(obra_b.id): 100},
})
scrap.action_validate()
line()
print('D. Desecho %s  estado=%s' % (scrap.name, scrap.state))
for aal in scrap.move_ids.analytic_account_line_ids:
    print('   %-24s %-9s %12.2f  %6.2f u' % (
        aal.product_id.display_name,
        aal[plan_column].code or '-', aal.amount, aal.unit_amount))

# E. Flujo nativo: proyecto en el conduce + costos analiticos en el tipo
type_out.analytic_costs = True
pick_e = build_picking('Proyecto Azua / despacho nativo',
                       [(panel, 8, None)], project_rec=project)
pick_e.move_ids.picked = True
pick_e.button_validate()
show('E. Conduce con PROYECTO (flujo nativo, sin distribucion manual)', pick_e)

# F. Proyecto + distribucion manual -> gana la manual, sin doble conteo
pick_f = build_picking('Proyecto Azua / despacho reimputado',
                       [(inversor, 2, {str(obra_a.id): 100})], project_rec=project)
pick_f.move_ids.picked = True
pick_f.button_validate()
show('F. Conduce con PROYECTO + distribucion MANUAL (gana la manual)', pick_f)

# ════════════════════════════════════════════════════════════════════════════
# 5. VERIFICACION
# ════════════════════════════════════════════════════════════════════════════
line('=')
print('ACUMULADO POR CUENTA ANALITICA (partidas de inventario)')
line('=')
AAL = env['account.analytic.line']
for acc in (obra_a, obra_b, obra_c):
    aals = AAL.search([(plan_column, '=', acc.id)])
    print('%-9s %-24s  %3d partidas  total %14.2f' % (
        acc.code, acc.name, len(aals), sum(aals.mapped('amount'))))

line('=')
moves_manual = env['stock.move'].search([('analytic_distribution', '!=', False)])
print('Movimientos con distribucion manual : %d' % len(moves_manual))
print('Partidas analiticas de esos movimientos: %d' % len(moves_manual.analytic_account_line_ids))
dupes = [m.display_name for m in moves_manual
         if len(m.analytic_account_line_ids) > len(m.analytic_distribution or {})]
print('Movimientos con partidas duplicadas : %s' % (dupes or 'ninguno'))

env.cr.commit()
line('=')
print('SEED OK. DB lista.')
PYEOF

echo ""
echo "======================================================"
echo " Listo. Abre http://localhost:${ODOO_PORT:-8069} y entra a $DB_NAME"
echo " Usuario: admin / admin"
echo ""
echo " Donde mirar:"
echo "   Inventario > Transferencias        -> columna Distribucion analitica"
echo "   Contabilidad > Partidas analiticas -> costo por obra"
echo "   Proyecto > Parque Solar Azua       -> Rentabilidad (Materiales)"
echo "======================================================"
