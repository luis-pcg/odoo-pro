#!/bin/bash
# verify_ncf_sequence_multicompany.sh
#
# Valida la secuencia de NCF en las topologias que no cubre el repro simple:
#
#   A) Dos diarios de venta en la MISMA compania, cada uno con su propio pool
#      de notas de credito y rangos distintos. Cada diario debe consumir SU
#      rango; ninguno debe ver los numeros del otro.
#   B) Dos companias independientes con pools de NC de rango IDENTICO. Los
#      numeros no se deben cruzar entre companias.
#   C) Compania con SUCURSAL (res.company.parent_id). La sucursal comparte el
#      RNC de la matriz, asi que comparte talonario: no puede repetir un NCF
#      que la matriz ya emitio.
#   D) Diario de compras apuntado a cada uno de los dos diarios de venta: la
#      NC de proveedor debe seguir la escalera del diario configurado.
#
# Uso: ./verify_ncf_sequence_multicompany.sh [--db=ncf_multi] [--keep]
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
DB="ncf_multi"; KEEP=false
for arg in "$@"; do case "$arg" in --db=*) DB="${arg#--db=}";; --keep) KEEP=true;; esac; done
FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " NCF multiempresa / multidiario / sucursales"
echo " DB: $DB   odoo-pro: $(git -C "$SCRIPT_DIR/odoo-pro" rev-parse --abbrev-ref HEAD) @ $(git -C "$SCRIPT_DIR/odoo-pro" rev-parse --short HEAD)"
echo "======================================================"

exists() { docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname='$DB'" 2>/dev/null | grep -q 1; }

if exists && [[ "$KEEP" == "false" ]]; then
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB' AND pid<>pg_backend_pid()" >/dev/null 2>&1
  docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$DB" >/dev/null 2>&1
fi
if ! exists; then
  echo "[1/2] Instalando l10n_do_document_pools en '$DB'..."
  docker exec "$CONTAINER" odoo -d "$DB" $FLAGS --http-port=8070 --no-http --log-level=warn \
    --stop-after-init --without-demo=all -i l10n_do_document_pools > /tmp/${DB}_install.log 2>&1 \
    || { echo "ERROR instalando:"; tail -20 /tmp/${DB}_install.log; exit 1; }
fi

echo "[2/2] Ejecutando escenarios..."
docker exec -i "$CONTAINER" odoo shell -d "$DB" $FLAGS --http-port=8070 --no-http --log-level=warn \
  <<'PYEOF' 2>&1 | sed -n '/^=== RESULTADOS/,$p'
from odoo import fields
from odoo.tests import Form

DO = env.ref("base.do")
ecf = lambda x: env.ref("l10n_do_accounting." + x)
E31, E34, E47 = ecf("ecf_fiscal_client"), ecf("ecf_credit_note_client"), ecf("ecf_exterior_supplier")
admin = env.ref("base.user_admin")
expiry = fields.Date.today().replace(year=fields.Date.today().year + 1)
fails, notes = [], []


def make_company(name, vat, parent=None):
    vals = {"name": name, "street": "x", "country_id": DO.id}
    if vat:
        vals["vat"] = vat
    if parent:
        vals["parent_id"] = parent.id
    c = env["res.company"].search([("name", "=", name)], limit=1) or env["res.company"].create(vals)
    admin.write({"company_ids": [(4, c.id)]})
    return c


def load_chart(c):
    if not env["account.account"].search_count([("company_ids", "in", c.id)]):
        env["account.chart.template"].with_company(c).try_loading("do", company=c, install_demo=False)
    c.l10n_do_ecf_issuer = True
    c.l10n_do_sequence_manager = True


def pool_of(journal, doc):
    return journal.l10n_do_document_type_ids.filtered(lambda p: p.l10n_latam_document_type_id == doc)[:1]


def confirm(journal, doc, start, end):
    p = pool_of(journal, doc)
    if not p:
        raise Exception("sin pool %s en %s" % (doc.doc_code_prefix, journal.name))
    if p.state != "valid":
        p.write({"auth_number": "A", "sequence_start": start, "sequence_end": end,
                 "l10n_do_ncf_expiration_date": expiry})
        p._action_confirm()
    return p


def partner(name, vat, ptype, country=None):
    p = env["res.partner"].search([("name", "=", name)], limit=1)
    return p or env["res.partner"].create({
        "name": name, "vat": vat, "l10n_do_dgii_tax_payer_type": ptype,
        "country_id": (country or DO).id})


def mk(e, mt, journal, prt, doc, expense=None):
    with Form(e["account.move"].with_context(default_move_type=mt, default_journal_id=journal.id)) as f:
        f.partner_id = prt
        f.invoice_date = fields.Date.today()
        f.l10n_latam_document_type_id = doc
        if expense and not f._get_modifier("l10n_do_expense_type", "invisible"):
            f.l10n_do_expense_type = expense
        with f.invoice_line_ids.new() as l:
            l.name = "x"; l.quantity = 1; l.price_unit = 1000.0; l.tax_ids.clear()
    m = f.save(); m.action_post(); return m


def mk_orm(e, journal, prt, doc, model_move):
    """Factura de sucursal: una sucursal no carga plan propio, asi que las
    propiedades por compania salen vacias y el Form no puede resolver las
    cuentas. Se copian de un asiento equivalente de la matriz."""
    recv = model_move.line_ids.filtered(lambda l: l.display_type == "payment_term")[:1].account_id
    inc = model_move.line_ids.filtered(lambda l: l.display_type == "product")[:1].account_id
    m = e["account.move"].create({
        "move_type": "out_invoice", "journal_id": journal.id, "partner_id": prt.id,
        "invoice_date": fields.Date.today(), "date": fields.Date.today(),
        "l10n_latam_document_type_id": doc.id,
        "invoice_line_ids": [(0, 0, {
            "name": "x", "quantity": 1, "price_unit": 1000.0,
            "account_id": inc.id, "tax_ids": [(5, 0, 0)]})],
    })
    m.line_ids.filtered(lambda l: l.display_type == "payment_term").account_id = recv
    m.action_post()
    return m


def rev(e, move):
    w = e["account.move.reversal"].with_context(
        active_ids=move.ids, active_model="account.move").create({"journal_id": move.journal_id.id})
    cn = e["account.move"].browse(w.reverse_moves()["res_id"])
    cn.l10n_latam_document_type_id = E34
    cn.action_post(); return cn


def envof(c):
    # Al activar una sucursal Odoo habilita tambien su matriz: sin la matriz no
    # se ve el plan contable, que es de ella.
    ids = [c.id] + ([c.parent_id.id] if c.parent_id else [])
    return env(user=admin, context=dict(env.context, allowed_company_ids=ids))


def check(label, got, want):
    ok = got == want
    if not ok:
        fails.append("%s: obtuvo %s, esperaba %s" % (label, got, want))
    print("  %-58s %-14s %s" % (label, got, "OK" if ok else "<-- FALLO, esperaba %s" % (want,)))


# ---------------------------------------------------------------- topologia
matriz = make_company("MATRIZ SRL", "131793916")
otra = make_company("OTRA EMPRESA SRL", "130862346")
load_chart(matriz); load_chart(otra)
# Una sucursal en Odoo 19 no tiene plan ni diarios propios: factura con los de
# la matriz y el asiento queda con company_id = sucursal.
sucursal = make_company("SUCURSAL NORTE", False, parent=matriz)

cliente = partner("CLIENTE SRL", "131566332", "taxpayer")
exterior = partner("PROVEEDOR EXTERIOR", "US-987654321", "foreigner", env.ref("base.us"))


def journals_of(c):
    js = env["account.journal"].search([("type", "in", ("sale", "purchase")), ("company_id", "=", c.id)])
    js.write({"l10n_latam_use_documents": True})
    for j in js:
        j._l10n_do_create_document_types()
    return js.filtered(lambda j: j.type == "sale"), js.filtered(lambda j: j.type == "purchase")

m_sales, m_purch = journals_of(matriz)
o_sales, o_purch = journals_of(otra)

# Segundo diario de venta en la matriz, con su propio pool de NC
ventas_b = env["account.journal"].search([("code", "=", "VTB"), ("company_id", "=", matriz.id)], limit=1)
if not ventas_b:
    ventas_b = env["account.journal"].create({
        "name": "Ventas B", "type": "sale", "code": "VTB",
        "company_id": matriz.id, "l10n_latam_use_documents": True})
    ventas_b._l10n_do_create_document_types()
ventas_a = m_sales[0]
purch_m = m_purch[0]

print("")
print("=== RESULTADOS =======================================================")
print("")
print("Topologia:")
print("  MATRIZ SRL (RNC 131793916)")
print("     - %s  pool E34 [1-20]" % ventas_a.name)
print("     - %s  pool E34 [21-40]" % ventas_b.name)
print("     - %s (compras, sin pool E34 propio)" % purch_m.name)
print("  SUCURSAL NORTE (parent_id = MATRIZ, comparte RNC)")
print("     - Ventas Sucursal, diario propio, pool E34 [1-20] = MISMO talonario")
print("  OTRA EMPRESA SRL (RNC 130862346, independiente)")
print("     - %s  pool E34 [1-20]  <- MISMO rango que la matriz" % o_sales[0].name)
print("")

pool_a = confirm(ventas_a, E34, 1, 20)
pool_b = confirm(ventas_b, E34, 21, 40)
sin_diarios = not env["account.journal"].search_count([("company_id", "=", sucursal.id)])
ventas_suc = env["account.journal"].create({
    "name": "Ventas Sucursal", "type": "sale", "code": "VTS",
    "company_id": sucursal.id, "l10n_latam_use_documents": True})
ventas_suc._l10n_do_create_document_types()
# Una sucursal no carga plan propio: hereda las cuentas de la matriz pero las
# propiedades por compania (cuenta a cobrar/pagar del contacto) salen vacias.
for prt in (cliente, exterior):
    p_m = prt.with_company(matriz)
    prt.with_company(sucursal).write({
        "property_account_receivable_id": p_m.property_account_receivable_id.id,
        "property_account_payable_id": p_m.property_account_payable_id.id,
    })
pool_c = confirm(ventas_suc, E34, 1, 20)
confirm(ventas_suc, E31, 100, 150)
pool_o = confirm(o_sales[0], E34, 1, 20)
confirm(ventas_a, E31, 1, 50); confirm(ventas_b, E31, 51, 99)
confirm(o_sales[0], E31, 1, 50)
confirm(purch_m, E47, 1, 50); confirm(o_purch[0], E47, 1, 50)

em, eo, es = envof(matriz), envof(otra), envof(sucursal)

# ---- A) dos diarios de venta en la misma compania ------------------------
print("A) Dos diarios de venta en MATRIZ, pools de NC con rangos distintos")
a1 = rev(em, mk(em, "out_invoice", ventas_a, cliente, E31))
check("NC #1 por Ventas A (rango [1-20])", a1.name, "E340000000001")
b1 = rev(em, mk(em, "out_invoice", ventas_b, cliente, E31))
check("NC #1 por Ventas B (rango [21-40])", b1.name, "E340000000021")
a2 = rev(em, mk(em, "out_invoice", ventas_a, cliente, E31))
check("NC #2 por Ventas A (no salta al rango de B)", a2.name, "E340000000002")
b2 = rev(em, mk(em, "out_invoice", ventas_b, cliente, E31))
check("NC #2 por Ventas B", b2.name, "E340000000022")
for p, want in ((pool_a, 3), (pool_b, 23)):
    p.invalidate_recordset()
check("Pool E34 de Ventas A: proximo", pool_a.l10n_do_next_sequence, 3)
check("Pool E34 de Ventas B: proximo", pool_b.l10n_do_next_sequence, 23)

# ---- D) diario de compras apuntado a cada diario de venta ----------------
print("")
print("D) Diario de compras de MATRIZ segun el 'Diario para NC' configurado")
purch_m.l10n_do_credit_note_sequence_journal_id = ventas_a
env["account.move"].invalidate_model(["l10n_do_journal_document_type_id"])
d1 = rev(em, mk(em, "in_invoice", purch_m, exterior, E47, "02"))
check("NC de proveedor con Compras -> Ventas A", d1.name, "E340000000003")
purch_m.l10n_do_credit_note_sequence_journal_id = ventas_b
env["account.move"].invalidate_model(["l10n_do_journal_document_type_id"])
d2 = rev(em, mk(em, "in_invoice", purch_m, exterior, E47, "02"))
check("NC de proveedor con Compras -> Ventas B", d2.name, "E340000000023")

# ---- B) companias independientes con el MISMO rango ----------------------
print("")
print("B) OTRA EMPRESA SRL, pool de NC con el mismo rango [1-20] que la matriz")
o1 = rev(eo, mk(eo, "out_invoice", o_sales[0], cliente, E31))
check("NC #1 de OTRA (no ve las 4 de la matriz)", o1.name, "E340000000001")
o2 = rev(eo, mk(eo, "out_invoice", o_sales[0], cliente, E31))
check("NC #2 de OTRA", o2.name, "E340000000002")
pool_o.invalidate_recordset(); pool_a.invalidate_recordset()
check("Pool de OTRA: proximo", pool_o.l10n_do_next_sequence, 3)
check("Pool de MATRIZ/Ventas A: proximo (intacto)", pool_a.l10n_do_next_sequence, 4)

# ---- C) sucursal ---------------------------------------------------------
print("")
print("C) SUCURSAL NORTE: diario propio, MISMO rango que la matriz (un solo RNC)")
check("La sucursal no hereda plan ni diarios propios de Odoo", sin_diarios, True)
check("Pool E34 de la sucursal y el de la matriz: mismo rango", (pool_c.sequence_start, pool_c.sequence_end), (1, 20))
c1 = rev(es, mk_orm(es, ventas_suc, cliente, E31, a1.reversed_entry_id))
check("company_id del asiento", c1.company_id.name, "SUCURSAL NORTE")
check("NC de la sucursal CONTINUA el talonario de la matriz", c1.name, "E340000000004")
c2 = rev(es, mk_orm(es, ventas_suc, cliente, E31, a1.reversed_entry_id))
check("NC #2 de la sucursal", c2.name, "E340000000005")
c3 = rev(em, mk(em, "out_invoice", ventas_a, cliente, E31))
check("La matriz sigue despues de la sucursal (no repite)", c3.name, "E340000000006")
pool_a.invalidate_recordset(); pool_c.invalidate_recordset()
check("Pool de la matriz cuenta lo emitido por la sucursal", pool_a.l10n_do_next_sequence, 7)
check("Pool de la sucursal cuenta lo emitido por la matriz", pool_c.l10n_do_next_sequence, 7)
check("Pool de OTRA sigue sin contaminarse", pool_o.l10n_do_next_sequence, 3)

todos = [a1, a2, b1, b2, d1, d2, o1, o2, c1, c2, c3]
grupo_matriz = [m for m in (a1, a2, b1, b2, d1, d2, c1, c2, c3)]
nombres = [m.name for m in grupo_matriz]
dups = sorted({n for n in nombres if nombres.count(n) > 1})
print("")
check("NCF repetidos dentro del grupo MATRIZ+SUCURSAL", dups or "ninguno", "ninguno")

print("")
print("======================================================================")
if fails:
    for f_ in fails:
        print("FALLO: %s" % f_)
else:
    print("TODO OK: %s documentos, sin colisiones" % len(todos))
env.cr.rollback()
PYEOF
