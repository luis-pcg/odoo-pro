# Seed script for odoo shell — l10n_do_accounting + l10n_do_document_pools
# Mirrors dev_env_odoo_pro-17/setup_test_l10n_do_invoices.py, adapted to v19 pools.
# Run: docker exec -i lfernandez_v19 odoo shell ... -d test_l10n_do_invoices < seed_l10n_do_invoices.py
from datetime import date

POOLS = [
    ("fiscal", "TEST-FISCAL-001"),
    ("consumer", "TEST-CONSUMER-001"),
    ("credit_note", "TEST-CREDIT-001"),
    ("debit_note", "TEST-DEBIT-001"),
]
SEQ_START, SEQ_END = 1, 50

env = env  # noqa  (provided by odoo shell)
company = env.company
do_country = env.ref("base.do")

# ── 1. Company → DO ───────────────────────────────────────────────
dop = env["res.currency"].with_context(active_test=False).search([("name", "=", "DOP")], limit=1)
if dop and not dop.active:
    dop.active = True
company.write({"vat": "131793898", "country_id": do_country.id})
if dop:
    company.currency_id = dop.id
company.partner_id.write({"country_id": do_country.id, "l10n_do_dgii_tax_payer_type": "taxpayer"})
print("[ok] company:", company.name, "vat=131793898 country=DO")

# ── 2. Chart of accounts (DO) ─────────────────────────────────────
# Fresh DB auto-loads generic_coa; force the DO chart so fiscal country = DO
# and ITBIS taxes exist. Must run before any posted move.
if company.chart_template != "do":
    print("[install] loading DO chart of accounts (was %s)..." % company.chart_template)
    env["account.chart.template"].try_loading("do", company, install_demo=False, force_create=True)
    print("[ok] CoA loaded, chart_template=", company.chart_template)
else:
    print("[skip] DO CoA already present")
# ensure fiscal country = DO (drives account.move.country_code)
if company.account_fiscal_country_id != do_country:
    company.account_fiscal_country_id = do_country.id
print("[ok] fiscal_country=", company.account_fiscal_country_id.code)

# ── 3. Sequence manager ON ────────────────────────────────────────
company.l10n_do_sequence_manager = True

# ── 4. Sale journal w/ documents ──────────────────────────────────
journal = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
)
if not journal:
    raise Exception("No sale journal found")
if not journal.l10n_latam_use_documents:
    journal.l10n_latam_use_documents = True
print("[ok] journal:", journal.name, "use_documents=", journal.l10n_latam_use_documents)

# ── 5. Configure NCF pools (sequences) ────────────────────────────
doc_types = env["l10n_do.account.journal.document_type"].search([("journal_id", "=", journal.id)])
print("[info]", len(doc_types), "journal document types")
exp = date(date.today().year + 2, 12, 31)
by_type = {dt.l10n_do_ncf_type: dt for dt in doc_types if dt.l10n_do_ncf_type}
for ncf_type, auth in POOLS:
    dt = by_type.get(ncf_type)
    if not dt:
        print("  [skip] ncf_type not available:", ncf_type)
        continue
    dt.write({
        "auth_number": auth,
        "sequence_start": SEQ_START,
        "sequence_end": SEQ_END,
        "l10n_do_ncf_expiration_date": exp,
        "state": "valid",
    })
    print("  [ok] pool", ncf_type, "->valid", SEQ_START, "-", SEQ_END, "auth", auth)

# ── 6. Test customer (taxpayer) ───────────────────────────────────
partner = env["res.partner"].search([("vat", "=", "101892256")], limit=1)
if not partner:
    partner = env["res.partner"].create({
        "name": "Empresa Test DO S.R.L.",
        "company_type": "company",
        "vat": "101892256",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
        "country_id": do_country.id,
        "customer_rank": 1,
        "email": "test@empresa-do.com",
    })
print("[ok] partner:", partner.name, partner.vat)

# ── 7. Test invoice (fiscal B01) + post ───────────────────────────
product = env["product.product"].search([("sale_ok", "=", True)], limit=1)
if not product:
    product = env["product.product"].create({"name": "Producto de Prueba", "list_price": 5000.0})
fiscal_dt = by_type.get("fiscal")
inv_vals = {
    "move_type": "out_invoice",
    "partner_id": partner.id,
    "journal_id": journal.id,
    "invoice_line_ids": [(0, 0, {
        "product_id": product.id, "quantity": 2.0, "price_unit": 5000.0,
        "name": "Producto de Prueba", "discount": 10.0,
    })],
}
if fiscal_dt:
    inv_vals["l10n_latam_document_type_id"] = fiscal_dt.l10n_latam_document_type_id.id
inv = env["account.move"].create(inv_vals)
print("[ok] invoice created id=%s (draft)" % inv.id)
try:
    inv.action_post()
    print("[ok] invoice POSTED: name=%s state=%s country_code=%s" % (
        inv.name, inv.state, inv.country_code))
except Exception as e:
    print("[warn] post failed:", e)

# ── 8. admin password + commit ────────────────────────────────────
env.ref("base.user_admin").password = "admin"
env.cr.commit()
print("=== SEED DONE ===")
print("invoice_id=%s journal_id=%s partner_id=%s" % (inv.id, journal.id, partner.id))
