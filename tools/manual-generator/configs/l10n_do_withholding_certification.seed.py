# Seed for the functional manual of l10n_do_withholding_certification (Odoo 17).
#
# Builds the one scenario the manual walks through: a vendor bill whose
# withholding is booked in a SEPARATE journal entry, reconciled with the bill,
# and then paid for the residual. That is the shape that used to be classified
# as the "entry" withholding type -- the type this branch removes -- so the
# manual is what proves the certificate still comes out right without it.
#
#   bill B0100000001  RD$ 600.00
#   entry RET-MANUAL  ITBIS withheld  32.41  +  ISR withheld  60.00   (92.41)
#   payment           RD$ 507.59
#
# Executed inside `odoo shell`; the global `env` is available. Ends with commit.
# Re-runnable: every record is looked up by its xml id first.

from odoo import fields

MODULE = "l10n_do_wh_manual"


def ref(name):
    return env.ref("%s.%s" % (MODULE, name), raise_if_not_found=False)


def tag(record, name):
    """Give `record` a stable xml id so the manual can navigate to it."""
    if not ref(name):
        env["ir.model.data"].create(
            {
                "module": MODULE,
                "name": name,
                "model": record._name,
                "res_id": record.id,
                "noupdate": True,
            }
        )
    return record


# --- company -----------------------------------------------------------------
company = env["res.company"].search([("chart_template", "=", "do")], limit=1)
if not company:
    raise ValueError("no company with the Dominican chart of accounts in this database")
company.write(
    {
        "l10n_do_withholding_cert_type": "private",
        "l10n_do_show_header": True,
        "l10n_do_show_footer": True,
    }
)
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
tag(company, "company")

# The manual is browsed as `admin`, which in a demo database is not an
# accountant: without these groups every account.move it opens is an Access
# Error, and the certificate report renders empty.
admin = env.ref("base.user_admin")
admin.write(
    {
        "company_ids": [(4, company.id)],
        "company_id": company.id,
        "groups_id": [
            (4, env.ref("account.group_account_manager").id),
            (4, env.ref("account.group_account_user").id),
        ],
    }
)

# --- withholding accounts ----------------------------------------------------
# The certificate reads l10n_do_tax_name and l10n_do_legal_base off the account,
# so an account flagged as withholding but left without them prints an empty
# tax name and an empty legal base.
def wh_account(code, tax_name, legal_base, xml_name):
    account = env["account.account"].search(
        [("code", "=like", "%" + code), ("company_id", "=", company.id)], limit=1
    )
    if not account:
        raise ValueError("account %s not found; is the `do` chart loaded?" % code)
    account.write(
        {
            "is_l10n_do_withholding_account": True,
            "l10n_do_tax_name": tax_name,
            "l10n_do_legal_base": legal_base,
        }
    )
    return tag(account, xml_name)


itbis_account = wh_account(
    "21030201", "ITBIS", "la Norma General 02-05 de la DGII", "account_itbis_withheld"
)
isr_account = wh_account(
    "21030301", "ISR", "el Art. 309 del Código Tributario", "account_isr_withheld"
)

# --- vendor ------------------------------------------------------------------
partner = ref("partner")
if not partner:
    partner = env["res.partner"].create(
        {
            "name": "Servicios Profesionales Peña, SRL",
            "company_type": "company",
            "vat": "131793916",
            "country_id": env.ref("base.do").id,
            "l10n_do_dgii_tax_payer_type": "taxpayer",
            "l10n_do_expense_type": "02",
            "supplier_rank": 1,
        }
    )
    tag(partner, "partner")

# --- journals ----------------------------------------------------------------
# A dedicated purchase journal: "Use Documents" (what turns on the NCF) cannot be
# flipped on a journal that already holds posted invoices, and the demo BILL
# journal does.
purchase_journal = ref("purchase_journal")
if not purchase_journal:
    purchase_journal = env["account.journal"].create(
        {
            "name": "Facturas de Proveedor (NCF)",
            "code": "FPNCF",
            "type": "purchase",
            "company_id": company.id,
            "l10n_latam_use_documents": True,
        }
    )
    tag(purchase_journal, "purchase_journal")
misc_journal = env["account.journal"].search(
    [("type", "=", "general"), ("company_id", "=", company.id), ("code", "=", "MISC")], limit=1
) or env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
bank_journal = env["account.journal"].search(
    [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
)

# --- the bill ----------------------------------------------------------------
bill = ref("bill")
if not bill:
    expense_account = env["account.account"].search(
        [("company_id", "=", company.id), ("account_type", "=", "expense")], limit=1
    )
    doc_type = env["l10n_latam.document.type"].search(
        [("l10n_do_ncf_type", "=", "fiscal"), ("internal_type", "=", "invoice")], limit=1
    )
    bill = env["account.move"].create(
        {
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "journal_id": purchase_journal.id,
            "invoice_date": fields.Date.today(),
            "l10n_do_expense_type": "02",
            "invoice_line_ids": [
                (0, 0, {"name": "Honorarios profesionales - septiembre", "account_id": expense_account.id, "price_unit": 600.0, "quantity": 1, "tax_ids": [(5, 0, 0)]}),
            ],
        }
    )
    if doc_type:
        bill.l10n_latam_document_type_id = doc_type.id
    bill.l10n_latam_document_number = "B0100000001"
    bill.action_post()
    tag(bill, "bill")

# --- the withholding journal entry -------------------------------------------
# ITBIS 30% of the 18% ITBIS on 600 = 32.41 -- the same figure the unit test
# uses -- plus a 10% ISR on professional fees. Counterpart on the payable
# account, which is what makes the entry reconcilable with the bill.
entry = ref("withholding_entry")
if not entry:
    payable_line = bill.line_ids.filtered(
        lambda ml: ml.account_id.account_type == "liability_payable"
    )[0]
    entry = env["account.move"].create(
        {
            "move_type": "entry",
            "ref": "Retenciones factura B0100000001",
            "journal_id": misc_journal.id,
            "date": fields.Date.today(),
            "line_ids": [
                (0, 0, {"name": "Retención ITBIS 30%", "account_id": itbis_account.id, "credit": 32.41, "debit": 0.0, "partner_id": partner.id}),
                (0, 0, {"name": "Retención ISR 10%", "account_id": isr_account.id, "credit": 60.0, "debit": 0.0, "partner_id": partner.id}),
                (0, 0, {"name": "Retenciones B0100000001", "account_id": payable_line.account_id.id, "debit": 92.41, "credit": 0.0, "partner_id": partner.id}),
            ],
        }
    )
    entry.action_post()
    tag(entry, "withholding_entry")

    # Reconcile the entry with the bill: the withholding stops being a debt.
    bill.js_assign_outstanding_line(entry.line_ids.filtered(lambda ml: ml.debit > 0).id)

# --- the payment -------------------------------------------------------------
payment = ref("payment")
if not payment:
    wizard = (
        env["account.payment.register"]
        .with_context(active_model="account.move", active_ids=bill.ids)
        .create(
            {
                "payment_date": fields.Date.today(),
                "journal_id": bank_journal.id,
                "amount": bill.amount_residual,
            }
        )
    )
    payment = wizard._create_payments()
    tag(payment, "payment")

# --- what the manual claims --------------------------------------------------
data = payment.get_certification_data()
print("seed: bill %s total %.2f residual %.2f" % (bill.name, bill.amount_total, bill.amount_residual))
print("seed: payment %s amount %.2f" % (payment.name, payment.amount))
print("seed: has_l10n_do_withholding=%s type=%s" % (payment.has_l10n_do_withholding, payment.l10n_do_withholding_type))
print("seed: withholding_values=%s" % {a.code: v for a, v in data["withholding_values"].items()})
print("seed: paid=%.2f gross=%.2f words=%s" % (data["paid_amount"], data["payments_amount"], data["amount_in_words"]))
print("seed: payment_id=%s bill_id=%s entry_id=%s" % (payment.id, bill.id, entry.id))

env.cr.commit()
print("seed: committed")
