# Datos de ejemplo para el manual de l10n_do_hr_expense (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date

MODULE = "l10n_do_hr_expense"

do = env.ref("base.do")
env.ref("base.DOP").active = True
company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id, "vat": "131793916"})
env["account.chart.template"].try_loading("do", company=company, install_demo=False)
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= env.ref("account.group_account_manager") | env.ref("hr_expense.group_hr_expense_manager")

company.partner_id.lang = "es_DO"
if "l10n_do_sequence_manager" in company._fields:
    company.l10n_do_sequence_manager = False

Journal = env["account.journal"].with_company(company)
expense_journal = Journal.search([("company_id", "=", company.id), ("code", "=", "GEMP")], limit=1) or Journal.create(
    {"name": "Gastos de Empleados", "code": "GEMP", "type": "purchase", "l10n_latam_use_documents": False}
)
fiscal_journal = Journal.search(
    [("company_id", "=", company.id), ("type", "=", "purchase"), ("l10n_latam_use_documents", "=", True)], limit=1
)
bridge_account = env["account.account"].search(
    [("code", "=", "11010399"), ("company_ids", "in", company.id)], limit=1
) or env["account.account"].create(
    {
        "name": "Puente de Gastos",
        "code": "11010399",
        "account_type": "asset_current",
        "reconcile": True,
        "company_ids": [(6, 0, company.ids)],
    }
)
bridge_journal = Journal.search([("company_id", "=", company.id), ("code", "=", "PGAS")], limit=1) or Journal.create(
    {
        "name": "Puente de Gastos",
        "code": "PGAS",
        "type": "cash",
        "default_account_id": bridge_account.id,
        "show_on_dashboard": False,
    }
)
bridge_journal.outbound_payment_method_line_ids.payment_account_id = bridge_account

Partner = env["res.partner"]
minor_vendor = Partner.create(
    {
        "name": "Proveedor Gastos Menores",
        "is_company": True,
        "country_id": do.id,
        "l10n_do_expense_type": "02",
        "supplier_rank": 1,
    }
)
fiscal_vendor = Partner.create(
    {
        "name": "Ferretería Ochoa SRL",
        "is_company": True,
        "country_id": do.id,
        "vat": "131566332",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
        "l10n_do_expense_type": "02",
        "supplier_rank": 1,
    }
)

bank_journal = Journal.search([("company_id", "=", company.id), ("type", "=", "bank")], limit=1)
company_method = bank_journal.outbound_payment_method_line_ids[:1]
company.write(
    {
        "expense_journal_id": expense_journal.id,
        "l10n_do_expense_fiscal_journal_id": fiscal_journal.id,
        "l10n_do_expense_bridge_journal_id": bridge_journal.id,
        "l10n_do_expense_minor_vendor_id": minor_vendor.id,
        "company_expense_allowed_payment_method_line_ids": [(6, 0, company_method.ids)],
    }
)

employee = env["hr.employee"].create(
    {"name": "María Pérez", "user_id": admin.id, "company_id": company.id, "work_email": "maria@example.com"}
)
product = env["product.product"].create(
    {"name": "Materiales de oficina", "type": "service", "can_be_expensed": True, "standard_price": 0.0, "supplier_taxes_id": [(6, 0, [])]}
)


def expense(name, fiscal_type, payment_mode, amount, ncf=None):
    vals = {
        "name": name,
        "employee_id": employee.id,
        "product_id": product.id,
        "total_amount_currency": amount,
        "payment_mode": payment_mode,
        "l10n_do_expense_fiscal_type": fiscal_type,
        "date": date(2026, 9, 28),
    }
    if fiscal_type == "fiscal":
        vals.update({"l10n_do_vendor_id": fiscal_vendor.id, "l10n_do_fiscal_number": ncf})
    record = env["hr.expense"].create(vals)
    if payment_mode == "company_account":
        record.payment_method_line_id = company_method
    return record


draft = expense("Taxi a reunión con cliente", "minor", "own_account", 850.0)
fiscal_draft = expense("Compra de herramientas", "fiscal", "own_account", 2360.0, "B0100000123")
approved = expense("Almuerzo con proveedor", "minor", "own_account", 1200.0)
approved.action_submit()
approved.action_approve()
posted = expense("Pinturas y brochas", "fiscal", "own_account", 4720.0, "B0100000456")
posted.action_submit()
posted.action_approve()
posted.account_move_id.action_post()
company_approved = expense("Combustible flotilla", "minor", "company_account", 3000.0)
company_approved.action_submit()
company_approved.action_approve()
company_paid = expense("Cables eléctricos", "fiscal", "company_account", 5900.0, "B0100000789")
company_paid.action_submit()
company_paid.action_approve()


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


def form_action(xmlid, record):
    demo_action(xmlid, {"name": record.display_name, "res_model": record._name, "view_mode": "form", "res_id": record.id})


def lines_action(xmlid, name, moves):
    demo_action(
        xmlid,
        {
            "name": name,
            "res_model": "account.move.line",
            "view_mode": "list",
            "domain": [("move_id", "in", moves.ids), ("display_type", "not in", ("line_section", "line_note"))],
            "context": {"group_by": ["move_id"]},
        },
    )


form_action("demo_expense_minor", draft)
form_action("demo_expense_fiscal", fiscal_draft)
form_action("demo_expense_approved", approved)
form_action("demo_receipt_draft", approved.account_move_id)
form_action("demo_expense_posted", posted)
form_action("demo_fiscal_bill", posted.l10n_do_fiscal_move_id)
lines_action("demo_posted_lines", "Asientos del gasto pagado por el empleado", posted.account_move_id | posted.l10n_do_fiscal_move_id | posted.l10n_do_fiscal_move_id.matched_payment_ids.move_id)
form_action("demo_company_bill_minor", company_approved.account_move_id)
form_action("demo_expense_company_paid", company_paid)
lines_action("demo_company_lines", "Asientos del gasto pagado por la empresa", company_paid.account_move_id | company_paid.account_move_id.matched_payment_ids.move_id)

assert approved.account_move_id.state == "draft" and not approved.l10n_do_fiscal_move_id
assert posted.l10n_do_fiscal_move_id.state == "posted" and posted.l10n_do_fiscal_move_id.matched_payment_ids
assert company_approved.account_move_id.state == "posted" and company_approved.account_move_id.matched_payment_ids
assert company_paid.account_move_id.matched_payment_ids and company_paid.state in ("paid", "in_payment")
print("seed l10n_do_hr_expense OK: %s / %s" % (posted.l10n_do_fiscal_move_id.name, company_paid.account_move_id.name))
env.cr.commit()
