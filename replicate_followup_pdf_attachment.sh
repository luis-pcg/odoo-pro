#!/bin/bash
# replicate_followup_pdf_attachment.sh
#
# Reproduce el caso: "Al enviar los estados de cuenta (follow-up) a los
# clientes se adjunta automaticamente un PDF con el formato del libro mayor
# (estado de cuenta), aunque la informacion ya va en el cuerpo del correo; y al
# quitarlo manualmente se sigue mandando."  — Odoo 19, modulo account_followup
# (Enterprise) + account_followup_extra_features (custom DO).
#
# Causa investigada (codigo ESTANDAR de Odoo Enterprise, NO Odoo Pro):
#   enterprise/account_followup/models/res_partner.py
#     _get_followup_attachments() lineas 488-490:
#         options['report_attachment_id'] = self._get_followup_report(options)
#         res_attachment_ids.append(options['report_attachment_id'])
#     => El PDF del follow-up report (estado de cuenta = "libro mayor") se
#        genera y adjunta SIEMPRE. No hay flag de configuracion que lo apague
#        (join_invoices solo controla los PDF de las FACTURAS, no este reporte).
#   _execute_followup_partner() linea 546:
#         options['attachment_ids'] = self._get_followup_attachments(options)
#     => Al enviar SOBREESCRIBE attachment_ids con la lista que vuelve a incluir
#        el PDF del reporte. Por eso lo que el usuario quita en el asistente
#        (que solo contiene los PDF de facturas) no impide el envio del estado
#        de cuenta: "se sigue mandando".
#   El modulo custom account_followup_extra_features solo cambia el HTML del
#   CUERPO del correo (get_followup_report_html), nunca el PDF adjunto.
#
# Este script:
#   1. Crea una DB limpia e instala account_followup_extra_features +
#      l10n_do_document_pools (arrastra account_followup, account_reports,
#      l10n_do_accounting).
#   2. Configura compania DO + plan contable DO + pools NCF (patron tomado de
#      seed_l10n_do_invoices.py).
#   3. Crea un cliente con email y una factura VENCIDA (90 dias) y la contabiliza
#      => el cliente queda en estado "in_need_of_action" (estado de cuenta).
#   4. Reproduce el bug: simula el asistente de recordatorio manual con
#      attachment_ids=[] (usuario quito todo) y llama _get_followup_attachments;
#      comprueba que el PDF del estado de cuenta SIGUE en la lista de adjuntos.
#   5. Prueba la hipotesis del fix: parchea en runtime _get_followup_attachments
#      para quitar ese PDF en companias DO; recomprueba que ya NO se adjunta.
#   6. Commitea SOLO los datos de demo (compania/cliente/factura/followup) para
#      que se pueda reproducir tambien a mano por web; los adjuntos del probe se
#      revierten.
#
# Uso:
#   ./replicate_followup_pdf_attachment.sh                 # crea DB, instala, reproduce
#   ./replicate_followup_pdf_attachment.sh --recreate      # borra y recrea si existe
#   ./replicate_followup_pdf_attachment.sh --skip-install  # DB ya instalada, solo reproduce
#   ./replicate_followup_pdf_attachment.sh --db=mi_db      # nombre de DB personalizado
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="account_followup_extra_features,l10n_do_document_pools"

DB_NAME="test_followup_pdf_repro"
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
echo " Repro: PDF estado de cuenta adjunto en follow-up"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo " Modulos    : $MODULES"
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
      echo "ERROR: la DB $DB_NAME ya existe. Usa --recreate para reemplazarla o --skip-install para solo reproducir." >&2
      exit 1
    fi
  fi

  echo "→ Creando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME" \
    || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULES (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --stop-after-init \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los modulos' >&2; exit 1; }
fi

echo "→ Sembrando datos DO y reproduciendo el comportamiento..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 --log-level=warn
" <<'PYEOF'
from datetime import date, timedelta
import logging
logging.disable(logging.WARNING)

def line(c='-'): print(c * 70)

company = env.company
do = env.ref("base.do")

# ════════════════════════════════════════════════════════════════════════════
# 1. COMPANIA DO + PLAN CONTABLE DO + pools NCF  (patron de seed_l10n_do_invoices.py)
# ════════════════════════════════════════════════════════════════════════════
dop = env["res.currency"].with_context(active_test=False).search([("name", "=", "DOP")], limit=1)
if dop and not dop.active:
    dop.active = True
company.write({"vat": "131793898", "country_id": do.id})
if dop:
    company.currency_id = dop.id
company.partner_id.write({"country_id": do.id, "l10n_do_dgii_tax_payer_type": "taxpayer"})

if company.chart_template != "do":
    print("[install] cargando plan contable DO (era %s)..." % company.chart_template)
    env["account.chart.template"].try_loading("do", company, install_demo=False, force_create=True)
if company.account_fiscal_country_id != do:
    company.account_fiscal_country_id = do.id
company.l10n_do_sequence_manager = True
print("[ok] compania=%s pais=%s chart=%s" % (
    company.name, company.country_id.code, company.chart_template))

journal = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
if not journal:
    raise Exception("No hay diario de ventas")
if not journal.l10n_latam_use_documents:
    journal.l10n_latam_use_documents = True

# Pool NCF fiscal (B01) para poder contabilizar
doc_types = env["l10n_do.account.journal.document_type"].search([("journal_id", "=", journal.id)])
by_type = {dt.l10n_do_ncf_type: dt for dt in doc_types if dt.l10n_do_ncf_type}
fiscal_dt = by_type.get("fiscal")
if fiscal_dt:
    fiscal_dt.write({
        "auth_number": "TEST-FISCAL-001",
        "sequence_start": 1,
        "sequence_end": 100,
        "l10n_do_ncf_expiration_date": date(date.today().year + 2, 12, 31),
        "state": "valid",
    })
print("[ok] diario=%s use_documents=%s pool_fiscal=%s" % (
    journal.name, journal.l10n_latam_use_documents, bool(fiscal_dt)))

# ════════════════════════════════════════════════════════════════════════════
# 2. CLIENTE con email + FACTURA VENCIDA (90 dias) contabilizada
# ════════════════════════════════════════════════════════════════════════════
partner = env["res.partner"].search([("vat", "=", "101892256")], limit=1)
if not partner:
    partner = env["res.partner"].create({
        "name": "Cliente Estado de Cuenta SRL",
        "company_type": "company",
        "vat": "101892256",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
        "country_id": do.id,
        "customer_rank": 1,
        "email": "cliente@example-do.com",
    })

product = env["product.product"].search([("sale_ok", "=", True)], limit=1)
if not product:
    product = env["product.product"].create({"name": "Servicio", "list_price": 10000.0})

today = date.today()
existing_inv = env["account.move"].search([
    ("partner_id", "=", partner.id), ("move_type", "=", "out_invoice")], limit=1)
if existing_inv:
    inv = existing_inv
    print("[skip] factura ya existe id=%s estado=%s" % (inv.id, inv.state))
else:
    inv_vals = {
        "move_type": "out_invoice",
        "partner_id": partner.id,
        "journal_id": journal.id,
        "invoice_date": today - timedelta(days=90),
        "invoice_date_due": today - timedelta(days=60),
        "invoice_line_ids": [(0, 0, {
            "product_id": product.id, "quantity": 1.0, "price_unit": 10000.0,
            "name": "Servicio facturado",
        })],
    }
    if fiscal_dt:
        inv_vals["l10n_latam_document_type_id"] = fiscal_dt.l10n_latam_document_type_id.id
    inv = env["account.move"].create(inv_vals)
    inv.action_post()
    print("[ok] factura POSTED name=%s total=%s vence=%s" % (
        inv.name, inv.amount_total, inv.invoice_date_due))

# Recalcular estado de followup
partner.invalidate_recordset()
print("[ok] cliente=%s estado_followup=%s linea=%s" % (
    partner.name, partner.followup_status, partner.followup_line_id.name or "-"))

env.cr.commit()   # persistir datos de demo (para reproducir tambien por web)
line('#'); print(" DATOS SEMBRADOS Y COMMITEADOS"); line('#')

# ════════════════════════════════════════════════════════════════════════════
# 3. REPRO DEL BUG — simula el asistente "Recordatorio manual" / "Send & Print"
#    con attachment_ids=[] (el usuario quito TODOS los adjuntos a mano).
# ════════════════════════════════════════════════════════════════════════════
followup_line = partner.followup_line_id or partner._get_first_followup_level()

def probe(titulo):
    options = {
        "partner_id": partner.id,
        "followup_line": followup_line,
        "template_id": followup_line.mail_template_id,
        "manual_followup": True,    # viene del asistente
        "join_invoices": True,
        "attachment_ids": [],       # el usuario quito todo a mano
    }
    att_ids = partner._get_followup_attachments(options)
    atts = env["ir.attachment"].browse(att_ids)
    report_id = options.get("report_attachment_id")
    line('=')
    print(" " + titulo)
    line('=')
    print(" attachment_ids del asistente (lo que dejo el usuario): []")
    print(" Adjuntos que REALMENTE se enviarian: %d" % len(atts))
    for a in atts:
        flag = "  <== PDF ESTADO DE CUENTA (libro mayor)" if a.id == report_id else ""
        print("   - [%s] %s%s" % (a.mimetype, a.name, flag))
    report_present = report_id in att_ids
    print(" PDF del estado de cuenta adjuntado: %s" % report_present)
    return report_present

# --- Escenario ACTUAL (codigo tal cual) -------------------------------------
bug_present = probe("ESCENARIO ACTUAL (codigo tal cual)")

# --- Hipotesis de FIX: parchear _get_followup_attachments en runtime ---------
ResPartner = type(env["res.partner"])
_orig = ResPartner._get_followup_attachments
def _patched(self, options):
    res = _orig(self, options)
    rid = options.get("report_attachment_id")
    if self.env.company.country_code == "DO" and rid in res:
        res.remove(rid)
        self.env["ir.attachment"].browse(rid).unlink()
    return res
ResPartner._get_followup_attachments = _patched
try:
    fix_present = probe("HIPOTESIS DE FIX (override quita el PDF en companias DO)")
finally:
    ResPartner._get_followup_attachments = _orig   # restaurar

# ════════════════════════════════════════════════════════════════════════════
# 4. VEREDICTO
# ════════════════════════════════════════════════════════════════════════════
env.cr.rollback()   # descartar los adjuntos creados por el probe (la demo ya esta commiteada)
line('#'); print(" VEREDICTO"); line('#')
print(" Bug reproducido (PDF se adjunta pese a attachment_ids=[]) : %s" % bug_present)
print(" Fix valida (con override el PDF ya NO se adjunta)         : %s" % (not fix_present))
if bug_present and not fix_present:
    print()
    print(" >>> CONFIRMADO: el PDF del estado de cuenta lo agrega")
    print("     _get_followup_attachments() SIEMPRE, sin importar lo que el")
    print("     usuario quite en el asistente. El override propuesto lo elimina.")
elif not bug_present:
    print()
    print(" >>> NO reproducido: el PDF no aparecio. Revisar instalacion/datos.")
PYEOF

STATUS=$?
echo
if [[ $STATUS -eq 0 ]]; then
  echo "======================================================"
  echo " DB lista para inspeccion manual: $DB_NAME"
  echo " URL   : http://localhost:${ODOO_PORT:-8069}"
  echo " Login : admin / admin"
  echo " Web   : Contabilidad > Clientes > Seguimiento (Customers Statement)"
  echo "         abrir 'Cliente Estado de Cuenta SRL' > boton 'Send & Print'"
  echo "         => en el correo aparece el PDF 'Follow-up ... .pdf' adjunto."
  echo " Re-reproducir sin reinstalar: $0 --db=$DB_NAME --skip-install"
  echo "======================================================"
else
  echo "ERROR: el repro fallo (exit $STATUS). DB conservada para inspeccion: $DB_NAME"
fi
exit $STATUS
