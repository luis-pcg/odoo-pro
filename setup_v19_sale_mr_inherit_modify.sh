#!/bin/bash
# setup_v19_sale_mr_inherit_modify.sh
#
# Crea una base de datos NUEVA para probar funcionalmente el modulo
# sale_mr_inherit_modify (calculo dimensional Pieza x Altura) en Odoo 19:
#
#   1. Crea la DB v19_sale_mr_inherit_modify e instala sale_mr_inherit_modify
#      CON datos demo (partners, productos, pedidos de venta con dimensiones,
#      BoMs y ordenes de fabricacion vinculadas).
#   2. Valida las 4 vistas heredadas del modulo: renderiza cada vista padre
#      combinada (get_view) y verifica que los campos/botones del modulo
#      aparezcan en el arch resultante.
#   3. Imprime los datos demo para exploracion manual via web (admin/admin).
#
# Vistas validadas:
#   - sale.view_order_form                             (new_qty, new_height)
#   - mrp.mrp_production_form_view                     (qty_sale, height_sale,
#                                                       sale_line_id, partner_id,
#                                                       vendedor)
#   - stock.view_picking_form                          (boton find_qty)
#   - stock.view_stock_move_line_detailed_operation_tree (new_qty, new_height)
#
# Uso:
#   ./setup_v19_sale_mr_inherit_modify.sh                  # crea DB nueva
#   ./setup_v19_sale_mr_inherit_modify.sh --db=mi_db       # nombre personalizado
#   ./setup_v19_sale_mr_inherit_modify.sh --recreate       # borra y recrea si existe
#   ./setup_v19_sale_mr_inherit_modify.sh --skip-install   # DB ya instalada, solo valida
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="sale_mr_inherit_modify"

DB_NAME="v19_sale_mr_inherit_modify"
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
echo " Setup sale_mr_inherit_modify — validacion de vistas"
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
      echo "ERROR: la DB $DB_NAME ya existe. Usa --recreate para reemplazarla o --skip-install para solo validar." >&2
      exit 1
    fi
  fi

  echo "→ Creando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULES CON datos demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --with-demo --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los modulos' >&2; exit 1; }
fi

echo "→ Validando vistas heredadas y datos demo..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

failures = []

# ════════════════════════════════════════════════════════════════════════════
# 1. VISTAS DEL MODULO: activas y con parent correcto
# ════════════════════════════════════════════════════════════════════════════
line('=')
print('1. Vistas registradas por sale_mr_inherit_modify')
line('=')
data = env['ir.model.data'].search([
    ('module', '=', 'sale_mr_inherit_modify'),
    ('model', '=', 'ir.ui.view'),
])
if not data:
    failures.append('No se encontraron vistas del modulo en ir.model.data')
for d in data.sorted('name'):
    v = env['ir.ui.view'].browse(d.res_id)
    print('  %-38s model=%-16s hereda=%s activa=%s' % (
        d.name, v.model, v.inherit_id.name or '-', v.active))
    if not v.active:
        failures.append('Vista %s inactiva' % d.name)

# ════════════════════════════════════════════════════════════════════════════
# 2. RENDER COMBINADO: get_view valida xpaths + campos en el arch final
# ════════════════════════════════════════════════════════════════════════════
line('=')
print('2. Render combinado (get_view) de las vistas padre')
line('=')
CHECKS = [
    ('sale.order', 'sale.view_order_form',
     ['name="new_qty"', 'name="new_height"']),
    ('mrp.production', 'mrp.mrp_production_form_view',
     ['name="qty_sale"', 'name="height_sale"', 'name="sale_line_id"',
      'name="partner_id"', 'name="vendedor"']),
    ('stock.picking', 'stock.view_picking_form',
     ['name="find_qty"']),
    ('stock.move.line', 'stock.view_stock_move_line_detailed_operation_tree',
     ['name="new_qty"', 'name="new_height"']),
]
for model, xmlid, expected in CHECKS:
    view = env.ref(xmlid)
    try:
        arch = env[model].get_view(view.id, view.type)['arch']
    except Exception as e:
        failures.append('%s: get_view fallo: %s' % (xmlid, e))
        print('  ✗ %-55s ERROR: %s' % (xmlid, e))
        continue
    missing = [x for x in expected if x not in arch]
    if missing:
        failures.append('%s: faltan %s en el arch' % (xmlid, missing))
        print('  ✗ %-55s faltan: %s' % (xmlid, missing))
    else:
        print('  ✓ %-55s (%d elementos del modulo presentes)' % (xmlid, len(expected)))

# Posicion en la lista de lineas de venta: Pieza/Altura antes de Cantidad
sale_arch = env['sale.order'].get_view(env.ref('sale.view_order_form').id, 'form')['arch']
i_piece = sale_arch.find('name="new_qty"')
i_qty = sale_arch.find('name="product_uom_qty"', i_piece)
if i_piece == -1 or i_qty == -1:
    failures.append('sale: no se pudo verificar el orden Pieza/Altura vs Cantidad')
else:
    print('  ✓ new_qty/new_height aparecen antes de product_uom_qty en la lista')

# ════════════════════════════════════════════════════════════════════════════
# 3. DATOS DEMO: pedidos y ordenes de fabricacion con dimensiones
# ════════════════════════════════════════════════════════════════════════════
line('=')
print('3. Datos demo para exploracion manual')
line('=')
orders = env['sale.order'].search([('order_line.new_qty', '>', 0)])
if not orders:
    failures.append('Sin pedidos demo con dimensiones (¿demo no cargado?)')
for o in orders:
    print('  Pedido %-12s cliente=%s' % (o.name, o.partner_id.name))
    for l in o.order_line:
        print('      %-32s pieza=%-6s altura=%-6s qty=%s' % (
            l.product_id.display_name[:32], l.new_qty, l.new_height, l.product_uom_qty))
mos = env['mrp.production'].search([('sale_line_id', '!=', False)])
if not mos:
    failures.append('Sin ordenes de fabricacion demo vinculadas a lineas de venta')
for mo in mos:
    print('  MO %-14s producto=%-28s qty_sale=%-5s height_sale=%-5s cliente=%s vendedor=%s' % (
        mo.name, mo.product_id.display_name[:28], mo.qty_sale, mo.height_sale,
        mo.partner_id.name or '-', mo.vendedor.name or '-'))

# ════════════════════════════════════════════════════════════════════════════
# RESULTADO
# ════════════════════════════════════════════════════════════════════════════
line('=')
if failures:
    print('RESULTADO: %d FALLO(S)' % len(failures))
    for f in failures:
        print('  ✗ %s' % f)
    import sys
    sys.exit(1)
print('RESULTADO: TODAS LAS VISTAS OK')
line('=')
PYEOF
RC=$?
if [[ $RC -ne 0 ]]; then
  echo "ERROR: la validacion de vistas fallo (rc=$RC)" >&2
  exit $RC
fi

PORT="$(docker port "$CONTAINER" 8069/tcp 2>/dev/null | head -1 | awk -F: '{print $NF}')"
echo ""
echo "Listo. DB '$DB_NAME' creada y vistas validadas."
echo "Web: http://localhost:${PORT:-8069}/odoo?db=$DB_NAME (admin/admin)"
echo "Rutas de prueba manual:"
echo "  - Ventas > Pedidos: columnas Piece/Height antes de Cantidad en las lineas"
echo "  - Fabricacion > Ordenes: campos de venta bajo la BoM"
echo "  - Inventario > Transferencia: boton 'Ver Cantidades' + Operaciones detalladas"
