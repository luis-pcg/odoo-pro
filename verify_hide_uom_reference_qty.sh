#!/bin/bash
# verify_hide_uom_reference_qty.sh
#
# Verifica la feature de la rama 19.0-feat-l10n_do_accounting-hide-uom-ref-lf
# (l10n_do_accounting 19.0.1.9.0): setting por compañía
# res.company.l10n_do_hide_uom_reference_qty que oculta en los reportes de
# factura la cantidad convertida a la unidad de referencia del producto
# ("720.00 Horas" debajo de "1.00 Mes(es)").
#
# Qué comprueba, sobre datos sembrados en una transacción con rollback:
#   1. El campo existe en res.company y en res.config.settings (related).
#   2. Setting OFF (default) -> el HTML del reporte SI trae 720.00 + Hours.
#   3. Setting ON            -> el HTML NO trae ni 720.00 ni Hours (la UdM
#                               facturada "Months" sigue saliendo).
#   4. Lo anterior en las DOS plantillas:
#        - l10n_do_accounting.report_invoice_document_inherited (diario con
#          l10n_latam_use_documents + país DO)
#        - account.report_invoice_document (diario sin documentos)
#      y en los dos report_type (pdf y html/portal).
#
# Gotchas cubiertos:
#   - uom.group_uom: sin ese grupo los <span> de UdM no se renderizan y todo
#     parece pasar aunque el xpath no haga nada.
#   - docker exec odoo necesita --db_host/--db_user/--db_password a mano.
#   - tras el -u hay que reiniciar el contenedor para que el worker HTTP
#     recargue el registry (si no, el navegador da 500 con el campo nuevo).
#
# Uso:
#   ./verify_hide_uom_reference_qty.sh                 # DB por defecto
#   ./verify_hide_uom_reference_qty.sh --db=OTRA_DB
#   ./verify_hide_uom_reference_qty.sh --skip-update   # no corre -u
#   ./verify_hide_uom_reference_qty.sh --no-restart    # no reinicia contenedor
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
MODULE="l10n_do_accounting"

DB="v19_do_report_test"
DO_UPDATE=true
DO_RESTART=true
for arg in "$@"; do
  case "$arg" in
    --db=*)        DB="${arg#--db=}" ;;
    --skip-update) DO_UPDATE=false ;;
    --no-restart)  DO_RESTART=false ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_FLAGS="-c /etc/odoo/odoo.conf --db_host=$DB_HOST --db_port=$DB_PORT \
--db_user=$DB_USER --db_password=$DB_PASS --no-http --max-cron-threads=0 \
--workers=0 --log-level=warn"

echo "======================================================"
echo " Verify: ocultar cantidad en unidad de referencia"
echo " Modulo : $MODULE"
echo " DB     : $DB"
echo " Cont.  : $CONTAINER"
echo "======================================================"

if ! docker info >/dev/null 2>&1; then
  echo "ERROR: el daemon de Docker no responde. Abre Docker Desktop y reintenta." >&2
  exit 1
fi

if ! docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
     "SELECT 1 FROM pg_database WHERE datname='$DB'" | grep -q 1; then
  echo "ERROR: la DB '$DB' no existe en $DB_CONTAINER." >&2
  echo "       Usa --db= con una DB que tenga $MODULE instalado, o crea una." >&2
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY 1" | sed 's/^/       - /' >&2
  exit 1
fi

if $DO_UPDATE; then
  echo "--- odoo -u $MODULE -----------------------------------"
  docker exec -i "$CONTAINER" bash -lc "odoo $ODOO_FLAGS -d $DB -u $MODULE --stop-after-init" \
    || { echo "ERROR: el update fallo (xpath/vista rota?)." >&2; exit 1; }
fi

echo "--- render + asserts ----------------------------------"
docker exec -i "$CONTAINER" bash -lc "odoo shell $ODOO_FLAGS -d $DB" <<'PYEOF'
import re

failures = []
def check(label, cond):
    print(("  [ok]   " if cond else "  [FAIL] ") + label)
    if not cond:
        failures.append(label)

company = env.company
Report = env["ir.actions.report"]

# 0. campos existen
check("res.company.l10n_do_hide_uom_reference_qty existe",
      bool(env["res.company"].fields_get(["l10n_do_hide_uom_reference_qty"])))
check("res.config.settings.l10n_do_hide_uom_reference_qty existe",
      bool(env["res.config.settings"].fields_get(["l10n_do_hide_uom_reference_qty"])))

# 1. el usuario debe estar en uom.group_uom o los <span> de UdM no salen
env.ref("uom.group_uom").sudo().write({"user_ids": [(4, env.uid)]})
env.user.invalidate_recordset()

# 2. UdM Mes(es) = 720 Horas
hour = env.ref("uom.product_uom_hour")
month = env["uom.uom"].with_context(active_test=False).search([("name", "=", "Months")], limit=1)
if not month:
    month = env["uom.uom"].create({
        "name": "Months", "relative_factor": 720.0, "relative_uom_id": hour.id,
    })
month.active = True

# 3. producto cuya UdM de referencia es Horas, facturable en Mes(es)
product = env["product.product"].create({
    "name": "ZZ Servicio mensual (test hide uom)",
    "type": "service",
    "uom_id": hour.id,
    "uom_ids": [(6, 0, [month.id])],   # para poder elegir Mes(es) en la UI
    "list_price": 1500.0,
})

partner = env["res.partner"].search([("l10n_do_dgii_tax_payer_type", "!=", False)], limit=1) \
    or env["res.partner"].create({"name": "ZZ Cliente test hide uom"})

def make_invoice(journal):
    return env["account.move"].create({
        "move_type": "out_invoice",
        "partner_id": partner.id,
        "journal_id": journal.id,
        "invoice_line_ids": [(0, 0, {
            "product_id": product.id,
            "quantity": 1.0,
            "product_uom_id": month.id,
            "price_unit": 1500.0,
        })],
    })

sale_journals = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id)])
j_do = sale_journals.filtered("l10n_latam_use_documents")[:1]
j_std = sale_journals.filtered(lambda j: not j.l10n_latam_use_documents)[:1]
if not j_std:
    j_std = env["account.journal"].create({
        "name": "ZZ Venta sin documentos", "code": "ZZSTD", "type": "sale",
        "company_id": company.id,
    })

cases = []
if j_do:
    cases.append(("plantilla DO", make_invoice(j_do)))
else:
    print("  [warn] no hay diario de venta con l10n_latam_use_documents; salto plantilla DO")
cases.append(("plantilla estandar", make_invoice(j_std)))

def render(move, report_type):
    html = Report.with_context(report_type=report_type)._render_qweb_html(
        "account.account_invoices", move.ids)[0]
    return html.decode() if isinstance(html, bytes) else html

for label, move in cases:
    tmpl = move._get_name_invoice_report()
    print("\n%s -> %s (%s)" % (label, tmpl, move.journal_id.name))
    for report_type in ("pdf", "html"):
        for hide in (False, True):
            company.sudo().l10n_do_hide_uom_reference_qty = hide
            env.flush_all()
            html = render(move, report_type)
            has_ref = bool(re.search(r"720\.00", html)) and "Hours" in html
            has_line_uom = "Months" in html
            tag = "%s/%s hide=%s" % (label, report_type, hide)
            check("%s: UdM facturada 'Months' presente" % tag, has_line_uom)
            if hide:
                check("%s: '720.00 Hours' OCULTO" % tag, not has_ref)
            else:
                check("%s: '720.00 Hours' visible" % tag, has_ref)

print("\n======================================================")
if failures:
    print("RESULTADO: %d assert(s) fallaron" % len(failures))
    for f in failures:
        print("  - " + f)
else:
    print("RESULTADO: todo OK")
print("======================================================")

env.cr.rollback()   # nada de esto se persiste
PYEOF

if $DO_RESTART; then
  echo "--- docker restart $CONTAINER (registry del worker HTTP) ---"
  docker restart "$CONTAINER" >/dev/null && echo "  contenedor reiniciado"
fi

echo
echo "Prueba manual en navegador (http://localhost:${ODOO_PORT:-8092}, admin/admin, DB $DB):"
echo "  1. Ajustes > Tecnico > activar 'Unidades de medida' (grupo uom.group_uom)."
echo "  2. Producto de servicio: UdM = Horas, agregar 'Mes(es)' en Empaques/uom_ids."
echo "  3. Factura de cliente con ese producto, cantidad 1, unidad Mes(es)."
echo "  4. Vista previa/Imprimir: debe salir '1.00 Mes(es)' y debajo '720.00 Horas'."
echo "  5. Ajustes > Contabilidad > Dominican Localization > marcar"
echo "     'Ocultar la cantidad en unidad de referencia en las facturas'."
echo "  6. Reimprimir: solo '1.00 Mes(es)'. Verificar tambien el portal del cliente."
