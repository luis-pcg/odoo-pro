#!/bin/bash
# replicate_ecf_already_reported.sh
#
# Valida la carga de facturas cuyo e-CF YA fue emitido/aceptado por DGII, sin
# reenviarlas, y comprueba que NO se rompe la emision futura ni la secuencia.
#
#   Fase 1 (--setup): sobre una DB con l10n_do_accounting + l10n_do_document_pools
#     + l10n_do_ecf_invoicing, activa el emisor e-CF, crea los tipos de documento
#     E** en el diario de venta y el pool E31. COMMITEA.
#
#   Fase 2 (siempre): corre las pruebas en una transaccion que se ROLLBACKEA, asi
#     el script es repetible. Data real bajo prueba (e-CF ya reportado a DGII):
#
#       NCF          E310000001609
#       RNC cliente  130674671
#       Fecha        08/06/2026  (dd/mm/yyyy de DGII -> 2026-06-08)
#       Facturado    9,508.18
#       ITBIS        1,711.54    (18% daria 1,711.47: se cuadra al centavo)
#       Total        11,219.72
#
#     Antes de las pruebas se siembra E310000001607 para simular la numeracion
#     que ya venia en produccion.
#       T1  factura e-CF normal -> E310000001608 (baseline)
#       T2  carga del e-CF real E310000001609 (numero siguiente)
#       T3  la siguiente factura normal sigue corrida (E310000001610)
#       T4  cobrar la factura cargada no dispara firma/envio
#       T5  NCF que adelanta la secuencia -> bloqueado
#       T6  el mismo NCF con allow_sequence_jump=True -> carga y documenta el salto
#       T7  rellenar un hueco (NCF menor al maximo) no mueve la numeracion futura
#       T8  NCF fuera del pool vigente -> bloqueado
#     Durante T2..T8 se parchean la firma XML y TODO el trafico HTTP para que
#     cualquier intento de contactar DGII haga fallar la prueba.
#
# Uso:
#   ./replicate_ecf_already_reported.sh --setup          # primera vez
#   ./replicate_ecf_already_reported.sh                  # solo pruebas
#   ./replicate_ecf_already_reported.sh --db=otra_db
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
DB_NAME="v19_ecf_load"
DO_SETUP=false

for arg in "$@"; do
  case "$arg" in
    --setup) DO_SETUP=true ;;
    --db=*)  DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS --no-http --max-cron-threads=0 --workers=0 --log-level=warn"

echo "======================================================"
echo " e-CF ya reportado en DGII — carga sin reenvio"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo "======================================================"

if $DO_SETUP; then
  echo "→ Fase 1: configurando emisor e-CF y pool E31..."
  docker exec -i "$CONTAINER" bash -lc "odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_FLAGS" <<'PYEOF'
from datetime import date

company = env.ref('base.main_company')
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
company = env['res.company'].browse(company.id)

company.l10n_do_ecf_issuer = True
company.l10n_do_ecf_service_env = 'TesteCF'
# Sin certificado a proposito: si algun camino intentara firmar, reventaria.

sale_journal = env['account.journal'].search(
    [('type', '=', 'sale'), ('company_id', '=', company.id), ('l10n_latam_use_documents', '=', True)],
    limit=1)
assert sale_journal, 'No hay diario de venta con documentos fiscales'
sale_journal._l10n_do_create_document_types()

E31 = env['l10n_latam.document.type'].search(
    [('doc_code_prefix', '=', 'E31'), ('country_id', '=', company.country_id.id)], limit=1)
assert E31, 'Tipo de documento E31 no encontrado'

pool = sale_journal.l10n_do_document_type_ids.filtered(
    lambda d: d.l10n_latam_document_type_id == E31)
assert pool, 'El diario no tiene el tipo de documento E31'
pool = pool[0]
pool.write({
    'auth_number': 'AUT-E31-0001',
    'sequence_start': 1,
    'sequence_end': 5000,
    'l10n_do_ncf_expiration_date': date(date.today().year + 2, 12, 31),
    'state': 'valid',
})
print('Emisor e-CF: %s | diario=%s | pool E31 [%s, %s] estado=%s' % (
    company.l10n_do_ecf_issuer, sale_journal.name, pool.sequence_start,
    pool.sequence_end, pool.state))
print('Tipos de documento en el diario: %s' % ', '.join(
    sale_journal.l10n_do_document_type_ids.mapped('l10n_latam_document_type_id.doc_code_prefix')))
env.cr.commit()
print('SETUP OK')
PYEOF
  [[ $? -ne 0 ]] && { echo 'ERROR en la fase de setup' >&2; exit 1; }
fi

echo "→ Fase 2: pruebas (se rollbackean al final)..."
docker exec -i "$CONTAINER" bash -lc "cat > /tmp/load_ecf_already_reported.py" < "$SCRIPT_DIR/load_ecf_already_reported.py"
docker exec -i "$CONTAINER" bash -lc "odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_FLAGS" <<'PYEOF'
import logging
import requests

from odoo.exceptions import UserError

logging.disable(logging.WARNING)

# El loader se importa como modulo: define load_ecf() y no ejecuta su bloque main.
loader_globals = {}
with open('/tmp/load_ecf_already_reported.py') as fh:
    exec(compile(fh.read(), 'load_ecf_already_reported.py', 'exec'), loader_globals)
load_ecf = loader_globals['load_ecf']

RESULTS = []


def check(label, ok, detail=''):
    RESULTS.append((label, ok, detail))
    print('%s %-58s %s' % ('PASS' if ok else 'FAIL', label, detail))


company = env.ref('base.main_company')
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
company = env['res.company'].browse(company.id)
E31 = env['l10n_latam.document.type'].search(
    [('doc_code_prefix', '=', 'E31'), ('country_id', '=', company.country_id.id)], limit=1)
sale_journal = env['account.journal'].search(
    [('type', '=', 'sale'), ('company_id', '=', company.id), ('l10n_latam_use_documents', '=', True)],
    limit=1)
itbis = env['account.tax'].search(
    [('company_id', '=', company.id), ('type_tax_use', '=', 'sale'),
     ('amount_type', '=', 'percent'), ('amount', '=', 18.0)], limit=1)
assert E31 and sale_journal and itbis, 'Falta configuracion: corre con --setup'

# ─────────────────── DATA REAL DEL e-CF YA REPORTADO A DGII ───────────────────
NCF = 'E310000001609'
RNC_CLIENTE = '130674671'
FECHA = '2026-06-08'            # 08/06/2026 12:00:00 A.M. del reporte de DGII
BASE = 9508.18                  # monto facturado
ITBIS = 1711.54                 # ITBIS exacto reportado
TOTAL = 11219.72                # BASE + ITBIS
SECURITY_CODE = '7Yx2Kp'        # codigo de seguridad del e-CF emitido
# ─────────────────────────────────────────────────────────────────────────────

partner = env['res.partner'].search([('vat', '=', RNC_CLIENTE)], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'CLIENTE RNC %s' % RNC_CLIENTE,
        'company_type': 'company',
        'vat': RNC_CLIENTE,
        'l10n_do_dgii_tax_payer_type': 'taxpayer',
        'country_id': company.country_id.id,
        'customer_rank': 1,
    })
print('Cliente: %s (RNC %s)' % (partner.display_name, partner.vat))

# Limpia cualquier e-CF E31 previo para partir de cero en cada corrida.
old = env['account.move'].search([('l10n_latam_document_type_id', '=', E31.id)])
if old:
    old.filtered(lambda m: m.state == 'posted').button_draft()
    old.write({'name': '/'})


def new_normal_invoice(price=1000.0):
    """Factura e-CF emitida por Odoo (numeracion automatica).

    Se publica con contexto l10n_do_active_test para no firmar/enviar: la logica
    de secuencia es exactamente la misma que en produccion.
    """
    move = env['account.move'].create({
        'move_type': 'out_invoice',
        'journal_id': sale_journal.id,
        'partner_id': partner.id,
        'invoice_date': FECHA,
        'date': FECHA,
        'l10n_latam_document_type_id': E31.id,
        'invoice_line_ids': [(0, 0, {
            'name': 'Producto normal', 'quantity': 1, 'price_unit': price,
            'tax_ids': [(6, 0, itbis.ids)],
        })],
    })
    move.with_context(l10n_do_active_test=True)._post(soft=False)
    return move


def payload(ncf, **extra):
    """Payload con la data real del e-CF reportado a DGII."""
    data = {
        'ncf': ncf,
        'invoice_date': FECHA,
        'company_id': company.id,
        'journal_id': sale_journal.id,
        'partner': {'vat': RNC_CLIENTE},
        'lines': [{'description': 'Servicios facturados (e-CF ya reportado a DGII)',
                   'quantity': 1, 'price_unit': BASE, 'tax_ids': itbis.ids}],
        'amount_tax': ITBIS,
        'amount_total': TOTAL,
        'ecf': {'security_code': SECURITY_CODE, 'sign_date': '%s 00:00:00' % FECHA,
                'trackid': 'TRACK-DGII-0001'},
    }
    data.update(extra)
    return data


# ── T1 baseline: sembrar la numeracion previa y emitir la anterior al NCF real ─
load_ecf(env, payload('E310000001607'), allow_sequence_jump=True)
inv1 = new_normal_invoice()
check('T1 baseline: numeracion automatica e-CF',
      inv1.name == 'E310000001608', inv1.name)

# ── Blindaje: cualquier firma o trafico HTTP hace fallar la prueba ────────────
class DgiiContacted(Exception):
    pass


def boom_sign(self, data):
    raise DgiiContacted('se intento FIRMAR un e-CF')


def boom_http(self, request, **kwargs):
    raise DgiiContacted('se intento una peticion HTTP: %s' % request.url)


type(env['l10n_do.dgii.ecf.tools']).get_signed_xml = boom_sign
requests.adapters.HTTPAdapter.send = boom_http

# ── T2 carga del e-CF ya reportado (numero siguiente) ────────────────────────
try:
    loaded = load_ecf(env, payload(NCF))
    ok = (loaded.state == 'posted' and loaded.name == NCF
          and loaded.l10n_do_ecf_send_state == 'delivered_accepted'
          and not loaded.l10n_do_ecf_edi_file)
    check('T2 carga e-CF reportado sin firmar ni enviar', ok,
          'state=%s ncf=%s ecf=%s xml=%s sello=%s' % (
              loaded.state, loaded.name, loaded.l10n_do_ecf_send_state,
              bool(loaded.l10n_do_ecf_edi_file), bool(loaded.l10n_do_electronic_stamp)))
except DgiiContacted as e:
    loaded = None
    check('T2 carga e-CF reportado sin firmar ni enviar', False, str(e))

check('T2b el sello/QR apunta al e-CF real de DGII',
      bool(loaded and NCF in (loaded.l10n_do_electronic_stamp or '')
           and SECURITY_CODE in (loaded.l10n_do_electronic_stamp or '')),
      (loaded.l10n_do_electronic_stamp or '')[:90] if loaded else '')

check('T2c la factura queda con la data exacta reportada a DGII',
      bool(loaded) and round(loaded.amount_untaxed, 2) == BASE
      and round(loaded.amount_tax, 2) == ITBIS and round(loaded.amount_total, 2) == TOTAL
      and str(loaded.invoice_date) == FECHA
      and loaded.commercial_partner_id.vat == RNC_CLIENTE
      and abs(sum(loaded.line_ids.mapped('balance'))) < 0.005,
      'base=%s itbis=%s total=%s fecha=%s rnc=%s' % (
          loaded.amount_untaxed, loaded.amount_tax, loaded.amount_total,
          loaded.invoice_date, loaded.commercial_partner_id.vat) if loaded else '')

# ── T3 la emision futura sigue corrida ───────────────────────────────────────
try:
    inv4 = new_normal_invoice()
    check('T3 la siguiente factura normal continua la secuencia',
          inv4.name == 'E310000001610', inv4.name)
except DgiiContacted as e:
    check('T3 la siguiente factura normal continua la secuencia', False, str(e))

# ── T4 cobrar la factura cargada no dispara firma/envio ──────────────────────
try:
    wizard = env['account.payment.register'].with_context(
        active_model='account.move', active_ids=loaded.ids).create({})
    wizard._create_payments()
    check('T4 cobrar la factura cargada no firma ni envia',
          loaded.payment_state in ('paid', 'in_payment')
          and loaded.l10n_do_ecf_send_state == 'delivered_accepted',
          'payment_state=%s ecf=%s' % (loaded.payment_state, loaded.l10n_do_ecf_send_state))
except DgiiContacted as e:
    check('T4 cobrar la factura cargada no firma ni envia', False, str(e))

# ── T5 NCF que adelanta la secuencia -> bloqueado ────────────────────────────
try:
    load_ecf(env, payload('E310000001650'))
    check('T5 NCF que adelanta la secuencia queda bloqueado', False, 'no lanzo UserError')
except UserError as e:
    check('T5 NCF que adelanta la secuencia queda bloqueado', True, str(e)[:80] + '...')

# ── T6 salto explicito y su efecto documentado ───────────────────────────────
jumped = load_ecf(env, payload('E310000001650'), allow_sequence_jump=True)
inv_after_jump = new_normal_invoice()
check('T6 con allow_sequence_jump el salto ocurre (y queda documentado)',
      jumped.name == 'E310000001650' and inv_after_jump.name == 'E310000001651',
      'cargado=%s siguiente=%s' % (jumped.name, inv_after_jump.name))

# ── T7 rellenar hueco no mueve la numeracion futura ──────────────────────────
gap = load_ecf(env, payload('E310000001620'))
inv_after_gap = new_normal_invoice()
check('T7 rellenar un hueco no mueve la numeracion futura',
      gap.name == 'E310000001620' and inv_after_gap.name == 'E310000001652',
      'hueco=%s siguiente=%s' % (gap.name, inv_after_gap.name))

# ── T8 NCF fuera del pool -> bloqueado ───────────────────────────────────────
try:
    load_ecf(env, payload('E310000006000'), allow_sequence_jump=True)
    check('T8 NCF fuera del pool vigente queda bloqueado', False, 'no lanzo UserError')
except UserError as e:
    check('T8 NCF fuera del pool vigente queda bloqueado', True, str(e)[:80] + '...')

# ── T9 el ITBIS del 18% se ajusta al centavo reportado por DGII ───────────────
raw_18 = round(BASE * 0.18, 2)
check('T9 ITBIS ajustado del 18% teorico al reportado a DGII',
      bool(loaded) and round(loaded.amount_tax, 2) == ITBIS and raw_18 != ITBIS,
      '18%% = %s -> DGII %s (diferencia %s)' % (raw_18, ITBIS, round(ITBIS - raw_18, 2)))

# ── T10 NCF duplicado -> bloqueado ───────────────────────────────────────────
try:
    load_ecf(env, payload(NCF))
    check('T10 NCF duplicado queda bloqueado', False, 'no lanzo UserError')
except UserError as e:
    check('T10 NCF duplicado queda bloqueado', True, str(e)[:80] + '...')

# ── T11 estado del pool tras las cargas ──────────────────────────────────────
pool = sale_journal.l10n_do_document_type_ids.filtered(
    lambda d: d.l10n_latam_document_type_id == E31)[0]
pool.invalidate_recordset()
check('T11 el pool sigue vigente y su proximo numero es coherente',
      pool.state == 'valid' and pool.l10n_do_next_sequence == 1653,
      'estado=%s proximo=%s restantes=%s' % (
          pool.state, pool.l10n_do_next_sequence, pool.l10n_do_sequence_remaining))

print('')
print('=' * 78)
failed = [r for r in RESULTS if not r[1]]
print('RESULTADO: %s/%s pruebas OK' % (len(RESULTS) - len(failed), len(RESULTS)))
for label, ok, detail in failed:
    print('  FAIL %s -> %s' % (label, detail))
print('=' * 78)

env.cr.rollback()
print('Rollback hecho: la DB queda como estaba (script repetible).')
PYEOF
echo "→ Fin."
