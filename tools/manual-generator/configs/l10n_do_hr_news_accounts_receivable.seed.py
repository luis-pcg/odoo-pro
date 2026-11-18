# Datos de ejemplo para el manual de l10n_do_hr_news_accounts_receivable (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date

from odoo.tests import Form

MODULE = "l10n_do_hr_news_accounts_receivable"

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write(
    {
        "lang": "es_DO",
        "tz": "America/Santo_Domingo",
        "tour_enabled": False,
        "group_ids": [(4, env.ref("account.group_account_manager").id), (4, env.ref("sales_team.group_sale_manager").id)],
    }
)

do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
company = env.ref("base.main_company")
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id})
try:
    with env.cr.savepoint():
        company.currency_id = dop.id
except Exception:
    pass
if not company.chart_template:
    env["account.chart.template"].try_loading("generic_coa", company, install_demo=False)

Employee = env["hr.employee"]
if not admin.employee_id:
    Employee.create({"name": "Administrador", "user_id": admin.id})
env = env(user=admin.id, context=dict(env.context, lang="es_DO"))

bank = env["account.journal"].search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
outstanding = env["account.account"].search([("code", "=", "101402")], limit=1) or env["account.account"].create(
    {"name": "Cobros pendientes de depositar", "code": "101402", "account_type": "asset_current", "reconcile": True}
)
bank.inbound_payment_method_line_ids.payment_account_id = outstanding

structure = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
stype = env.ref("l10n_do_hr_payroll.structure_type_employee")
stype.default_schedule_pay = "monthly"
rule = env.ref("l10n_do_hr_payroll.hr_rule_credit_invoices")

news_type = env["l10n.do.hr.news.type"].create(
    {
        "name": "Venta a crédito a empleados",
        "validation_type": "manager",
        "salary_rule_id": rule.id,
        "is_accounts_receivable_type": True,
        "journal_id": bank.id,
    }
)


def employee(name):
    return env["hr.employee"].create(
        {
            "name": name,
            "company_id": company.id,
            "country_id": do.id,
            "l10n_do_has_papers": True,
            "wage": 60000.0,
            "date_version": date(2022, 1, 1),
            "contract_date_start": date(2022, 1, 1),
            "structure_type_id": stype.id,
        }
    )


maria = employee("María Altagracia Rosario")
pedro = employee("Pedro Antonio Jiménez")

product = env["product.product"].create(
    {
        "name": "Lentes graduados con montura",
        "type": "service",
        "list_price": 12000.0,
        "invoice_policy": "order",
        "taxes_id": [(6, 0, [])],
    }
)


def credit_sale(emp, first_payment, quantity):
    order = env["sale.order"].create(
        {
            "partner_id": emp.work_contact_id.id,
            "first_payment": first_payment,
            "payment_quantity": quantity,
            "order_line": [(0, 0, {"product_id": product.id, "product_uom_qty": 1, "tax_ids": [(6, 0, [])]})],
        }
    )
    order.action_confirm()
    invoice = order._create_invoices()
    invoice.invoice_date = date(2026, 9, 2)
    news = env["l10n.do.hr.news"].create(
        {
            "news_type_id": news_type.id,
            "employee_id": emp.id,
            "partner_id": emp.work_contact_id.id,
            "request_date": date(2026, 9, 2),
            "sale_order_id": order.id,
            "first_payment": order.first_payment,
            "payment_quantity": order.payment_quantity,
            "recurrent_amount": order.amount_total,
        }
    )
    news.note = "Compra de %s en la óptica de la empresa, descontada por nómina." % product.name
    news.action_confirm()
    invoice.l10n_do_hr_news_id = news
    invoice.action_post()
    return order, invoice, news


order_p, invoice_p, news_p = credit_sale(pedro, 3000.0, 4)
order_m, invoice_m, news_m = credit_sale(maria, 3000.0, 4)

register = Form(env["account.payment.register"].with_context(active_model="account.move", active_ids=invoice_m.ids))
register.payment_date = date(2026, 9, 2)
register.save().action_create_payments()

payslip = env["hr.payslip"].create(
    {
        "name": "Nómina Septiembre 2026 - María Altagracia Rosario",
        "employee_id": maria.id,
        "version_id": maria.version_id.id,
        "struct_id": structure.id,
        "company_id": company.id,
        "date_from": date(2026, 9, 1),
        "date_to": date(2026, 9, 30),
    }
)
payslip.compute_sheet()
payslip.action_validate()


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


form_action("demo_news_type", news_type)
form_action("demo_employee", pedro)
form_action("demo_sale_order", order_p)
form_action("demo_news_pending", news_p)
form_action("demo_invoice_pending", invoice_p)
form_action("demo_news_approved", news_m)
form_action("demo_payslip", payslip)
form_action("demo_invoice_paid", invoice_m)

assert news_p.state == "confirm" and news_p.account_move_id == invoice_p, "pending news not linked"
assert news_m.state == "validate" and news_m.salary_attachment_id, "first payment did not approve the news"
assert payslip.state == "validated", "payslip not validated"
assert len(invoice_m.matched_payment_ids) == 2, "payslip did not pay the installment"
print(
    "seed %s OK: residual %s, payments %s"
    % (MODULE, invoice_m.amount_residual, invoice_m.matched_payment_ids.mapped("amount"))
)
env.cr.commit()
