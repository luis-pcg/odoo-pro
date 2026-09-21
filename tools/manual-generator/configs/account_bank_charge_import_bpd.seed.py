# Seed for the manual of account_bank_charge_import_bpd.
#
# Builds, from a CLEAN DB:
#   * a company with a chart of accounts and a bank journal whose bank account
#     is marked as Banco Popular -- that marker is the module's whole gate
#   * a charge product with an expense account
#   * one completed import of the module's own example csv, run through the
#     module's real parser: no stubbing anywhere, unlike the base module's
#     manual, because reading the file is exactly what this module adds
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

import odoo
from odoo.tools import BinaryBytes
from odoo.tools.misc import file_open, file_path

env = odoo.api.Environment(env.cr, odoo.SUPERUSER_ID, {})

company = env.ref("base.main_company")
company.write({"name": "INDEXA SRL"})

# -- 0. Espanol --------------------------------------------------------------
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

env["ir.module.module"].search(
    [
        (
            "name",
            "in",
            ["account_bank_charge_import_bpd", "account_bank_charge_import_base", "account", "l10n_do_banks"],
        ),
        ("state", "=", "installed"),
    ]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Plan contable y permisos --------------------------------------------
env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)

admin = env.ref("base.user_admin")
admin.group_ids = [
    (4, env.ref("account.group_account_basic").id),
    (4, env.ref("account.group_account_user").id),
    (4, env.ref("account.group_account_manager").id),
]

# -- 2. Diario de banco marcado como Banco Popular ---------------------------
# l10n_do_bank en la cuenta bancaria es lo unico que le dice al modulo que este
# diario es del BPD; sin eso, delega en el modulo base y no lee nada.
dop = env.ref("base.DOP")
dop.active = True

journal = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
if not journal:
    journal = env["account.journal"].create({"name": "Banco", "code": "BNK1", "type": "bank"})
journal.write({"name": "Banco Popular - Cuenta Operativa", "currency_id": dop.id})
partner_bank = env["res.partner.bank"].create(
    {
        "partner_id": company.partner_id.id,
        "account_number": "011137683",
        "l10n_do_bank": "bpd",
    }
)
journal.bank_account_id = partner_bank

transfer_account = company.transfer_account_id
if transfer_account:
    journal.outbound_payment_method_line_ids.write({"payment_account_id": transfer_account.id})
    journal.inbound_payment_method_line_ids.write({"payment_account_id": transfer_account.id})

# -- 3. Producto de cargo ----------------------------------------------------
expense = env["account.account"].search([("account_type", "=", "expense"), ("company_ids", "=", company.id)], limit=1)
product = env["product.product"].create(
    {
        "name": "Comisiones e intereses bancarios",
        "type": "service",
        "supplier_taxes_id": False,
        "property_account_expense_id": expense.id,
    }
)

# -- 4. Importacion real del csv de ejemplo del modulo -----------------------
path = file_path("account_bank_charge_import_bpd/bpd_charges_file/bpd_chrgs.csv")
content = file_open(path, "rb").read()

wizard = env["account.bank.charge.import_wizard"].create(
    {
        "company_id": company.id,
        "journal_id": journal.id,
        "data_file": BinaryBytes(content),
        "filename": "bpd_chrgs.csv",
        "validate": True,
        "invoice_product_ids": [(0, 0, {"reference": "placeholder"})],
    }
)
wizard.onchange_data_file()
for line in wizard.invoice_product_ids:
    line.product_id = product
    line.onchange_product_id()

references = wizard.invoice_product_ids.mapped("reference")
wizard.import_bank_charges()

invoices = env["account.move"].search([("ref", "in", references), ("move_type", "in", ("in_invoice", "in_refund"))])
payments = env["account.payment"].search([("journal_id", "=", journal.id)])

# -- 5. Acciones demo para las capturas --------------------------------------
MODULE = "account_bank_charge_import_bpd"


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


demo_action("demo_journal", {
    "name": "Diario del BPD",
    "res_model": "account.journal",
    "view_mode": "form",
    "res_id": journal.id,
})
demo_action("demo_invoices", {
    "name": "Facturas de cargos BPD",
    "res_model": "account.move",
    "view_mode": "list,form",
    "domain": "[('id', 'in', %s)]" % invoices.ids,
})
demo_action("demo_invoice", {
    "name": "Factura de cargo BPD",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": invoices.sorted("amount_total", reverse=True)[0].id,
})
demo_action("demo_payments", {
    "name": "Pagos generados",
    "res_model": "account.payment",
    "view_mode": "list,form",
    "domain": "[('journal_id', '=', %s)]" % journal.id,
})

env.cr.commit()
print(
    "SEED OK: %s referencias, %s facturas por %s, %s pagos"
    % (len(references), len(invoices), sum(invoices.mapped("amount_total")), len(payments))
)
