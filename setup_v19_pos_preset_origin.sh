#!/bin/bash
# setup_v19_pos_preset_origin.sh
#
# Crea y configura una base de datos NUEVA (sin datos demo) para probar a mano
# el modulo pos_preset_by_order_origin en Odoo 19: el preajuste del PdV se
# deduce del origen de la orden (mesa -> Comer en el local, venta directa ->
# Para llevar, y la venta directa que pasa a una mesa cambia sola).
#
# Que hace:
#
#   1. Crea la DB v19_pos_preset_origin e instala pos_preset_by_order_origin
#      (arrastra pos_restaurant -> point_of_sale).
#   2. Compania "Pasteleria del Jardin" (RD, DOP) con plan contable generico.
#   3. Tres productos de pasteleria y un metodo de pago en efectivo.
#   4. Un PdV en modo restaurante con un piso "Salon" y cuatro mesas.
#   5. Los dos preajustes de fabrica renombrados y silenciosos (sin
#      identificacion ni franjas horarias): Comer en el local / Para llevar.
#   6. Los ajustes del modulo: En mesa = Comer en el local, Venta directa =
#      Para llevar, Predeterminado = Para llevar.
#   7. Verifica que los tres campos quedaron puestos y que los dos preajustes
#      viajan al frontend (dominio de carga de pos.preset).
#
# Los datos se COMMITEAN (la DB queda lista para usar via web).
#
# Uso:
#   ./setup_v19_pos_preset_origin.sh                  # crea DB nueva
#   ./setup_v19_pos_preset_origin.sh --db=mi_db       # nombre propio
#   ./setup_v19_pos_preset_origin.sh --recreate       # borra y recrea
#   ./setup_v19_pos_preset_origin.sh --skip-install   # solo siembra
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="pos_preset_by_order_origin"

DB_NAME="v19_pos_preset_origin"
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
echo " Setup preajuste de PdV segun el origen de la orden"
echo " Modulo     : $MODULE"
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
      -i $MODULE --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
fi

echo "→ Configurando compania, PdV, mesas, preajustes y productos..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

company = env.ref('base.main_company')
do = env.ref('base.do')
admin = env.ref('base.user_admin')

# ════════════════════════════════════════════════════════════════════════════
# 1. IDIOMA, COMPANIA Y PLAN CONTABLE
# ════════════════════════════════════════════════════════════════════════════
es = env['res.lang']._activate_lang('es_DO')
try:
    env['base.language.install'].create(
        {'lang_ids': [(6, 0, [es.id])], 'overwrite': True}
    ).lang_install()
except Exception:
    env.cr.rollback()
admin.lang = 'es_DO'
env = env(context=dict(env.context, lang='es_DO'))
company = company.with_env(env)

company.write({'name': 'Pastelería del Jardín', 'country_id': do.id})
company.partner_id.lang = 'es_DO'
if not company.chart_template:
    env['account.chart.template'].try_loading('generic_coa', company=company, install_demo=False)
dop = env.ref('base.DOP')
dop.active = True
if company.currency_id != dop:
    company.currency_id = dop

# ════════════════════════════════════════════════════════════════════════════
# 2. PRODUCTOS Y METODO DE PAGO
# ════════════════════════════════════════════════════════════════════════════
categ = env['pos.category'].create({'name': 'Pastelería'})
products = env['product.template'].create([
    {
        'name': name,
        'list_price': price,
        'type': 'consu',
        'available_in_pos': True,
        'pos_categ_ids': [(6, 0, categ.ids)],
        'taxes_id': [(6, 0, [])],
    }
    for name, price in (
        ('Suspiro de fresa', 180.00),
        ('Brownie de nuez', 140.00),
        ('Café con leche', 95.00),
    )
])

cash_journal = env['account.journal'].search(
    [('type', '=', 'cash'), ('company_id', '=', company.id)], limit=1)
if not cash_journal:
    cash_journal = env['account.journal'].create(
        {'name': 'Efectivo', 'code': 'CSH', 'type': 'cash', 'company_id': company.id})
cash_method = env['pos.payment.method'].create(
    {'name': 'Efectivo', 'journal_id': cash_journal.id, 'company_id': company.id})

# ════════════════════════════════════════════════════════════════════════════
# 3. PDV EN MODO RESTAURANTE: UN PISO Y CUATRO MESAS
# ════════════════════════════════════════════════════════════════════════════
config = env['pos.config'].create({
    'name': 'Salón Pastelería',
    'module_pos_restaurant': True,
    'company_id': company.id,
    'payment_method_ids': [(6, 0, cash_method.ids)],
    'iface_available_categ_ids': [(6, 0, categ.ids)],
})
config.floor_ids.unlink()
floor = env['restaurant.floor'].create(
    {'name': 'Salón', 'pos_config_ids': [(6, 0, config.ids)]})
env['restaurant.table'].create([
    {
        'table_number': number,
        'floor_id': floor.id,
        'seats': 4,
        'shape': 'square',
        'position_h': position_h,
        'position_v': position_v,
    }
    for number, position_h, position_v in (
        (1, 120, 120), (2, 340, 120), (3, 120, 320), (4, 340, 320),
    )
])

# ════════════════════════════════════════════════════════════════════════════
# 4. PREAJUSTES SILENCIOSOS
# ════════════════════════════════════════════════════════════════════════════
# Los de fabrica piden nombre (Takeout) o direccion (Delivery) y abrirían un
# dialogo en cada orden: el modulo asigna el preajuste sin pasar por ellos.
dine_in = env.ref('pos_restaurant.pos_takein_preset')
takeaway = env.ref('pos_restaurant.pos_takeout_preset')
dine_in.write({'name': 'Comer en el local', 'identification': 'none', 'use_timing': False})
takeaway.write({
    'name': 'Para llevar',
    'identification': 'none',
    'use_timing': False,
    'resource_calendar_id': False,
})

# ════════════════════════════════════════════════════════════════════════════
# 5. LOS AJUSTES DEL MODULO
# ════════════════════════════════════════════════════════════════════════════
# Predeterminado = venta directa: es lo que permite que una venta directa vacia
# adopte la mesa que el cajero toca, en lugar de quedar huerfana en las tabs.
config.write({
    'use_presets': True,
    'available_preset_ids': [(6, 0, (takeaway | dine_in).ids)],
    'default_preset_id': takeaway.id,
    'direct_sale_preset_id': takeaway.id,
    'table_preset_id': dine_in.id,
})

# ════════════════════════════════════════════════════════════════════════════
# 6. VERIFICACION
# ════════════════════════════════════════════════════════════════════════════
line('=')
print(' VERIFICACION')
line('=')
ok = True

checks = [
    ('Modo restaurante', config.module_pos_restaurant, True),
    ('Preajustes activos', config.use_presets, True),
    ('Predeterminado', config.default_preset_id, takeaway),
    ('En mesa', config.table_preset_id, dine_in),
    ('Venta directa', config.direct_sale_preset_id, takeaway),
    ('Mesas del piso', len(floor.table_ids), 4),
]
for label, got, expected in checks:
    good = got == expected
    ok = ok and good
    name = got.name if hasattr(got, 'name') else got
    print(' %-22s %-24s %s' % (label + ':', name, 'OK' if good else 'FALLA'))

# Los dos preajustes tienen que viajar al frontend, o el many2one llega como un
# id colgante y el modulo "no hace nada" en silencio.
loaded = env['pos.preset'].search(env['pos.preset']._load_pos_data_domain({}, config))
for preset in (dine_in, takeaway):
    good = preset in loaded
    ok = ok and good
    print(' %-22s %-24s %s' % ('Carga al frontend:', preset.name, 'OK' if good else 'FALLA'))

for preset in (dine_in, takeaway):
    good = preset.identification == 'none' and not preset.use_timing
    ok = ok and good
    print(' %-22s %-24s %s' % ('Preajuste silencioso:', preset.name, 'OK' if good else 'FALLA'))

line()
print(' Productos: %s' % ', '.join(products.mapped('name')))
print(' Moneda   : %s' % company.currency_id.name)
line('=')

if ok:
    print(' OK: PdV listo para probar los tres escenarios. Commiteando...')
else:
    print(' ERROR: alguna verificacion fallo. Se commitea igual para inspeccionar.')
env.cr.commit()
PYEOF

STATUS=$?
echo
if [[ $STATUS -eq 0 ]]; then
  echo "======================================================"
  echo " DB lista: $DB_NAME"
  echo " URL      : http://localhost:${ODOO_PORT:-8069}"
  echo " Login    : admin / admin"
  echo " Probar:"
  echo "   1. Punto de venta → Salón Pastelería → Abrir caja registradora."
  echo "   2. Tocar la mesa 2       → la orden nace 'Comer en el local'."
  echo "   3. Mesas → Nueva orden   → la orden nace 'Para llevar'."
  echo "   4. Agregar un producto y 'Asignar mesa' → 4 → 'Asignar':"
  echo "      pasa a 'Comer en el local' sin cambiar el total."
  echo "   5. Cambiar el preajuste a mano: el automatismo no lo vuelve a tocar."
  echo " Ajustes  : Ajustes → Punto de venta → Para llevar / Entrega / Miembros"
  echo " Re-sembrar sin reinstalar: $0 --db=$DB_NAME --skip-install"
  echo "======================================================"
else
  echo "ERROR: el sembrado fallo (exit $STATUS). DB conservada para inspeccion: $DB_NAME"
fi
exit $STATUS
