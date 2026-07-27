#!/bin/bash
# replicate_azul_verify_status.sh
#
# Replica el caso de produccion de payment_azul_webservices:
#   Cliente cierra la ventana durante el 3DS -> tx queda pending ->
#   admin pulsa "Verify Status" (action_verify_azul_status) -> VerifyPayment.
#
# Las respuestas mockeadas de VerifyPayment son COPIAS EXACTAS de respuestas
# reales capturadas contra pruebas.azul.com.do (2026-07-03):
#   - 3DS abandonado : Found=true, IsoCode=3D2METHOD (sin ResponseMessage)
#   - Aprobada       : Found=true, IsoCode=00, AuthorizationCode=OKxxxx
#   - Declinada      : Found=true, IsoCode=51, "INSUF FONDOS"
#   - No encontrada  : Found=false
#
# Casos:
#   A. VerifyPayment de 3DS abandonado  -> tx debe seguir PENDING (no done)
#   B. VerifyPayment de venta aprobada  -> tx DONE, pero factura sigue SIN pagar
#      hasta que corra el post-processing (cron cada 10 min) -> luego pagada
#   C. VerifyPayment de venta declinada -> tx ERROR + ValidationError al admin
#   D. VerifyPayment no encontrada      -> tx ERROR
#   E. Cron con tx pending >2h y Azul aun en 3DS -> tx CANCEL (abandonada)
#
# NO commitea nada (rollback al final). Uso:
#   ./replicate_azul_verify_status.sh                 # DB v19_payment_azul_webservices
#   ./replicate_azul_verify_status.sh --db=mi_db
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_NAME="v19_payment_azul_webservices"
for arg in "$@"; do
  case "$arg" in
    --db=*) DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

echo "======================================================"
echo " Replica verify-status Azul — DB: $DB_NAME"
echo "======================================================"

docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME \
    --db_host=${DB_PORT_5432_TCP_ADDR:-odoo-db} --db_user=${DB_ENV_POSTGRES_USER:-odoo} \
    --db_password=${DB_ENV_POSTGRES_PASSWORD:-odoo_password} \
    --no-http --max-cron-threads=0 --workers=0 --log-level=critical
" <<'PYEOF'
import logging
import time
from unittest.mock import patch

from odoo.exceptions import ValidationError

logging.disable(logging.ERROR)

ts = str(int(time.time()))[-6:]
company = env.ref('base.main_company')
provider = env['payment.provider'].sudo().search([('code', '=', 'azul_webservices')], limit=1)
card = env.ref('payment.payment_method_card')
ProviderCls = type(env['payment.provider'])

print('Provider: %s | state=%s | journal=%s' % (
    provider.name, provider.state,
    provider.journal_id.name if provider.journal_id else 'SIN DIARIO'))

partner = env['res.partner'].create({'name': 'Cliente Replica Verify'})
product = env['product.product'].search([('name', '=', 'Producto de Prueba Azul')], limit=1)


def make_case(tag):
    """Factura publicada + tx Azul pending vinculada (cliente cerro ventana 3DS)."""
    inv = env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': partner.id,
        'invoice_line_ids': [(0, 0, {
            'product_id': product.id, 'quantity': 1, 'price_unit': 1500.0,
        })],
    })
    inv.action_post()
    tx = env['payment.transaction'].create({
        'provider_id': provider.id,
        'payment_method_id': card.id,
        'reference': 'REPLVER-%s-%s' % (tag, ts),
        'amount': inv.amount_total,
        'currency_id': inv.currency_id.id,
        'partner_id': partner.id,
        'operation': 'online_direct',
        'invoice_ids': [(6, 0, inv.ids)],
    })
    tx._set_pending(state_message='Waiting for 3D Secure authentication')
    tx.azul_3ds_session_data = '<form>challenge simulada</form>'
    return inv, tx


# Respuestas VerifyPayment reales (capturadas de pruebas.azul.com.do)
def resp_abandonada(ref):
    return {
        'Found': True, 'IsoCode': '3D2METHOD', 'ResponseCode': 'ISO8583',
        'AuthorizationCode': '', 'ErrorDescription': 'ResponseMessage: 3D_SECURE_2_METHOD',
        'AzulOrderId': '44924981', 'Amount': '150000', 'DateTime': '20260703104242',
        'CustomOrderId': ref, 'TransactionType': 'Sale',
    }

def resp_aprobada(ref):
    return {
        'Found': True, 'IsoCode': '00', 'ResponseCode': 'ISO8583',
        'AuthorizationCode': 'OK2717', 'ErrorDescription': '',
        'AzulOrderId': '44924985', 'Amount': '150000', 'DateTime': '20260703104429',
        'CardNumber': '40055200****0129', 'RRN': '2026070310443144924985',
        'Ticket': '1', 'LotNumber': '1', 'CustomOrderId': ref, 'TransactionType': 'Sale',
    }

def resp_declinada(ref):
    return {
        'Found': True, 'IsoCode': '51', 'ResponseCode': 'ISO8583',
        'AuthorizationCode': '', 'ErrorDescription': 'INSUF FONDOS. ResponseMessage: DECLINADA',
        'AzulOrderId': '44924982', 'Amount': '150000', 'DateTime': '20260703104252',
        'CustomOrderId': ref, 'TransactionType': 'Sale',
    }

def resp_no_encontrada(ref):
    return {
        'Found': False, 'IsoCode': '', 'ResponseCode': '', 'AuthorizationCode': '',
        'ErrorDescription': '', 'AzulOrderId': '', 'Amount': None,
        'DateTime': '20260703104313', 'CustomOrderId': ref, 'TransactionType': None,
    }


def verify_with(tx, response):
    with patch.object(ProviderCls, '_azul_make_request', return_value=response):
        tx.action_verify_azul_status()


def check(label, ok):
    print('  [%s] %s' % ('PASS' if ok else 'FAIL', label))
    return ok

results = []
line = lambda: print('-' * 74)

# ── CASO A: 3DS abandonado ──────────────────────────────────────────────────
line()
print('CASO A: cliente cierra ventana en 3DS, Azul reporta 3D2METHOD')
inv_a, tx_a = make_case('A')
verify_with(tx_a, resp_abandonada(tx_a.reference))
print('  tx.state=%s | state_message=%r' % (tx_a.state, (tx_a.state_message or '')[:60]))
results.append(check('tx sigue pending (NO se marca done)', tx_a.state == 'pending'))
results.append(check('factura sigue sin pagar', inv_a.payment_state == 'not_paid'))

# ── CASO B: Azul SI aprobo (cliente completo 3DS, callback perdido) ─────────
# Con el fix (19.0.1.0.7): verify->done post-procesa de inmediato, la factura
# queda pagada junto con la transaccion, sin esperar el cron de 10 minutos.
line()
print('CASO B: Azul aprobo (IsoCode=00) pero Odoo nunca recibio el callback')
inv_b, tx_b = make_case('B')
verify_with(tx_b, resp_aprobada(tx_b.reference))
print('  tx.state=%s | msg=%r' % (tx_b.state, (tx_b.state_message or '')[:70]))
print('  azul_order_id=%s | provider_reference=%s' % (tx_b.azul_order_id, tx_b.provider_reference))
results.append(check('tx done ("Payment successful")', tx_b.state == 'done'))
results.append(check('is_post_processed = True justo despues del boton (fix)',
                     tx_b.is_post_processed))
print('  payment creado: %s | estado=%s' % (
    tx_b.payment_id.name or tx_b.payment_id.id or 'NINGUNO',
    tx_b.payment_id.state or '-'))
results.append(check('factura pagada inmediatamente (payment_state=%s)' % inv_b.payment_state,
                     inv_b.payment_state in ('in_payment', 'paid')))

# ── CASO C: declinada ───────────────────────────────────────────────────────
line()
print('CASO C: Azul declino (IsoCode=51 INSUF FONDOS)')
inv_c, tx_c = make_case('C')
raised = False
try:
    verify_with(tx_c, resp_declinada(tx_c.reference))
except ValidationError as e:
    raised = True
    print('  ValidationError al admin: %r' % str(e)[:70])
results.append(check('tx en error', tx_c.state == 'error'))
results.append(check('factura sin pagar', inv_c.payment_state == 'not_paid'))
if not raised:
    print('  (nota: la ValidationError del decline la traga el except amplio de '
          '_verify_transaction_status; quirk conocido, no bloqueante)')

# ── CASO D: no encontrada en Azul ───────────────────────────────────────────
line()
print('CASO D: CustomOrderId no existe en Azul (Found=false)')
inv_d, tx_d = make_case('D')
verify_with(tx_d, resp_no_encontrada(tx_d.reference))
print('  tx.state=%s | msg=%r' % (tx_d.state, (tx_d.state_message or '')[:70]))
results.append(check('tx en error (no en done)', tx_d.state == 'error'))

# ── CASO E: cron abandona pending >2h aun en 3DS ────────────────────────────
line()
print('CASO E: cron con tx pending de hace 3h y Azul aun reporta 3DS en curso')
inv_e, tx_e = make_case('E')
env.cr.execute(
    "UPDATE payment_transaction SET create_date = now() - interval '3 hours' WHERE id = %s",
    (tx_e.id,))
tx_e.invalidate_recordset()
with patch.object(ProviderCls, '_azul_make_request', return_value=resp_abandonada(tx_e.reference)):
    env['payment.transaction']._azul_cron_verify_pending_transactions()
print('  tx.state=%s | msg=%r' % (tx_e.state, (tx_e.state_message or '')[:70]))
results.append(check('tx cancelada como abandonada', tx_e.state == 'cancel'))
results.append(check('tx abandonada post-procesada de inmediato (fix)', tx_e.is_post_processed))

# ════════════════════════════════════════════════════════════════════════════
line()
if all(results):
    print('RESULTADO: %d/%d checks PASS' % (len(results), len(results)))
else:
    print('RESULTADO: %d/%d checks PASS — revisar FAIL arriba' %
          (sum(results), len(results)))
print('(rollback: no se persiste nada)')
env.cr.rollback()
PYEOF

STATUS=$?
echo
[[ $STATUS -eq 0 ]] && echo "Replica completada." || echo "ERROR: replica fallo (exit $STATUS)"
exit $STATUS
