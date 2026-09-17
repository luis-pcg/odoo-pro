#!/bin/bash
# verify_ncf_sequence_isolation.sh
#
# Regresion del fix de la secuencia de notas de credito. Comprueba las dos
# caras del mismo discriminante (numero propio vs numero del contraparte):
#
#   A) El NCF de un suplidor (numero AJENO, tecleado a mano) que cae dentro
#      del rango del pool de ventas NO debe envenenar la secuencia propia.
#      Es el caso que arreglaba el commit 87bd0da2 y no se puede perder.
#   B) Ese mismo NCF ajeno tampoco debe contar contra el pool (ni mover el
#      "proximo numero" ni agotarlo antes de tiempo).
#
# Usa la DB que deja replicate_ncf_credit_note_duplicate.sh.
#
#   ./verify_ncf_sequence_isolation.sh [--db=repro_ncf_dup]
#
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
DB="repro_ncf_dup"
for arg in "$@"; do case "$arg" in --db=*) DB="${arg#--db=}" ;; esac; done

docker exec -i "$CONTAINER" odoo shell -d "$DB" \
  --db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS \
  --http-port=8070 --no-http --log-level=warn <<'PYEOF' 2>&1 | grep -E "^(OK|FALLO|  )" 
from odoo import fields
from odoo.tests import Form

company = env["res.company"].search([("name", "=", "REPRO ECF SRL")], limit=1)
admin = env.ref("base.user_admin")
env = env(user=admin, context=dict(env.context, allowed_company_ids=[company.id]))
sale_journal = env["account.journal"].search([("type","=","sale"),("company_id","=",company.id)])[0]
purchase_journal = env["account.journal"].search([("type","=","purchase"),("company_id","=",company.id)])[0]
doc_e31 = env.ref("l10n_do_accounting.ecf_fiscal_client")
cliente = env["res.partner"].search([("vat","=","131566332")],limit=1)

pool_e31 = sale_journal.l10n_do_document_type_ids.filtered(lambda d: d.l10n_latam_document_type_id == doc_e31)[0]
print("  Pool E31 de ventas: rango [%s,%s], proximo=%s" % (
    pool_e31.sequence_start, pool_e31.sequence_end, pool_e31.l10n_do_next_sequence))

# El proveedor tiene que ser contribuyente para que le apliquen los E31 y el
# numero lo ponga el suplidor (manual), no nosotros.
proveedor = env["res.partner"].search([("vat","=","130862346")],limit=1) or env["res.partner"].create({
    "name": "PROVEEDOR CONTRIBUYENTE SRL",
    "vat": "130862346",
    "l10n_do_dgii_tax_payer_type": "taxpayer",
    "country_id": env.ref("base.do").id,
})

# Factura de proveedor con el E31 DEL SUPLIDOR, numero 40: dentro del rango
# del pool de ventas y muy por encima de lo que llevamos emitido.
with Form(env["account.move"].with_context(
    default_move_type="in_invoice", default_journal_id=purchase_journal.id)) as f:
    f.partner_id = proveedor
    f.invoice_date = fields.Date.today()
    f.l10n_latam_document_type_id = doc_e31
    f.l10n_latam_document_number = "E310000000040"
    if not f._get_modifier("l10n_do_expense_type", "invisible"):
        f.l10n_do_expense_type = "01"
    with f.invoice_line_ids.new() as l:
        l.name = "x"; l.quantity = 1; l.price_unit = 1000.0; l.tax_ids.clear()
bill = f.save()
bill.action_post()
print("  Factura de proveedor E31 (numero del suplidor): %s  manual=%s" % (
    bill.name, bill.l10n_latam_manual_document_number))

fails = []
if not bill.l10n_latam_manual_document_number:
    fails.append("la factura del suplidor deberia quedar marcada como numero manual")

esperado = pool_e31.l10n_do_next_sequence

# Factura de cliente E31: debe seguir NUESTRA secuencia, no el 41.
with Form(env["account.move"].with_context(
    default_move_type="out_invoice", default_journal_id=sale_journal.id)) as f:
    f.partner_id = cliente
    f.invoice_date = fields.Date.today()
    f.l10n_latam_document_type_id = doc_e31
    with f.invoice_line_ids.new() as l:
        l.name = "x"; l.quantity = 1; l.price_unit = 1000.0; l.tax_ids.clear()
sale = f.save()
sale.action_post()
print("  Factura de cliente E31 emitida despues        : %s (esperado %s)" % (sale.name, esperado))
if sale.sequence_number != esperado:
    fails.append("la venta tomo %s en vez de %s: el NCF del suplidor envenena la secuencia propia"
                 % (sale.sequence_number, esperado))

pool_e31.invalidate_recordset()
print("  Pool E31 tras la venta: proximo=%s (esperado %s)" % (
    pool_e31.l10n_do_next_sequence, esperado + 1))
if pool_e31.l10n_do_next_sequence != esperado + 1:
    fails.append("el pool cuenta el NCF del suplidor: proximo=%s en vez de %s"
                 % (pool_e31.l10n_do_next_sequence, esperado + 1))

env.cr.rollback()
if fails:
    for f_ in fails:
        print("FALLO: %s" % f_)
else:
    print("OK: el NCF del suplidor no toca ni la secuencia propia ni el pool")
PYEOF
