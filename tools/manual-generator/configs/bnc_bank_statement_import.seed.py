# Seed for the manual of bnc_bank_statement_import.
#
# Builds, from a CLEAN DB with the module installed:
#   * Spanish UI, a chart of accounts and the accounting groups for admin
#   * a bank journal whose bank account is marked as Banesco (l10n_do_bank =
#     "banesco") and carries the account number of the sample file
#   * demo actions for the bank account form and the imported lines
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

import odoo

env = odoo.api.Environment(env.cr, odoo.SUPERUSER_ID, {})
company = env.ref("base.main_company")

company.name = "INDEXA SRL"
if not company.chart_template:
    env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)
es = env["res.lang"]._activate_lang("es_DO")
env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
admin = env.ref("base.user_admin")
admin.lang = "es_DO"
admin.group_ids = [
    (4, env.ref("account.group_account_basic").id),
    (4, env.ref("account.group_account_user").id),
    (4, env.ref("account.group_account_manager").id),
]
dop = env.ref("base.DOP")
dop.active = True

env = env(context=dict(env.context, lang="es_DO"))
MODULE = "bnc_bank_statement_import"

journal = env.ref("%s.demo_journal" % MODULE, raise_if_not_found=False)
if not journal:
    bank_account = env["res.partner.bank"].create({
        "account_number": "123456789",
        "l10n_do_bank": "banesco",
        "l10n_do_account_type": "cheque",
        "partner_id": company.partner_id.id,
    })
    journal = env["account.journal"].create({
        "name": "Banesco - Cuenta Corriente",
        "code": "BNC1",
        "type": "bank",
        "currency_id": dop.id,
        "bank_account_id": bank_account.id,
    })
    env["ir.model.data"].create(
        {"module": MODULE, "name": "demo_journal", "model": "account.journal", "res_id": journal.id, "noupdate": True}
    )


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


demo_action("demo_bank_account", {
    "name": "Cuenta bancaria del diario",
    "res_model": "res.partner.bank",
    "view_mode": "form",
    "res_id": journal.bank_account_id.id,
})
demo_action("demo_statement_lines", {
    "name": "Transacciones importadas - Banesco",
    "res_model": "account.bank.statement.line",
    "view_mode": "list,form",
    "view_id": env.ref("account_accountant.view_bank_statement_line_tree_bank_rec_widget").id,
    "domain": "[('journal_id', '=', %s)]" % journal.id,
})

env.cr.commit()
print("SEED OK %s journal=%s" % (MODULE, journal.id))
