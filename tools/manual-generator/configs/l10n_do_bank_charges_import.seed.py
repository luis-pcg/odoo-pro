# Seed for the manual of l10n_do_bank_charges_import.
#
# Builds, from a CLEAN DB:
#   * a Dominican company with the DO chart of accounts, which is what brings
#     the fiscal purchase journals and the e-CF document types
#   * a bank journal and a charge product
#   * one completed import whose charge reference is an e-CF (E31), run through
#     the module's own code with only the file parsing stubbed, so the manual
#     can show the fiscal fields this module stamps on the bill
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

from datetime import date
from unittest.mock import patch

import odoo

env = odoo.api.Environment(env.cr, odoo.SUPERUSER_ID, {})

company = env.ref("base.main_company")
do = env.ref("base.do")

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
            [
                "l10n_do_bank_charges_import",
                "account_bank_charge_import_base",
                "l10n_do_accounting",
                "l10n_do",
                "account",
            ],
        ),
        ("state", "=", "installed"),
    ]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Compania dominicana con su plan contable -----------------------------
company.write(
    {
        "name": "INDEXA SRL",
        "country_id": do.id,
        "vat": "131793916",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
    }
)
env["account.chart.template"].try_loading("do", company=company, install_demo=False)

admin = env.ref("base.user_admin")
admin.group_ids = [
    (4, env.ref("account.group_account_basic").id),
    (4, env.ref("account.group_account_user").id),
    (4, env.ref("account.group_account_manager").id),
]

# -- 2. Diario de banco y diarios fiscales de compra -------------------------
journal = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
if not journal:
    journal = env["account.journal"].create({"name": "Banco", "code": "BNK1", "type": "bank"})
journal.name = "Banco - Cuenta Operativa"
if not journal.bank_account_id:
    journal.set_bank_account("0011223344")

purchase_journals = env["account.journal"].search(
    [("type", "=", "purchase"), ("l10n_latam_use_documents", "=", True), ("company_id", "=", company.id)]
)
# The extra journal is what makes the module's field show up in the wizard.
if len(purchase_journals) < 2:
    env["account.journal"].create(
        {
            "name": "Compras Fiscales - Gastos Menores",
            "code": "CFGM",
            "type": "purchase",
            "company_id": company.id,
            "l10n_latam_use_documents": True,
        }
    )
purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("l10n_latam_use_documents", "=", True), ("company_id", "=", company.id)],
    limit=1,
)

# -- 3. Producto de cargo ----------------------------------------------------
expense = env["account.account"].search([("account_type", "=", "expense"), ("company_ids", "=", company.id)], limit=1)
product = env["product.product"].create(
    {
        "name": "Comisiones bancarias",
        "type": "service",
        "supplier_taxes_id": False,
        "property_account_expense_id": expense.id,
    }
)

# -- 4. Importacion con una referencia e-CF ----------------------------------
CHARGES = {
    "E310000000123": {
        "type": "in_invoice",
        "origin": "",
        "payments": [
            {"date": date(2026, 3, 9), "reference": "COMISION MANEJO DE CUENTA", "amount": 350.0},
            {"date": date(2026, 3, 24), "reference": "COMISION TRANSFERENCIA LBTR", "amount": 1250.0},
        ],
    },
}

bank_partner = env["res.partner"].create(
    {
        "name": "BANCO MULTIPLE BHD SA",
        "vat": "101136792",
        "country_id": do.id,
        "street": "Calle Luis F. Thomen",
        "city": "Santo Domingo",
    }
)

wizard = env["account.bank.charge.import_wizard"].create(
    {
        "company_id": company.id,
        "journal_id": journal.id,
        "purchase_journal_id": purchase_journal.id,
        "invoice_product_ids": [
            (0, 0, {"reference": "E310000000123", "product_id": product.id, "name": "Comisiones de marzo"})
        ],
    }
)

BASE = "odoo.addons.account_bank_charge_import_base.wizard.account_bank_charge_import_wizard"
with (
    patch(f"{BASE}.AccountBankChargeImportWizard._parse_file", return_value=("DOP", None, CHARGES)),
    patch(f"{BASE}.AccountBankChargeImportWizard._get_bank_partner_id", return_value=bank_partner),
):
    wizard.import_bank_charges()

invoice = env["account.move"].search([("ref", "=", "E310000000123")], limit=1)

# -- 5. Acciones demo para las capturas --------------------------------------
MODULE = "l10n_do_bank_charges_import"


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
    "name": "Factura fiscal de cargos bancarios",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": invoice.id,
})
demo_action("demo_journals", {
    "name": "Diarios fiscales de compra",
    "res_model": "account.journal",
    "view_mode": "list,form",
    "domain": "[('type', '=', 'purchase'), ('l10n_latam_use_documents', '=', True)]",
})

env.cr.commit()
print(
    "SEED OK: %s, diario %s, tipo doc %s, ncf %s, gasto %s"
    % (
        invoice.name,
        invoice.journal_id.name,
        invoice.l10n_latam_document_type_id.doc_code_prefix,
        invoice.l10n_latam_document_number,
        invoice.l10n_do_expense_type,
    )
)
