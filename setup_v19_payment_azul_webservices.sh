#!/bin/bash
# setup_v19_payment_azul_webservices.sh
#
# Crea y configura una base de datos NUEVA (sin datos demo) para trabajar el
# proveedor de pago Azul (payment_azul_webservices) en Odoo 19:
#
#   1. Crea la DB v19_payment_azul_webservices e instala payment_azul_webservices
#      (arrastra payment, website_sale).
#   2. Copia los certs mTLS de pruebas al contenedor
#      (progressa.local.crt / progressa-dev-unencrypted.key).
#   3. Configura la compania (pais RD, moneda DOP) y el proveedor Azul en modo
#      TEST: MID 39038540035, auth 3dsecure/3dsecure, certs PEM, 3DS activo,
#      publicado en el website.
#   4. Crea un producto publicado para probar el checkout.
#   5. Sanity check: construye el cliente PyAzul desde el provider (valida
#      certs + settings, sin llamada de red).
#
# Los datos se COMMITEAN (la DB queda lista para usar via web).
#
# Uso:
#   ./setup_v19_payment_azul_webservices.sh                  # crea DB nueva
#   ./setup_v19_payment_azul_webservices.sh --db=mi_db       # nombre personalizado
#   ./setup_v19_payment_azul_webservices.sh --recreate       # borra y recrea si existe
#   ./setup_v19_payment_azul_webservices.sh --skip-install   # DB ya instalada, solo configura
#
#   export AZUL_CERT_DIR=/ruta/a/certs   (default: ../dev_env_odoo_pro-17/certs)
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="payment_azul_webservices"
CERT_DIR="${AZUL_CERT_DIR:-$SCRIPT_DIR/../dev_env_odoo_pro-17/certs}"

DB_NAME="v19_payment_azul_webservices"
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
echo " Setup Azul Webservices — $MODULE"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo " Certs      : $CERT_DIR"
echo "======================================================"

# Verificar certs locales antes de tocar nada
if [[ ! -f "$CERT_DIR/progressa.local.crt" || ! -f "$CERT_DIR/progressa-dev-unencrypted.key" ]]; then
  echo "ERROR: faltan certs mTLS en '$CERT_DIR'." >&2
  echo "       Se esperan: progressa.local.crt y progressa-dev-unencrypted.key" >&2
  echo "       Ajusta con: export AZUL_CERT_DIR=<ruta>" >&2
  exit 1
fi

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
      echo "ERROR: la DB $DB_NAME ya existe. Usa --recreate para reemplazarla o --skip-install para solo configurar." >&2
      exit 1
    fi
  fi

  echo "→ Creando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULE sin datos demo (arrastra website_sale, puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
fi

echo "→ Copiando certs mTLS al contenedor..."
docker cp "$CERT_DIR/progressa.local.crt" "$CONTAINER:/tmp/azul_cert.pem" || exit 1
docker cp "$CERT_DIR/progressa-dev-unencrypted.key" "$CONTAINER:/tmp/azul_key.pem" || exit 1

echo "→ Configurando compania, proveedor Azul y producto de prueba..."
docker exec -i "$CONTAINER" bash -lc "
  ODOO_PORT_HOST=${ODOO_PORT:-8069} odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import base64
import logging
import os

logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

# ════════════════════════════════════════════════════════════════════════════
# 1. COMPANIA: pais RD, moneda DOP
# ════════════════════════════════════════════════════════════════════════════
company = env.ref('base.main_company')
do = env.ref('base.do')
dop = env.ref('base.DOP')
dop.active = True
company.write({
    'name': 'Comercio Dominicano SRL',
    'country_id': do.id,
    'city': 'Santo Domingo',
    'phone': '809-555-0200',
})
try:
    company.currency_id = dop.id
    for pricelist in env['product.pricelist'].search([]):
        pricelist.currency_id = dop.id
    print('Compania: %s | pais=%s moneda=%s' % (
        company.name, company.country_id.code, company.currency_id.name))
except Exception as e:
    env.cr.rollback()
    print('AVISO: no se pudo cambiar la moneda a DOP (%s). Azul convierte USD->DOP.' % e)

# ════════════════════════════════════════════════════════════════════════════
# 2. PROVEEDOR AZUL: modo test, credenciales de pruebas, certs mTLS
# ════════════════════════════════════════════════════════════════════════════
with open('/tmp/azul_cert.pem', 'rb') as f:
    cert_b64 = base64.b64encode(f.read())
with open('/tmp/azul_key.pem', 'rb') as f:
    key_b64 = base64.b64encode(f.read())

provider = env.ref('payment_azul_webservices.payment_provider_azul')
provider.write({
    'state': 'test',
    'is_published': True,
    'azul_webservices_merchant_account': '39038540035',
    'azul_webservices_auth_1': '3dsecure',
    'azul_webservices_auth_2': '3dsecure',
    'azul_webservices_cert_pem': cert_b64,
    'azul_webservices_cert_pem_filename': 'progressa.local.crt',
    'azul_webservices_key_pem': key_b64,
    'azul_webservices_key_pem_filename': 'progressa-dev-unencrypted.key',
    'azul_webservices_enable_3ds': True,
    'azul_webservices_challenge_indicator': '01',
})
# available_currency_ids es compute stored que corrio en el install con DOP aun
# inactiva (quedo solo USD); refrescar para que el checkout en DOP encuentre el
# provider (_get_compatible_providers filtra por esta lista).
provider.available_currency_ids = provider._get_supported_currencies()
print('Monedas soportadas: %s' % ', '.join(provider.available_currency_ids.mapped('name')))
print('Provider: %s | state=%s MID=%s 3DS=%s publicado=%s' % (
    provider.name, provider.state, provider.azul_webservices_merchant_account,
    provider.azul_webservices_enable_3ds, provider.is_published))
print('Metodos de pago: %s' % ', '.join(provider.payment_method_ids.mapped('name')))

# web.base.url estable para callbacks 3DS en pruebas locales
port = os.environ.get('ODOO_PORT_HOST', '8069')
env['ir.config_parameter'].sudo().set_param('web.base.url', 'http://localhost:%s' % port)
print('web.base.url = http://localhost:%s' % port)

# ════════════════════════════════════════════════════════════════════════════
# 3. PRODUCTO PUBLICADO para probar el checkout
# ════════════════════════════════════════════════════════════════════════════
product = env['product.template'].create({
    'name': 'Producto de Prueba Azul',
    'list_price': 1500.00,
    'sale_ok': True,
    'website_published': True,
    'description_sale': 'Producto para probar pagos con Azul (ambiente de pruebas).',
})
print('Producto: %s | RD$%s publicado=%s' % (
    product.name, '{:,.2f}'.format(product.list_price), product.website_published))

# ════════════════════════════════════════════════════════════════════════════
# 4. SANITY CHECK: construir cliente PyAzul desde el provider (sin red)
# ════════════════════════════════════════════════════════════════════════════
line('=')
from odoo.addons.payment_azul_webservices import utils as azul_utils
client = azul_utils.get_pyazul_client(provider)
line('#')
if client is not None:
    print(' OK: cliente PyAzul construido (certs y settings validos). Commiteando...')
    env.cr.commit()
else:
    print(' ERROR: get_pyazul_client devolvio None. Revisar campos/certs del provider.')
    print(' Se commitea igual para poder inspeccionar via web.')
    env.cr.commit()
PYEOF

STATUS=$?
echo
if [[ $STATUS -eq 0 ]]; then
  echo "======================================================"
  echo " DB lista: $DB_NAME"
  echo " URL      : http://localhost:${ODOO_PORT:-8069}"
  echo " Login    : admin / admin"
  echo " Checkout : http://localhost:${ODOO_PORT:-8069}/shop"
  echo " Tarjeta test 3DS: ver docs del modulo / Documento E-commerce Azul"
  echo " Re-configurar sin reinstalar: $0 --db=$DB_NAME --skip-install"
  echo "======================================================"
else
  echo "ERROR: la configuracion fallo (exit $STATUS). DB conservada para inspeccion: $DB_NAME"
fi
exit $STATUS
