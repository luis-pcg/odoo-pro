#!/bin/bash
# setup_v19_l10n_do_accounting.sh
#
# Crea y configura una base de datos NUEVA para probar la facturacion fiscal
# dominicana (NCF) en Odoo 19:
#
#   1. Crea la DB v19_l10n_do_accounting e instala l10n_do_accounting +
#      l10n_do_document_pools (gestor de secuencias NCF).
#   2. Configura la compania: pais RD, RNC, moneda DOP, plan contable DO.
#   3. Activa el gestor de secuencias (l10n_do_sequence_manager).
#   4. Activa "usa documentos" en los diarios de venta y compra; configura los
#      pools de NCF (B01/B02/B03/B04/B12/B14/B15/B16 en venta, B11/B13/B17 en
#      compra) con autorizacion, rango y vencimiento.
#   5. Crea clientes/suplidores de prueba de cada tipo de contribuyente DGII
#      (RNC/cedulas validos) y productos de prueba.
#   6. Sanity check: publica facturas B01/B02/B14/B15, una nota de credito B04,
#      una nota de debito B03 y una factura de compra B11; imprime NCF asignados
#      y secuencias restantes por pool.
#
# Los datos se COMMITEAN (la DB queda lista para usar via web, admin/admin).
#
# Uso:
#   ./setup_v19_l10n_do_accounting.sh                  # crea DB nueva
#   ./setup_v19_l10n_do_accounting.sh --db=mi_db       # nombre personalizado
#   ./setup_v19_l10n_do_accounting.sh --recreate       # borra y recrea si existe
#   ./setup_v19_l10n_do_accounting.sh --skip-install   # DB ya instalada, solo siembra
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v17"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="l10n_do_accounting,l10n_do_document_pools"

DB_NAME="v17_607_forms"
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
echo " Setup fiscal dominicano — $MODULES"
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

echo "→ Configurando compania, secuencias NCF y data de prueba..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
from datetime import date

import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 78)

today = date.today()
expiration = date(today.year + 2, 12, 31)

# ════════════════════════════════════════════════════════════════════════════
# 1. COMPANIA: pais RD, RNC, moneda DOP
# ════════════════════════════════════════════════════════════════════════════
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
print('Compania: %s | pais=%s RNC=%s moneda=%s' % (
    company.name, company.country_id.code, company.vat, company.currency_id.name))

# ════════════════════════════════════════════════════════════════════════════
# 2. PLAN CONTABLE DOMINICANO (impuestos ITBIS incluidos)
# ════════════════════════════════════════════════════════════════════════════
if company.chart_template != 'do':
    print('Cargando plan contable DO (era %s)...' % company.chart_template)
    env['account.chart.template'].try_loading('do', company, install_demo=False)
if company.account_fiscal_country_id != do:
    company.account_fiscal_country_id = do.id
print('Plan contable: %s | pais fiscal=%s' % (
    company.chart_template, company.account_fiscal_country_id.code))

# ════════════════════════════════════════════════════════════════════════════
# 3. GESTOR DE SECUENCIAS NCF
# ════════════════════════════════════════════════════════════════════════════
company.l10n_do_sequence_manager = True
print('Gestor de secuencias NCF: ACTIVADO')

# ════════════════════════════════════════════════════════════════════════════
# 4. DIARIOS CON DOCUMENTOS + POOLS DE NCF
# ════════════════════════════════════════════════════════════════════════════
sale_journal = env['account.journal'].search(
    [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
purchase_journal = env['account.journal'].search(
    [('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
if not sale_journal or not purchase_journal:
    raise Exception('Faltan diarios de venta/compra')
for journal in (sale_journal, purchase_journal):
    if not journal.l10n_latam_use_documents:
        journal.l10n_latam_use_documents = True
print('Diarios con documentos: %s / %s' % (sale_journal.name, purchase_journal.name))

# (ncf_type, autorizacion, inicio, fin)
SALE_POOLS = [
    ('fiscal',       'AUT-B01-0001', 1, 1000),  # B01 credito fiscal
    ('consumer',     'AUT-B02-0001', 1, 1000),  # B02 consumo
    ('debit_note',   'AUT-B03-0001', 1, 200),   # B03 nota de debito
    ('credit_note',  'AUT-B04-0001', 1, 200),   # B04 nota de credito
    ('unique',       'AUT-B12-0001', 1, 100),   # B12 unico ingreso
    ('special',      'AUT-B14-0001', 1, 100),   # B14 regimenes especiales
    ('governmental', 'AUT-B15-0001', 1, 100),   # B15 gubernamental
    ('export',       'AUT-B16-0001', 1, 100),   # B16 exportacion
]
PURCHASE_POOLS = [
    ('informal',     'AUT-B11-0001', 1, 500),   # B11 compras a informales
    ('minor',        'AUT-B13-0001', 1, 200),   # B13 gastos menores
    ('exterior',     'AUT-B17-0001', 1, 100),   # B17 pagos al exterior
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
        print('  [ok] pool %-12s %s-%s auth=%s vence=%s' % (
            ncf_type, seq_start, seq_end, auth, expiration))
    return configured

print('Pools de venta (%s):' % sale_journal.code)
sale_pools = configure_pools(sale_journal, SALE_POOLS)
print('Pools de compra (%s):' % purchase_journal.code)
purchase_pools = configure_pools(purchase_journal, PURCHASE_POOLS)

# ════════════════════════════════════════════════════════════════════════════
# 5. PARTNERS DE PRUEBA (RNC/cedulas validos) Y PRODUCTOS
# ════════════════════════════════════════════════════════════════════════════
PARTNERS = [
    # (nombre, vat, tipo DGII, es_compania, rank)
    ('MARCOS ORGANIZADOR DE NEGOCIOS SRL', '131098193', 'taxpayer', True, 'customer'),
    ('ITERATIVO SRL', '131566332', 'taxpayer', True, 'customer'),
    ('JOSE LUIS LOPEZ GONZALEZ', '22400559690', 'non_payer', False, 'customer'),
    ('ZONA FRANCA INDUSTRIAL DE LAS AMERICAS S A', '101168481', 'special', True, 'customer'),
    ('MINISTERIO DE INDUSTRIA Y COMERCIO Y MIPYMES', '401007355', 'governmental', True, 'customer'),
    ('FOOD FOR THE HUNGRY Y DOM', '401051842', 'nonprofit', True, 'customer'),
    ('INDEXA SRL', '131793916', 'taxpayer', True, 'supplier'),
    ('KEVIN JIMENEZ LORENZO', '40222200327', 'non_payer', False, 'supplier'),
]
partners = {}
for name, vat, payer_type, is_company, rank in PARTNERS:
    partner = env['res.partner'].search([('vat', '=', vat)], limit=1)
    if not partner:
        partner = env['res.partner'].create({
            'name': name,
            'company_type': 'company' if is_company else 'person',
            'vat': vat,
            'l10n_do_dgii_tax_payer_type': payer_type,
            'country_id': do.id,
            'customer_rank': 1 if rank == 'customer' else 0,
            'supplier_rank': 1 if rank == 'supplier' else 0,
        })
    partners[vat] = partner
    print('  [ok] partner %-45s %s (%s)' % (name[:45], vat, payer_type))

# Extranjero (exportacion B16)
foreigner = env['res.partner'].search([('name', '=', 'ACME EXPORT LLC')], limit=1)
if not foreigner:
    foreigner = env['res.partner'].create({
        'name': 'ACME EXPORT LLC',
        'company_type': 'company',
        'country_id': env.ref('base.us').id,
        'vat': '98-7654321',  # tax id extranjero: requerido para NCF de exportacion (B16)
        'l10n_do_dgii_tax_payer_type': 'foreigner',
        'customer_rank': 1,
    })
print('  [ok] partner %-45s (foreigner, US)' % foreigner.name)

products = {}
for name, price in [('Producto Gravado', 1000.0), ('Servicio de Consultoria', 2500.0)]:
    product = env['product.product'].search([('name', '=', name)], limit=1)
    if not product:
        product = env['product.product'].create({
            'name': name, 'list_price': price, 'standard_price': price * 0.6,
            'type': 'service' if 'Servicio' in name else 'consu',
        })
    products[name] = product
    print('  [ok] producto %-30s RD$ %.2f' % (name, price))

# ════════════════════════════════════════════════════════════════════════════
# 6. SANITY CHECK: FACTURAS DE CADA TIPO
# ════════════════════════════════════════════════════════════════════════════
line('=')
print('SANITY CHECK — publicando documentos fiscales')
line('=')

posted = []

def make_invoice(partner, ncf_type, pool_map, journal, move_type='out_invoice', lines=None):
    """Crea y publica una factura con el tipo de NCF dado. Devuelve el move o None."""
    dt = pool_map.get(ncf_type)
    if not dt:
        print('  [skip] sin pool para %s' % ncf_type)
        return None
    lines = lines or [(products['Producto Gravado'], 2.0, 1000.0)]
    vals = {
        'move_type': move_type,
        'partner_id': partner.id,
        'journal_id': journal.id,
        'invoice_date': today,
        'l10n_latam_document_type_id': dt.l10n_latam_document_type_id.id,
        'invoice_line_ids': [(0, 0, {
            'product_id': p.id, 'quantity': q, 'price_unit': pu, 'name': p.name,
        }) for p, q, pu in lines],
    }
    try:
        with env.cr.savepoint():
            move = env['account.move'].create(vals)
            move.action_post()
            posted.append(move)
            print('  [ok] %-12s NCF=%-14s partner=%-35s total=%.2f' % (
                ncf_type, move.name, partner.name[:35], move.amount_total))
            return move
    except Exception as e:
        print('  [FALLO] %s: %s' % (ncf_type, e))
        return None

# B01 credito fiscal
inv_b01 = make_invoice(partners['131098193'], 'fiscal', sale_pools, sale_journal,
                       lines=[(products['Producto Gravado'], 2.0, 1000.0),
                              (products['Servicio de Consultoria'], 1.0, 2500.0)])
# B02 consumo
make_invoice(partners['22400559690'], 'consumer', sale_pools, sale_journal)
# B14 regimenes especiales
make_invoice(partners['101168481'], 'special', sale_pools, sale_journal)
# B15 gubernamental
make_invoice(partners['401007355'], 'governmental', sale_pools, sale_journal)
# B16 exportacion
make_invoice(foreigner, 'export', sale_pools, sale_journal)

# B04 nota de credito (reversa parcial de la B01 via wizard)
if inv_b01:
    try:
        with env.cr.savepoint():
            wiz = env['account.move.reversal'].with_context(
                active_model='account.move', active_ids=inv_b01.ids,
            ).create({
                'journal_id': inv_b01.journal_id.id,
                'reason': 'Devolucion de mercancia',
                'l10n_do_refund_type': 'percentage',
                'l10n_do_percentage': 50.0,
            })
            action = wiz.reverse_moves()
            refund = env['account.move'].browse(action['res_id'])
            refund.action_post()
            posted.append(refund)
            print('  [ok] %-12s NCF=%-14s modifica=%s total=%.2f' % (
                'credit_note', refund.name, refund.l10n_do_origin_ncf, refund.amount_total))
    except Exception as e:
        print('  [FALLO] credit_note: %s' % e)

# B03 nota de debito (via wizard)
if inv_b01:
    try:
        with env.cr.savepoint():
            income_account = env['account.account'].search(
                [('account_type', '=', 'income')], limit=1)
            wiz = env['account.debit.note'].with_context(
                active_model='account.move', active_ids=inv_b01.ids,
            ).create({
                'reason': 'Ajuste de precio',
                'l10n_do_debit_type': 'fixed_amount',
                'l10n_do_amount': 500.0,
                'l10n_do_account_id': income_account.id,
            })
            action = wiz.create_debit()
            debit = env['account.move'].browse(action['res_id'])
            debit.action_post()
            posted.append(debit)
            print('  [ok] %-12s NCF=%-14s modifica=%s total=%.2f' % (
                'debit_note', debit.name, debit.l10n_do_origin_ncf, debit.amount_total))
    except Exception as e:
        print('  [FALLO] debit_note: %s' % e)

# B11 compra a informal
supplier = partners['40222200327']
supplier.l10n_do_expense_type = '02'
make_invoice(supplier, 'informal', purchase_pools, purchase_journal,
             move_type='in_invoice',
             lines=[(products['Servicio de Consultoria'], 1.0, 8000.0)])

# ════════════════════════════════════════════════════════════════════════════
# 7. RESUMEN DE POOLS
# ════════════════════════════════════════════════════════════════════════════
line('=')
print('POOLS — secuencias restantes')
line('=')
try:
    for journal in (sale_journal, purchase_journal):
        for dt in env['l10n_do.account.journal.document_type'].search(
                [('journal_id', '=', journal.id), ('state', '=', 'valid')]):
            print('  %-6s %-14s vence=%s' % (
                journal.code, dt.l10n_do_ncf_type, dt.l10n_do_ncf_expiration_date))
except Exception as e:
    print('  [skip] resumen de pools no disponible: %s' % e)

line('=')
print('%d documentos publicados' % len(posted))

# ════════════════════════════════════════════════════════════════════════════
# 8. PASSWORD ADMIN + COMMIT
# ════════════════════════════════════════════════════════════════════════════
env.ref('base.user_admin').password = 'admin'
env.cr.commit()
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
echo " URL     : http://localhost:8090/odoo  (admin/admin)"
echo "======================================================"
