#!/bin/bash
# replicate_withholding_cert_invoice_tax.sh
#
# Replica el bug reportado en la instancia odoo-vasalf-staging:
#
#   1. El boton "Print Certification" no aparece en los pagos.
#   2. El reporte "Withholding Certification" sale completamente en blanco.
#
# Causa: l10n_do_withholding_certification (v19) solo detecta retencion en
# account.payment.withholding.line (flujo nativo v19). Las bases migradas de
# v17 llevan la retencion como impuestos negativos SOBRE LA FACTURA de
# proveedor, asi que esa tabla queda vacia, has_l10n_do_withholding = False y:
#   - el boton queda oculto  (invisible="... or not has_l10n_do_withholding")
#   - la plantilla del reporte esta envuelta en t-if="o.has_l10n_do_withholding"
#     => PDF/HTML vacio.
#
# El script arma esa misma forma de datos en una DB local:
#   - Compania RD, plan contable 'do', DOP.
#   - Factura de proveedor con el grupo de retencion "10% Serv." del plan DO
#     (18% ITBIS + -18% ret ITBIS + -10% ret ISR) => lineas de impuesto de
#     retencion en la factura.
#   - Pago outbound registrado y conciliado con esa factura.
#   - Despues se marcan los impuestos con is_withholding_tax_on_payment = True
#     y las cuentas con is_l10n_do_withholding_account = True, replicando el
#     estado post-migracion de staging.
#
# Uso:
#   ./replicate_withholding_cert_invoice_tax.sh --recreate   # crea DB, siembra y diagnostica
#   ./replicate_withholding_cert_invoice_tax.sh              # solo diagnostica (siembra si falta)
#   ./replicate_withholding_cert_invoice_tax.sh --update     # actualiza el modulo (corre la
#                                                            # migracion) y diagnostica
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="l10n_do_withholding_certification"

DB_NAME="v19_wh_cert_invoice_tax"
RECREATE=false
UPDATE=false
for arg in "$@"; do
  case "$arg" in
    --recreate) RECREATE=true ;;
    --update)   UPDATE=true ;;
    --db=*)     DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Replica: certificacion de retencion sin boton / en blanco"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo "======================================================"

db_exists() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$DB_NAME'\"" \
    | grep -q 1
}

if $RECREATE; then
  if db_exists; then
    echo "→ Eliminando DB $DB_NAME..."
    docker exec "$CONTAINER" bash -lc "
      PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
        \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid()\" >/dev/null
      PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
    " || { echo 'ERROR eliminando la DB' >&2; exit 1; }
  fi
  echo "→ Creando DB $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULE sin demo (varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --stop-after-init --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el modulo' >&2; exit 1; }
elif ! db_exists; then
  echo "ERROR: la DB $DB_NAME no existe. Usa --recreate." >&2
  exit 1
fi

if $UPDATE; then
  echo "→ Actualizando $MODULE (dispara los scripts de migracion)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -u $MODULE --stop-after-init --max-cron-threads=0 --workers=0 2>&1 \
      | grep -Ei 'l10n_do_withholding_certification|has_l10n_do_withholding|withholding line|ERROR|CRITICAL' \
      | tail -30
  " || { echo 'ERROR actualizando el modulo' >&2; exit 1; }
fi

echo "→ Sembrando (si falta) y diagnosticando..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
import re
from datetime import date

import logging
logging.disable(logging.WARNING)

REF = 'WHCERT-REPRO'


def line(c='='):
    print(c * 78)


# ════════════════════════════════════════════════════════════════════════════
# 1. COMPANIA RD + PLAN CONTABLE 'do'
# ════════════════════════════════════════════════════════════════════════════
company = env.ref('base.main_company')
do = env.ref('base.do')
dop = env.ref('base.DOP')
dop.active = True
company.write({
    'name': 'Retenciones Repro SRL',
    'country_id': do.id,
    'city': 'Santo Domingo',
    'vat': '131793898',
    'l10n_do_withholding_cert_type': 'private',
})
company.partner_id.write({'country_id': do.id, 'l10n_do_dgii_tax_payer_type': 'taxpayer'})
try:
    company.currency_id = dop.id
except Exception as e:
    print('AVISO: no se pudo fijar DOP (%s)' % e)
if company.chart_template != 'do':
    print('Cargando plan contable DO (era %s)...' % company.chart_template)
    env['account.chart.template'].try_loading('do', company, install_demo=False, force_create=True)
if company.account_fiscal_country_id != do:
    company.account_fiscal_country_id = do.id
print('Compania: %s | pais fiscal=%s | plan=%s | moneda=%s' % (
    company.name, company.account_fiscal_country_id.code, company.chart_template, company.currency_id.name))

# ════════════════════════════════════════════════════════════════════════════
# 2. SIEMBRA: factura de proveedor con retencion en los impuestos + pago
# ════════════════════════════════════════════════════════════════════════════
# El asiento del pago hereda el mismo ref, filtrar por tipo para no confundirlos.
bill = env['account.move'].search([('ref', '=', REF), ('move_type', '=', 'in_invoice')], limit=1)

if not bill:
    partner = env['res.partner'].search([('ref', '=', REF)], limit=1)
    if not partner:
        partner = env['res.partner'].create({
            'name': 'Felix Quintin Ferreras Mendez',
            'ref': REF,
            'company_type': 'person',
            'country_id': do.id,
            'vat': '00113918205',
            'l10n_do_dgii_tax_payer_type': 'non_payer',
        })

    product = env['product.product'].search([('default_code', '=', REF)], limit=1)
    if not product:
        product = env['product.product'].create({
            'name': 'Servicios de Consultoria Legal',
            'default_code': REF,
            'type': 'service',
            'supplier_taxes_id': [(5, 0, 0)],
        })

    # Grupo de retencion del plan DO: 18% ITBIS + -18% ret ITBIS + -10% ret ISR.
    # OJO: se aplica ANTES de marcar is_withholding_tax_on_payment, igual que en
    # v17 -- si el flag ya estuviera puesto, el core los excluiria de la factura.
    wh_group = env['account.tax'].search([
        ('company_id', '=', company.id),
        ('amount_type', '=', 'group'),
        ('type_tax_use', '=', 'purchase'),
        ('description', 'ilike', 'Person Services'),
    ], limit=1)
    if not wh_group:
        raise Exception('No se encontro el grupo de retencion "10% Serv." del plan DO')
    taxes = wh_group.children_tax_ids or wh_group
    print('Impuestos aplicados: %s' % ', '.join(taxes.mapped('name')))

    journal = env['account.journal'].search(
        [('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
    journal.l10n_latam_use_documents = False

    bill = env['account.move'].create({
        'move_type': 'in_invoice',
        'partner_id': partner.id,
        'journal_id': journal.id,
        'ref': REF,
        'invoice_date': date(date.today().year, 1, 15),
        'date': date(date.today().year, 1, 15),
        'invoice_line_ids': [(0, 0, {
            'product_id': product.id,
            'name': 'Servicios de consultoria legal enero',
            'quantity': 1,
            'price_unit': 5555.56,
            'tax_ids': [(6, 0, taxes.ids)],
        })],
    })
    bill.action_post()
    print('Factura %s publicada | total=%s' % (bill.name, bill.amount_total))

    wizard = env['account.payment.register'].with_context(
        active_model='account.move', active_ids=bill.ids
    ).create({})
    wizard.action_create_payments()
    env.flush_all()
    print('Pago registrado.')
    env.cr.commit()

payment = bill.matched_payment_ids[:1]
if not payment:
    # matched_payment_ids no siempre se computa; buscar por conciliacion.
    apr = bill.line_ids.mapped('matched_debit_ids') + bill.line_ids.mapped('matched_credit_ids')
    counterparts = apr.mapped('debit_move_id') + apr.mapped('credit_move_id')
    payment = counterparts.mapped('payment_id')[:1]
if not payment:
    raise Exception('No se encontro el pago conciliado con %s' % bill.name)

# ════════════════════════════════════════════════════════════════════════════
# 3. ESTADO POST-MIGRACION: flags que trae staging
# ════════════════════════════════════════════════════════════════════════════
wh_tax_lines = bill.line_ids.filtered(lambda l: l.tax_line_id and l.tax_line_id.amount < 0)
if not wh_tax_lines:
    raise Exception('La factura no genero lineas de impuesto de retencion')

LEGAL_BASE = {'ITBIS': 'Norma R293-11', 'ISR': 'Norma 07-2019'}
for aml in wh_tax_lines:
    tax = aml.tax_line_id
    if not tax.is_withholding_tax_on_payment:
        tax.is_withholding_tax_on_payment = True   # lo que hace el post_init_hook / migracion
    kind = 'ITBIS' if 'ITBIS' in tax.name.upper() else 'ISR'
    aml.account_id.write({
        'is_l10n_do_withholding_account': True,
        'l10n_do_tax_name': 'Retencion %s' % kind,
        'l10n_do_legal_base': LEGAL_BASE[kind],
    })
env.flush_all()
env.cr.commit()

# ════════════════════════════════════════════════════════════════════════════
# 4. DIAGNOSTICO
# ════════════════════════════════════════════════════════════════════════════
line()
print(' DIAGNOSTICO')
line()
print('Factura      : %s | total=%s (ya neto de retencion)' % (bill.name, bill.amount_total))
for aml in wh_tax_lines:
    print('  ret tax    : %-42s cuenta=%s monto=%s' % (
        aml.tax_line_id.name, aml.account_id.code, abs(aml.balance)))
print('Pago         : %s | tipo=%s | estado=%s | monto=%s' % (
    payment.name, payment.payment_type, payment.state, payment.amount))
print('withholding_line_ids (flujo nativo v19) : %d' % len(payment.withholding_line_ids))

if hasattr(payment, '_get_invoice_withholding_by_account'):
    detected = payment._get_invoice_withholding_by_account()
    print('retencion detectada en la factura        : %s' % (
        {a.code: v for a, v in detected.items()} or '{}'))
else:
    print('retencion detectada en la factura        : (metodo no existe en esta version)')

payment.invalidate_recordset(['has_l10n_do_withholding'])
flag = payment.has_l10n_do_withholding
print('has_l10n_do_withholding (almacenado)     : %s' % flag)

btn_visible = payment.payment_type == 'outbound' and flag
print('boton "Print Certification" visible      : %s' % btn_visible)

report = env.ref('l10n_do_withholding_certification.l10n_do_withholding_cert')
html, _fmt = env['ir.actions.report']._render_qweb_html(report.report_name, payment.ids)
body = html.decode('utf-8', 'replace').split('<body', 1)[-1]
text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', body)).strip()
print('reporte: html=%d bytes | texto=%d chars' % (len(html), len(text)))

if flag and len(text) > 200:
    data = payment.get_certification_data()
    print('  bruto=%s | retenido=%s | pagado=%s' % (
        data['payments_amount'], sum(data['withholding_values'].values()), data['paid_amount']))
    print('  columnas=%s' % [a.l10n_do_tax_name for a in data['withholding_values']])
    print('  filas=%d' % len(data['invoices_data']))
    print('  base legal="%s"' % payment.get_l10n_do_legal_base_string(data['withholding_values'].items()))

line()
if btn_visible and len(text) > 200:
    print(' RESULTADO: OK — boton visible y reporte con contenido')
else:
    print(' RESULTADO: BUG REPRODUCIDO — boton oculto=%s / reporte vacio=%s' % (
        not btn_visible, len(text) <= 200))
line()
PYEOF
