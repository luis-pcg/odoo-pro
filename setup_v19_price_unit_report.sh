#!/bin/bash
# setup_v19_price_unit_report.sh
#
# Crea una DB NUEVA para validar price_unit_display_precision >= 19.0.2.1.0,
# el arreglo del PRECIO UNITARIO EN LOS REPORTES (no solo en las vistas):
#
#   v19 declara price_unit como Float(min_display_digits='Product Price') sin
#   digits. En un reporte QWeb <span t-field="line.price_unit"/> pasa por
#   ir.qweb.field.float.record_to_html, que le pide la precision al campo, no
#   la encuentra y cae al tope de 6 decimales. El digits="[16, N]" que el
#   modulo inyecta en _get_view NO llega al reporte: un reporte no pasa por
#   _get_view. El modulo ahora tambien sobreescribe el converter.
#
# La DB queda sembrada con:
#   * Cotizacion S00001 «caso cliente»: 108 x 2,110.00, 13% de descuento de
#     linea y DOS descuentos globales de 1.50% -> lineas de descuento con
#     price_unit -2973.834 y -2929.22649 en la base.
#   * Su factura de cliente, confirmada.
#   * Cotizacion S00002 «valor crudo»: price_unit 1.234567.
#   * Orden de compra con price_unit 12.345678.
#   Ajuste PRENDIDO en 2 decimales (Ajustes > Generales > Precio unitario).
#
# Que validar (admin/admin):
#   1. Imprimir la cotizacion y la factura: el Precio unitario sale 2,973.83.
#      Antes salia 2,973.834.
#   2. Ajustes > Generales > Precio unitario > Decimales = 4 -> imprime
#      2,973.834. Desmarcar el checkbox -> vuelven los 6 digitos.
#      Sin reiniciar el servidor.
#   3. La orden de compra imprime 12.35 (el reporte de compra tambien usa
#      t-field, y no hace falta modulo puente).
#   4. Los totales no cambian nunca.
#
# Uso:
#   ./setup_v19_price_unit_report.sh                # crea DB v19_price_unit_report
#   ./setup_v19_price_unit_report.sh --recreate     # borra y recrea si existe
#   ./setup_v19_price_unit_report.sh --db=mi_db     # nombre personalizado
#   ./setup_v19_price_unit_report.sh --skip-install # DB ya instalada, solo siembra
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="sale_management,purchase,hr_expense,price_unit_display_precision"

DB_NAME="v19_price_unit_report"
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
echo " Setup precio unitario en REPORTES — $MODULES"
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

  echo "→ Instalando $MODULES con datos demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los modulos' >&2; exit 1; }
fi

echo "→ Sembrando documentos con decimales de sobra..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import logging
import re

logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

# ────────────────────────────────────────────────────────────────────────────
# 0. AJUSTE PRENDIDO EN 2 DECIMALES + admin/admin
# ────────────────────────────────────────────────────────────────────────────
params = env['ir.config_parameter'].sudo()
params.set_param('price_unit_display_precision.enabled', 'True')
params.set_param('price_unit_display_precision.digits', '2')
env.registry.clear_cache('templates')

admin = env.ref('base.user_admin')
admin.write({'login': 'admin', 'password': 'admin'})

company = env.company

# ────────────────────────────────────────────────────────────────────────────
# 1. CLIENTE, PROVEEDOR Y PRODUCTO
# ────────────────────────────────────────────────────────────────────────────
Partner = env['res.partner']
customer = Partner.create({'name': 'Cliente Decimales SRL'})
vendor = Partner.create({'name': 'Proveedor Decimales SRL'})
product = env['product.product'].create({
    'name': 'Servicio con decimales',
    'type': 'service',
    'invoice_policy': 'order',
    'list_price': 2110.0,
    'standard_price': 12.345678,
    'purchase_ok': True,
})

# ────────────────────────────────────────────────────────────────────────────
# 2. CASO CLIENTE: descuentos globales encadenados que compuestan decimales
# ────────────────────────────────────────────────────────────────────────────
so = env['sale.order'].create({
    'partner_id': customer.id,
    'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 108})],
})
so.order_line.price_unit = 2110.0
for discount_type, percentage in (
    ('sol_discount', 0.13), ('so_discount', 0.015), ('so_discount', 0.015),
):
    env['sale.order.discount'].create({
        'sale_order_id': so.id,
        'discount_type': discount_type,
        'discount_percentage': percentage,
    }).action_apply_discount()
so.action_confirm()
invoice = so._create_invoices()
invoice.action_post()

print('Cotizacion %s — price_unit en la base:' % so.name)
for sol in so.order_line:
    print('   %-40s %r' % (sol.name.splitlines()[0][:40], sol.price_unit))
print('Factura %s (%s), total %s' % (invoice.name, invoice.state, invoice.amount_total))

# ────────────────────────────────────────────────────────────────────────────
# 3. VALOR CRUDO: 6 decimales escritos a mano, sin descuentos de por medio
# ────────────────────────────────────────────────────────────────────────────
so2 = env['sale.order'].create({
    'partner_id': customer.id,
    'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': 3})],
})
so2.order_line.price_unit = 1.234567
print('Cotizacion %s — price_unit %r' % (so2.name, so2.order_line.price_unit))

# ────────────────────────────────────────────────────────────────────────────
# 4. COMPRAS: cubierta por el mismo codigo, sin modulo puente
# ────────────────────────────────────────────────────────────────────────────
po = env['purchase.order'].create({
    'partner_id': vendor.id,
    'order_line': [(0, 0, {'product_id': product.id, 'product_qty': 3})],
})
po.order_line.price_unit = 12.345678
print('Orden de compra %s — price_unit %r' % (po.name, po.order_line.price_unit))

# ────────────────────────────────────────────────────────────────────────────
# 5. COMPROBACION: el mismo render que hace el PDF
# ────────────────────────────────────────────────────────────────────────────
def printed(report, records):
    html = env['ir.actions.report']._render_qweb_html(report, records.ids)[0].decode()
    return re.sub(r'<[^>]+>', ' ', html)

line('=')
for label, report, records, digits, expected, unexpected in (
    ('Cotizacion', 'sale.report_saleorder', so, 2, '2,973.83', '2,973.834'),
    ('Factura', 'account.report_invoice', invoice, 2, '2,973.83', '2,973.834'),
    ('Compra', 'purchase.report_purchaseorder', po, 2, '12.35', '12.345678'),
    ('Cotizacion', 'sale.report_saleorder', so, 4, '2,973.834', '2,973.8340'),
):
    params.set_param('price_unit_display_precision.digits', str(digits))
    env.registry.clear_cache('templates')
    text = printed(report, records)
    ok = expected in text and unexpected not in text
    print('%-11s %d decimales -> %-10s %s' % (
        label, digits, expected, 'OK' if ok else 'REVISAR (no imprime %s)' % expected))

params.set_param('price_unit_display_precision.digits', '2')
env.registry.clear_cache('templates')

env.cr.commit()
line('=')
print('DB sembrada. admin/admin')
PYEOF

echo
echo "======================================================"
echo " Listo: $DB_NAME"
echo " http://localhost:${ODOO_PORT:-8092}/odoo  (admin/admin)"
echo
echo " 1. Ventas > $DB_NAME: cotizacion S00001 -> Imprimir > Cotizacion."
echo "    Precio unitario de las lineas de descuento = 2,973.83 / 2,929.23."
echo " 2. Su factura: mismo precio unitario, mismos totales."
echo " 3. Ajustes > Generales > Precio unitario > Decimales = 4 -> reimprimir:"
echo "    2,973.834. Desmarcar el checkbox -> 2,973.834 / 2,929.22649."
echo " 4. Compras: la orden imprime 12.35 sin modulo puente."
echo "======================================================"
