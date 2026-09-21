# Seed for the manual of account_bank_statement_import_csv_patch.
#
# Builds, from a CLEAN DB:
#   * Spanish UI, a chart of accounts and the accounting groups for admin
#   * a bank journal with an August statement already imported through the
#     real CSV import wizard, so the September file the manual uploads chains
#     onto a previous closing balance
#   * the company switch of this module turned on
#   * two demo actions (journal entries and statements of the journal) that
#     the manual points at to show the result
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

import odoo

env = odoo.api.Environment(env.cr, odoo.SUPERUSER_ID, {})

company = env.ref("base.main_company")
company.write({"name": "INDEXA SRL"})

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)

admin = env.ref("base.user_admin")
admin.group_ids = [
    (4, env.ref("account.group_account_basic").id),
    (4, env.ref("account.group_account_user").id),
    (4, env.ref("account.group_account_manager").id),
]

company.create_statement_draft = True

journal = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
if not journal:
    journal = env["account.journal"].create({"name": "Banco", "code": "BNK1", "type": "bank"})
journal.name = "Banco Popular - Cuenta Corriente"

AUGUST = (
    b"date,payment_ref,amount,balance\n"
    b"2026-08-05,Deposito inicial,100000.00,100000.00\n"
    b"2026-08-12,Cobro factura Supermercado Bravo,25000.00,125000.00\n"
    b"2026-08-20,Pago nomina quincena,-5000.00,120000.00\n"
)
if not env["account.bank.statement"].search_count([("journal_id", "=", journal.id)]):
    attachment = env["ir.attachment"].create({"mimetype": "text/csv", "name": "estado_agosto.csv", "raw": AUGUST})
    action = journal.create_document_from_attachment(attachment.ids)
    wizard = env["base_import.import"].browse(action["params"]["context"]["wizard_id"]).with_context(
        action["params"]["context"]
    )
    options = {
        "date_format": "%Y-%m-%d", "keep_matches": False, "encoding": "utf-8", "fields": [], "quoting": '"',
        "bank_stmt_import": True, "has_headers": True, "limit": 100, "skip": 0, "separator": ",",
        "float_thousand_separator": ",", "float_decimal_separator": ".", "advanced": False,
    }
    result = wizard.execute_import(["date", "payment_ref", "amount", "balance"], [], options, dryrun=False)
    assert not result["messages"], result["messages"]

MODULE = "account_bank_statement_import_csv_patch"


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


demo_action("demo_statement_moves", {
    "name": "Asientos de las transacciones importadas",
    "res_model": "account.move",
    "view_mode": "list,form",
    "view_id": env.ref("account.view_move_tree").id,
    "domain": "[('journal_id', '=', %s), ('statement_line_id', '!=', False)]" % journal.id,
})
demo_action("demo_statements", {
    "name": "Extractos del diario",
    "res_model": "account.bank.statement",
    "view_mode": "list,form",
    "domain": "[('journal_id', '=', %s)]" % journal.id,
})

env.cr.commit()
print("SEED OK journal=%s company=%s" % (journal.id, company.id))
