#!/bin/bash
# replicate_ncf_credit_note_duplicate.sh
#
# Reproduce el caso reportado por ALCOVER (y visto en otros clientes):
# la nota de credito ELECTRONICA emitida sobre una factura de proveedor
# auto-numerada (E41 Compras / E47 Pago al Exterior) repite el e-NCF que ya
# llevaba una nota de credito de cliente.
#
# Escenario (identico a staging odoo-alcover-staging-37461955):
#   1. Factura de cliente E31            -> se reversa -> NC E34 (out_refund)
#   2. Factura de proveedor E47 (pago al -> se reversa -> NC E34 (in_refund)
#      exterior, numerada por NOSOTROS)
#   Las dos NC consumen la MISMA secuencia E34 de la DGII: la segunda debe
#   tomar el numero siguiente, nunca repetir el de la primera.
#
# El script NO toca git: prueba el codigo que este ahora en odoo-pro, asi que
# sirve para correrlo antes y despues del fix.
#
# Uso:
#   ./replicate_ncf_credit_note_duplicate.sh                 # DB repro_ncf_dup
#   ./replicate_ncf_credit_note_duplicate.sh --db=otra_db
#   ./replicate_ncf_credit_note_duplicate.sh --keep          # no recrea la DB
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_CONTAINER="odoo-db"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
WEB_PORT="${ODOO_PORT:-8092}"

DB="repro_ncf_dup"
KEEP=false
for arg in "$@"; do
  case "$arg" in
    --db=*) DB="${arg#--db=}" ;;
    --keep) KEEP=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

BRANCH="$(git -C "$SCRIPT_DIR/odoo-pro" rev-parse --abbrev-ref HEAD)"
COMMIT="$(git -C "$SCRIPT_DIR/odoo-pro" rev-parse --short HEAD)"
DIRTY="$(git -C "$SCRIPT_DIR/odoo-pro" status --porcelain -- l10n_do_accounting l10n_do_document_pools | wc -l | tr -d ' ')"

echo "======================================================"
echo " Repro: NC de proveedor duplica el e-NCF de la NC de cliente"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB"
echo " odoo-pro   : $BRANCH @ $COMMIT (archivos sin commitear: $DIRTY)"
echo "======================================================"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: contenedor '$CONTAINER' no esta corriendo. Corre: docker-compose up -d" >&2
  exit 1
fi

db_exists() {
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$DB'" 2>/dev/null | grep -q 1
}

if db_exists && [[ "$KEEP" == "false" ]]; then
  echo "[1/3] Borrando DB previa '$DB'..."
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB' AND pid <> pg_backend_pid()" >/dev/null 2>&1
  docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$DB" >/dev/null 2>&1
fi

if ! db_exists; then
  echo "[1/3] Instalando l10n_do_document_pools en '$DB' (sin demo)..."
  docker exec "$CONTAINER" odoo -d "$DB" $ODOO_DB_FLAGS \
    --http-port=8070 --no-http --log-level=warn --stop-after-init \
    --without-demo=all -i l10n_do_document_pools \
    > /tmp/${DB}_install.log 2>&1
  if [[ $? -ne 0 ]]; then
    echo "ERROR instalando. Ultimas lineas:" >&2; tail -20 /tmp/${DB}_install.log >&2; exit 1
  fi
else
  echo "[1/3] Reusando DB existente '$DB' (--keep)."
fi

echo "[2/3] Sembrando escenario e-CF y emitiendo los documentos..."
docker exec -i "$CONTAINER" odoo shell -d "$DB" $ODOO_DB_FLAGS \
  --http-port=8070 --no-http --log-level=warn <<'PYEOF' >/tmp/repro_ncf_shell.log 2>&1
from odoo import fields
from odoo.tests import Form

# Compania dedicada: la compania principal de la DB trae otro plan contable y
# con eso account_fiscal_country_id no es DO, asi que la logica de NCF queda
# inerte y el numero saldria con el formato LATAM generico.
company = env["res.company"].search([("name", "=", "REPRO ECF SRL")], limit=1)
if not company:
    company = env["res.company"].create({
        "name": "REPRO ECF SRL",
        "vat": "131793916",
        "street": "Calle Falsa 123",
        "country_id": env.ref("base.do").id,
    })

admin = env.ref("base.user_admin")
admin.write({"company_ids": [(4, company.id)], "company_id": company.id})
env = env(user=admin, context=dict(env.context, allowed_company_ids=[company.id]))

if not env["account.account"].search_count([("company_ids", "in", company.id)]):
    env["account.chart.template"].with_company(company).try_loading(
        "do", company=company, install_demo=False
    )
if company.account_fiscal_country_id != env.ref("base.do"):
    raise Exception("El plan de cuentas dominicano no quedo cargado en la compania")

# Emisor de e-CF: sin esto los tipos E** no aparecen como disponibles.
company.l10n_do_ecf_issuer = True

journals = env["account.journal"].search(
    [("type", "in", ("sale", "purchase")), ("company_id", "=", company.id)]
)
journals.write({"l10n_latam_use_documents": True})
sale_journal = journals.filtered(lambda j: j.type == "sale")[0]
purchase_journal = journals.filtered(lambda j: j.type == "purchase")[0]
# Los pools se crean segun los tipos permitidos: al encender el e-CF hay que
# regenerarlos para que existan los E**.
for journal in (sale_journal, purchase_journal):
    journal._l10n_do_create_document_types()
purchase_journal.l10n_do_credit_note_sequence_journal_id = sale_journal

doc_e31 = env.ref("l10n_do_accounting.ecf_fiscal_client")          # E31 Credito Fiscal
doc_e47 = env.ref("l10n_do_accounting.ecf_exterior_supplier")      # E47 Pago al Exterior
doc_e34 = env.ref("l10n_do_accounting.ecf_credit_note_client")     # E34 Nota de Credito

cliente = env["res.partner"].search([("vat", "=", "131566332")], limit=1) or env["res.partner"].create({
    "name": "CLIENTE CONTRIBUYENTE SRL",
    "vat": "131566332",
    "l10n_do_dgii_tax_payer_type": "taxpayer",
    "country_id": env.ref("base.do").id,
})
# "foreigner" es lo que habilita E47 (Pago al Exterior) del lado de compras.
proveedor = env["res.partner"].search([("name", "=", "PROVEEDOR DEL EXTERIOR")], limit=1) or env["res.partner"].create({
    "name": "PROVEEDOR DEL EXTERIOR",
    # E34 tiene is_vat_required: sin identificacion la validacion de tipo de
    # documento rechaza la nota de credito.
    "vat": "US-987654321",
    "l10n_do_dgii_tax_payer_type": "foreigner",
    "country_id": env.ref("base.us").id,
})

company.l10n_do_sequence_manager = True
expiration = fields.Date.today().replace(year=fields.Date.today().year + 1)


def confirm_pool(journal, document_type, start, end):
    pool = journal.l10n_do_document_type_ids.filtered(
        lambda d: d.l10n_latam_document_type_id == document_type
    )
    if not pool:
        raise Exception("El diario %s no tiene pool para %s" % (journal.name, document_type.name))
    pool = pool[0]
    if pool.state != "valid":
        pool.write({
            "auth_number": "AUTH-%s" % document_type.doc_code_prefix,
            "sequence_start": start,
            "sequence_end": end,
            "l10n_do_ncf_expiration_date": expiration,
        })
        pool._action_confirm()
    return pool


pool_e31 = confirm_pool(sale_journal, doc_e31, 1, 50)
pool_e47 = confirm_pool(purchase_journal, doc_e47, 1, 50)
pool_e34 = confirm_pool(sale_journal, doc_e34, 1, 50)


def make_move(move_type, journal, partner, document_type, expense_type=None):
    # Form recorre los mismos onchange que la interfaz: sin eso el tipo de
    # documento y la bandera de numero manual quedan mal calculados.
    with Form(env["account.move"].with_context(
        default_move_type=move_type, default_journal_id=journal.id
    )) as move_form:
        move_form.partner_id = partner
        move_form.invoice_date = fields.Date.today()
        move_form.l10n_latam_document_type_id = document_type
        if expense_type and not move_form._get_modifier("l10n_do_expense_type", "invisible"):
            move_form.l10n_do_expense_type = expense_type
        with move_form.invoice_line_ids.new() as line_form:
            line_form.name = "Servicio de prueba"
            line_form.quantity = 1
            line_form.price_unit = 1000.0
            line_form.tax_ids.clear()
    move = move_form.save()
    move.action_post()
    return move


def reverse(move):
    wizard = env["account.move.reversal"].with_context(
        active_ids=move.ids, active_model="account.move"
    ).create({"journal_id": move.journal_id.id})
    credit_note = env["account.move"].browse(wizard.reverse_moves()["res_id"])
    credit_note.l10n_latam_document_type_id = doc_e34
    credit_note.action_post()
    return credit_note


factura_cliente = make_move("out_invoice", sale_journal, cliente, doc_e31)
nc_cliente = reverse(factura_cliente)

factura_proveedor = make_move(
    "in_invoice", purchase_journal, proveedor, doc_e47, expense_type="02"
)
nc_proveedor = reverse(factura_proveedor)

admin.write({"login": "admin", "password": "admin"})
env.cr.commit()

print("")
print("RESULTADO=%s|%s|%s|%s|%s|%s|%s|%s|%s" % (
    factura_cliente.name,
    nc_cliente.name,
    factura_proveedor.name,
    nc_proveedor.name,
    nc_proveedor.l10n_do_journal_document_type_id == pool_e34,
    pool_e34.l10n_do_next_sequence,
    nc_cliente.name == nc_proveedor.name,
    nc_proveedor.l10n_latam_manual_document_number,
    factura_proveedor.l10n_latam_manual_document_number,
))
PYEOF

RESULT_LINE="$(grep -m1 '^RESULTADO=' /tmp/repro_ncf_shell.log 2>/dev/null)"
if [[ -z "$RESULT_LINE" ]]; then
  echo "ERROR: la siembra fallo. Ultimas lineas del log:" >&2
  tail -40 /tmp/repro_ncf_shell.log >&2
  exit 1
fi

IFS='|' read -r FACT_CLI NC_CLI FACT_PROV NC_PROV NC_USA_POOL POOL_NEXT DUPLICADO NC_MANUAL FACT_MANUAL \
  <<< "${RESULT_LINE#RESULTADO=}"

echo ""
echo "[3/3] Documentos emitidos"
echo "  Factura de cliente        (out_invoice, E31) : $FACT_CLI"
echo "  NC de cliente             (out_refund,  E34) : $NC_CLI"
echo "  Factura de proveedor      (in_invoice,  E47) : $FACT_PROV   (numero manual: $FACT_MANUAL)"
echo "  NC de proveedor           (in_refund,   E34) : $NC_PROV   (numero manual: $NC_MANUAL)"
echo ""
echo "  NC de proveedor usa el pool E34 del diario de ventas : $NC_USA_POOL"
echo "  Proximo numero que reporta el pool E34               : $POOL_NEXT"
echo ""
if [[ "$DUPLICADO" == "True" ]]; then
  echo "  >>> BUG REPRODUCIDO: las dos notas de credito llevan el mismo e-NCF ($NC_CLI)"
  STATUS=1
else
  echo "  >>> OK: cada nota de credito tomo su propio e-NCF ($NC_CLI y $NC_PROV)"
  STATUS=0
fi
echo ""
echo "  Revisalo a mano en: http://localhost:${WEB_PORT}/odoo  (DB $DB, admin / admin)"
echo "  Contabilidad > Clientes > Notas de credito  y  Contabilidad > Proveedores > Notas de credito"
echo ""
exit $STATUS
