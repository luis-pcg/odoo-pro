#!/bin/bash
# setup_v19_do_report_test.sh
#
# Crea una DB NUEVA para probar los ARREGLOS DEL REPORTE DE FACTURA DO
# (rama 19.0-fix-l10n_do_rnc_validation-02-lf), l10n_do_accounting >= 19.0.1.0.8:
#
#   1. Caja de totales en moneda de la compania (opt-in): Ajustes > Contabilidad
#      > seccion "Currencies" > "Show invoice totals in company currency (DO)".
#      Se deja PRENDIDA + una factura en USD para ver la caja.
#   2. Subtotal/Total/Monto Gravado en NEGRO forzado en Boxed: ahora en <strong>.
#      Layout por defecto = Boxed y colores oscuros para que se note el contraste.
#   3. Tagline (report_header): ahora sale en TODAS las plantillas (custom_header).
#      Se setea el tagline + logo de la compania.
#   4. Columna "Monto descuento" (e-CF) que desalineaba el subtotal de seccion:
#      factura e-CF con secciones + descuentos.
#   5. invoice_reference_type con opcion "None" (apagado): el diario de venta se
#      deja en "None" (Contabilidad > Config > Diarios > Ajustes avanzados).
#   6. Bubble: logo se solapaba con la tabla desde la pag. 2 + paginacion cortada
#      al fondo: factura MULTIPAGINA para verlo (probar cambiando layout a Bubble).
#
# La DB queda commiteada y lista (admin/admin).
#
# Uso:
#   ./setup_v19_do_report_test.sh                 # crea DB v19_do_report_test
#   ./setup_v19_do_report_test.sh --recreate      # borra y recrea si existe
#   ./setup_v19_do_report_test.sh --db=mi_db      # nombre personalizado
#   ./setup_v19_do_report_test.sh --skip-install  # DB ya instalada, solo siembra
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="l10n_do_accounting,l10n_do_document_pools"

DB_NAME="v19_do_report_test"
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
echo " Setup TEST reporte factura DO — $MODULES"
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

  echo "→ Instalando $MODULES sin datos demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los modulos' >&2; exit 1; }
fi

echo "→ Configurando compania, secuencias NCF y facturas de prueba del reporte..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import base64
import struct
import zlib
from datetime import date

from odoo import fields

import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

today = date.today()
expiration = date(today.year + 2, 12, 31)

# ────────────────────────────────────────────────────────────────────────────
# 1. COMPANIA: pais RD, RNC, moneda DOP, logo, tagline, colores, layout Boxed
# ────────────────────────────────────────────────────────────────────────────
company = env.ref('base.main_company')
do = env.ref('base.do')
dop = env.ref('base.DOP')
dop.active = True
company.write({
    'name': 'Empresa Fiscal Dominicana SRL',
    'country_id': do.id,
    'city': 'Santo Domingo',
    'phone': '809-555-0100',
    'vat': '131793898',
})
company.partner_id.write({
    'country_id': do.id,
    'l10n_do_dgii_tax_payer_type': 'taxpayer',
})
try:
    company.currency_id = dop.id
except Exception as e:
    print('AVISO: no se pudo cambiar la moneda a DOP (%s)' % e)


def make_png(w, h, rgb):
    """PNG solido WxH sin dependencias externas (para logo de prueba)."""
    def chunk(typ, data):
        return (struct.pack('>I', len(data)) + typ + data
                + struct.pack('>I', zlib.crc32(typ + data) & 0xffffffff))
    row = b'\x00' + bytes(rgb) * w
    raw = row * h
    sig = b'\x89PNG\r\n\x1a\n'
    ihdr = struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)
    idat = zlib.compress(raw)
    return sig + chunk(b'IHDR', ihdr) + chunk(b'IDAT', idat) + chunk(b'IEND', b'')

# logo (bloque azul oscuro) + tagline + colores oscuros + layout Boxed
company.logo = base64.b64encode(make_png(260, 90, (11, 54, 99)))
company.report_header = '<p>Su aliado fiscal en Rep. Dominicana — TAGLINE DE PRUEBA</p>'
company.primary_color = '#0b3663'
company.secondary_color = '#1a7fa8'
try:
    company.external_report_layout_id = env.ref('web.external_layout_boxed').id
except Exception as e:
    print('AVISO: no se pudo fijar layout Boxed (%s)' % e)

# CAMBIO 1: caja de totales en moneda de la compania (opt-in) — PRENDIDA
company.l10n_do_display_tax_company_currency = True

# FACTURACION ELECTRONICA: la compania es EMISORA e-CF -> emite E-NCF
# (E31/E32/E34...). is_ecf_invoice sale True de forma natural por el doc type,
# sin necesidad de certificado (la firma/envio DGII es de l10n_do_ecf_invoicing).
company.l10n_do_ecf_issuer = True
print('Compania: %s | logo+tagline OK | layout=%s | caja_moneda_cia=%s | ecf_issuer=%s' % (
    company.name, company.external_report_layout_id.name,
    company.l10n_do_display_tax_company_currency, company.l10n_do_ecf_issuer))

# ────────────────────────────────────────────────────────────────────────────
# 2. PLAN CONTABLE DOMINICANO
# ────────────────────────────────────────────────────────────────────────────
if company.chart_template != 'do':
    print('Cargando plan contable DO (era %s)...' % company.chart_template)
    env['account.chart.template'].try_loading('do', company, install_demo=False, force_create=True)
if company.account_fiscal_country_id != do:
    company.account_fiscal_country_id = do.id
print('Plan contable: %s | pais fiscal=%s' % (
    company.chart_template, company.account_fiscal_country_id.code))

# ────────────────────────────────────────────────────────────────────────────
# 3. MONEDA USD + TASA (para la factura en moneda extranjera / caja moneda cia)
# ────────────────────────────────────────────────────────────────────────────
usd = env.ref('base.USD')
usd.active = True
env['res.currency.rate'].search([('currency_id', '=', usd.id),
                                 ('company_id', '=', company.id)]).unlink()
env['res.currency.rate'].create({
    'currency_id': usd.id,
    'company_id': company.id,
    'name': date(today.year, 1, 1),
    'rate': 1.0 / 60.0,  # 1 USD = 60 DOP
})
print('Moneda USD activa | tasa 1 USD = 60 DOP')

# ────────────────────────────────────────────────────────────────────────────
# 4. GESTOR DE SECUENCIAS NCF + POOLS + diario de venta con ref = None (CAMBIO 5)
# ────────────────────────────────────────────────────────────────────────────
company.l10n_do_sequence_manager = True
sale_journal = env['account.journal'].search(
    [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
purchase_journal = env['account.journal'].search(
    [('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
if not sale_journal or not purchase_journal:
    raise Exception('Faltan diarios de venta/compra')
for journal in (sale_journal, purchase_journal):
    if not journal.l10n_latam_use_documents:
        journal.l10n_latam_use_documents = True

# CAMBIO 5: la opcion "None" (apagado) queda DISPONIBLE en el diario
# (Contabilidad > Config > Diarios > Ventas > Ajustes avanzados). Se deja el
# default core 'invoice'; cambiar a "None" manualmente para apagar la
# comunicacion de pago y ver que "Communication Standard" se oculta.
sale_journal.l10n_do_payment_form = 'cash'   # forma de pago DGII (e-CF)
print('Diario venta %s: invoice_reference_type=%s (opcion "None" disponible)' % (
    sale_journal.code, sale_journal.invoice_reference_type))

# Pools e-CF (E-NCF): E31 credito fiscal, E32 consumo, E34 nota credito
SALE_POOLS = [
    ('e-fiscal',      'AUT-E31-0001', 1, 1000),
    ('e-consumer',    'AUT-E32-0001', 1, 1000),
    ('e-credit_note', 'AUT-E34-0001', 1, 200),
]

def configure_pools(journal, pools):
    doc_types = env['l10n_do.account.journal.document_type'].search(
        [('journal_id', '=', journal.id)])
    by_type = {dt.l10n_do_ncf_type: dt for dt in doc_types if dt.l10n_do_ncf_type}
    configured = {}
    for ncf_type, auth, seq_start, seq_end in pools:
        dt = by_type.get(ncf_type)
        if not dt:
            print('  [skip] tipo NCF no disponible en %s: %s' % (journal.code, ncf_type))
            continue
        dt.write({
            'auth_number': auth,
            'sequence_start': seq_start,
            'sequence_end': seq_end,
            'l10n_do_ncf_expiration_date': expiration,
            'state': 'valid',
        })
        configured[ncf_type] = dt
        print('  [ok] pool %-12s %s-%s' % (ncf_type, seq_start, seq_end))
    return configured

print('Pools de venta (%s):' % sale_journal.code)
sale_pools = configure_pools(sale_journal, SALE_POOLS)

# ────────────────────────────────────────────────────────────────────────────
# 5. PARTNERS Y PRODUCTOS
# ────────────────────────────────────────────────────────────────────────────
def get_partner(name, vat, payer_type, is_company=True):
    p = env['res.partner'].search([('vat', '=', vat)], limit=1)
    if not p:
        p = env['res.partner'].create({
            'name': name,
            'company_type': 'company' if is_company else 'person',
            'vat': vat,
            'l10n_do_dgii_tax_payer_type': payer_type,
            'country_id': do.id,
            'customer_rank': 1,
        })
    return p

cust_rnc = get_partner('MARCOS ORGANIZADOR DE NEGOCIOS SRL', '131098193', 'taxpayer')
cust_ced = get_partner('JOSE LUIS LOPEZ GONZALEZ', '22400559690', 'non_payer', is_company=False)

# productos: uno gravado ITBIS 18%, uno exento (sin impuesto) para Monto Exento
sale_tax = env['account.tax'].search(
    [('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
     ('amount', '=', 18.0)], limit=1)
prod_grav = env['product.product'].search([('name', '=', 'Producto Gravado 18%')], limit=1)
if not prod_grav:
    prod_grav = env['product.product'].create({
        'name': 'Producto Gravado 18%', 'list_price': 1000.0,
        'standard_price': 600.0, 'type': 'consu',
        'taxes_id': [(6, 0, sale_tax.ids)] if sale_tax else False,
    })
prod_exento = env['product.product'].search([('name', '=', 'Producto Exento')], limit=1)
if not prod_exento:
    prod_exento = env['product.product'].create({
        'name': 'Producto Exento', 'list_price': 500.0,
        'standard_price': 300.0, 'type': 'consu', 'taxes_id': [(6, 0, [])],
    })
print('Partners/productos OK (tax18=%s)' % (bool(sale_tax)))

# ────────────────────────────────────────────────────────────────────────────
# 6. FACTURAS DE PRUEBA
# ────────────────────────────────────────────────────────────────────────────
line('=')
print('Publicando facturas de prueba del reporte')
line('=')
posted = {}

def L(prod, qty, price, disc=0.0):
    return (0, 0, {
        'product_id': prod.id, 'name': prod.name, 'quantity': qty,
        'price_unit': price, 'discount': disc,
        'tax_ids': [(6, 0, prod.taxes_id.ids)],
    })

def SEC(name):
    return (0, 0, {'display_type': 'line_section', 'name': name})

def post(vals, key):
    with env.cr.savepoint():
        m = env['account.move'].create(vals)
        m.action_post()
        posted[key] = m
        print('  [ok] %-10s NCF=%-14s lineas=%d total=%.2f %s' % (
            key, m.name, len(m.invoice_line_ids), m.amount_total, m.currency_id.name))
        return m

dt_e31 = sale_pools['e-fiscal'].l10n_latam_document_type_id     # E31 credito fiscal
dt_e32 = sale_pools['e-consumer'].l10n_latam_document_type_id   # E32 consumo

# (A) MULTIPAGINA con secciones + descuentos (CAMBIOS 2,3,6 + subtotal seccion)
big_lines = [SEC('GRUPO A — PRODUCTOS')]
for i in range(14):
    big_lines.append(L(prod_grav, 1 + (i % 3), 1000.0 + i * 25, disc=(10.0 if i % 4 == 0 else 0.0)))
big_lines.append(SEC('GRUPO B — MAS PRODUCTOS'))
for i in range(14):
    big_lines.append(L(prod_grav, 2, 900.0 + i * 15, disc=(15.0 if i % 5 == 0 else 0.0)))
big_lines.append(L(prod_exento, 3, 500.0))  # linea exenta
post({
    'move_type': 'out_invoice', 'partner_id': cust_rnc.id,
    'journal_id': sale_journal.id, 'invoice_date': today,
    'l10n_latam_document_type_id': dt_e31.id,
    'invoice_line_ids': big_lines,
}, 'MULTIPAGINA_E31')

# (B) USD — caja de totales en moneda de la compania (CAMBIO 1)
post({
    'move_type': 'out_invoice', 'partner_id': cust_rnc.id,
    'journal_id': sale_journal.id, 'invoice_date': today,
    'currency_id': usd.id,
    'l10n_latam_document_type_id': dt_e31.id,
    'invoice_line_ids': [L(prod_grav, 5, 100.0), L(prod_grav, 2, 250.0, disc=10.0)],
}, 'USD_E31')

# (C) e-CF con seccion + descuentos (CAMBIO 4: columna Monto descuento alineada)
post({
    'move_type': 'out_invoice', 'partner_id': cust_rnc.id,
    'journal_id': sale_journal.id, 'invoice_date': today,
    'l10n_latam_document_type_id': dt_e31.id,
    'invoice_line_ids': [
        SEC('SERVICIOS'),
        L(prod_grav, 2, 1500.0, disc=10.0),
        L(prod_grav, 1, 3000.0, disc=25.0),
        L(prod_exento, 4, 500.0),
    ],
}, 'ECF_E31')

# (D) Consumo electronico E32
post({
    'move_type': 'out_invoice', 'partner_id': cust_ced.id,
    'journal_id': sale_journal.id, 'invoice_date': today,
    'l10n_latam_document_type_id': dt_e32.id,
    'invoice_line_ids': [L(prod_grav, 1, 1000.0)],
}, 'CONSUMO_E32')

# Timbre electronico (QR): con security_code + sign_date el reporte pinta el QR
# e-NCF. is_ecf_invoice ya es True de forma natural (doc type E##).
for k, m in posted.items():
    if m.is_ecf_invoice:
        m.write({
            'l10n_do_ecf_security_code': 'aB3xZ9',
            'l10n_do_ecf_sign_date': fields.Datetime.now(),
        })
print('  [ok] QR e-NCF poblado en %d facturas e-CF' % sum(1 for m in posted.values() if m.is_ecf_invoice))

# ────────────────────────────────────────────────────────────────────────────
# 7. ADMIN + COMMIT
# ────────────────────────────────────────────────────────────────────────────
env.ref('base.user_admin').password = 'admin'
env.cr.commit()
line('=')
print('Facturas listas para imprimir:')
for k, m in posted.items():
    print('  %-14s %s  (id=%d)' % (k, m.name, m.id))
line('=')
print('=== SEED DONE — DB lista (admin/admin) ===')
PYEOF

status=$?
if [[ $status -ne 0 ]]; then
  echo "ERROR: el seed fallo (exit $status)" >&2
  exit $status
fi

echo ""
echo "======================================================"
echo " DB lista: $DB_NAME"
echo " URL     : http://localhost:${ODOO_PORT:-8092}/odoo  (admin/admin)"
echo ""
echo " IMPORTANTE: reinicia el contenedor para cargar el python nuevo:"
echo "   docker restart $CONTAINER"
echo "======================================================"
