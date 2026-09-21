# Seed for the manual of account_bank_charge_import_base.
#
# Builds, from a CLEAN DB:
#   * a company with a chart of accounts and a bank journal that already knows
#     its account number, which is what the import matches the file against
#   * two charge products with an expense account, the mapping the wizard asks
#     the user to fill in
#   * one completed import, run through the module's OWN code with the file
#     parsing stubbed, so the manual can show the vendor bill and the payments
#     the module produces
#
# The parser is stubbed because it is the one thing this module does not have:
# _parse_file raises by design and every bank ships its own override
# (account_bank_charge_import_bhd, _bpd). Everything downstream of that return
# value -- invoice, taxes, analytic distribution, payments, reconciliation --
# is the module's code, untouched.
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

from datetime import date
from unittest.mock import patch

import odoo

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
    [("name", "in", ["account_bank_charge_import_base", "account", "l10n_do_banks"]), ("state", "=", "installed")]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Plan contable y permisos --------------------------------------------
env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)

# group_account_basic is what the dashboard KPI check asks for; the manager
# group does not imply it on its own in 20.0.
admin = env.ref("base.user_admin")
admin.group_ids = [
    (4, env.ref("account.group_account_basic").id),
    (4, env.ref("account.group_account_user").id),
    (4, env.ref("account.group_account_manager").id),
    (4, env.ref("analytic.group_analytic_accounting").id),
]

# -- 2. Diario de banco con su numero de cuenta ------------------------------
journal = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
if not journal:
    journal = env["account.journal"].create({"name": "Banco", "code": "BNK1", "type": "bank"})
journal.name = "BHD - Cuenta Operativa"
if not journal.bank_account_id:
    journal.set_bank_account("0011223344")

# -- 3. Productos de cargo ---------------------------------------------------
expense = env["account.account"].search(
    [("account_type", "=", "expense"), ("company_ids", "=", company.id)], limit=1
)
Product = env["product.product"]
comisiones = Product.create(
    {
        "name": "Comisiones bancarias",
        "type": "service",
        "supplier_taxes_id": False,
        "property_account_expense_id": expense.id,
    }
)
Product.create(
    {
        "name": "Cargos por transferencia",
        "type": "service",
        "supplier_taxes_id": False,
        "property_account_expense_id": expense.id,
    }
)

# -- 4. Una importacion completa, hecha por el propio modulo -----------------
CHARGES = {
    "B0157199285": {
        "type": "in_invoice",
        "origin": "",
        "payments": [
            {"date": date(2026, 3, 4), "reference": "COMISION PAGO IMPUESTO X IB", "amount": 75.15},
            {"date": date(2026, 3, 17), "reference": "EXI COMISION TRANS APROBA CCT", "amount": 2508.24},
        ],
    },
}

# The check digit matters: since 20.0 base validates every tax id on save.
BANK_VALUES = {
    "name": "BANCO MULTIPLE BHD SA",
    "vat": "101136792",
    "street": "Calle Luis F. Thomen",
    "city": "Santo Domingo",
    "country_id": env.ref("base.do").id,
}

wizard = env["account.bank.charge.import_wizard"].create(
    {
        "company_id": company.id,
        "journal_id": journal.id,
        "invoice_product_ids": [
            (0, 0, {"reference": "B0157199285", "product_id": comisiones.id, "name": "Comisiones de marzo"})
        ],
    }
)

WIZARD = "odoo.addons.account_bank_charge_import_base.wizard.account_bank_charge_import_wizard"
bank_partner = env["res.partner"].create(BANK_VALUES)
with (
    patch(f"{WIZARD}.AccountBankChargeImportWizard._parse_file", return_value=("USD", "0011223344", CHARGES)),
    patch(f"{WIZARD}.AccountBankChargeImportWizard._get_bank_partner_id", return_value=bank_partner),
):
    wizard.import_bank_charges()

invoice = env["account.move"].search([("ref", "=", "B0157199285")], limit=1)
payments = env["account.payment"].search([("journal_id", "=", journal.id)])

# -- 5. Acciones demo para las capturas --------------------------------------
MODULE = "account_bank_charge_import_base"


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


demo_action("demo_invoice", {
    "name": "Factura de cargos bancarios",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": invoice.id,
})
demo_action("demo_payments", {
    "name": "Pagos generados",
    "res_model": "account.payment",
    "view_mode": "list,form",
    "domain": "[('journal_id', '=', %s)]" % journal.id,
})
demo_action("demo_journal", {
    "name": "Diario de banco",
    "res_model": "account.journal",
    "view_mode": "form",
    "res_id": journal.id,
})

env.cr.commit()
print(
    "SEED OK: factura %s por %s, %s pagos, estado %s"
    % (invoice.name, invoice.amount_total, len(payments), invoice.payment_state)
)
