# Seed for the manual of dgii_reports (Declaraciones DGII 606/607/608/609).
# Builds, from a CLEAN DB, a Dominican company with one month (08/2026) of:
#
#   606  compra fiscal B01 pagada por banco + compra informal B11 con retencion
#        de 100% ITBIS y 10% ISR, pagada.
#   607  venta fiscal B01 pagada en efectivo + venta de consumo B02 a credito.
#   608  venta fiscal B01 anulada (tipo 05).
#   609  pago al exterior B17 a un proveedor de EE. UU.
#
# plus a sent report for 07/2026 and a generated report for 08/2026.
# Ejecutado dentro de `odoo shell` (`env` disponible). Termina con commit.

MODULE = "dgii_reports"

company = env.ref("base.main_company")
do = env.ref("base.do")
admin = env.ref("base.user_admin")

# -- 0. Plan contable dominicano (antes del espanol: los codigos de diario
#       traducidos exceden los 7 caracteres del campo) ------------------------
company.write({"country_id": do.id})
env(context=dict(env.context, lang="en_US"))["account.chart.template"].try_loading("do", company=company, install_demo=False)

# -- 0. Espanol --------------------------------------------------------------
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin.lang = "es_DO"
admin.tour_enabled = False
env = env(context=dict(env.context, lang="es_DO"))
env["ir.module.module"].search(
    [("name", "in", [MODULE, "l10n_do_accounting", "l10n_do"]), ("state", "=", "installed")]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Compania RD + plan contable dominicano -------------------------------
company.write(
    {
        "name": "INDEXA SRL",
        "country_id": do.id,
        "vat": "131793916",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
    }
)
company.partner_id.lang = "es_DO"
admin.group_ids = [
    (4, env.ref("account.group_account_manager").id),
    (4, env.ref("account.group_account_user").id),
    (4, env.ref("account.group_account_basic").id),
    (4, env.ref("l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel").id),
]


def tax_ref(xmlid):
    return env.ref("account.%s_%s" % (company.id, xmlid))


itbis_purch = tax_ref("tax_18_purch")
itbis_sale = tax_ref("tax_18_sale")
ret_itbis_100 = tax_ref("ret_100_tax_person")
ret_isr_10 = tax_ref("ret_10_income_person")

# Cuentas de retencion clasificadas para el 606 (Tipo fiscal de cuenta).
ret_itbis_account = ret_itbis_100.invoice_repartition_line_ids.filtered("account_id").account_id[:1]
ret_isr_account = ret_isr_10.invoice_repartition_line_ids.filtered("account_id").account_id[:1]
ret_itbis_account.l10n_do_account_fiscal_type = "A34"
ret_isr_account.write({"l10n_do_account_fiscal_type": "ISR", "l10n_do_isr_retention_type": "02"})

# -- 2. Diarios ---------------------------------------------------------------
Journal = env["account.journal"]
sale_journal = Journal.search([("type", "=", "sale"), ("company_id", "=", company.id)], limit=1)
sale_journal.write({"name": "Ventas Fiscales", "l10n_latam_use_documents": True})
purchase_journal = Journal.search([("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1)
purchase_journal.write({"name": "Compras Fiscales", "l10n_latam_use_documents": True})
cash_journal = Journal.search([("type", "=", "cash"), ("company_id", "=", company.id)], limit=1)
cash_journal = cash_journal or Journal.create({"name": "Efectivo", "type": "cash", "code": "CSH1", "company_id": company.id})
cash_journal.l10n_do_payment_form = "cash"
bank_journal = Journal.search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
bank_journal.l10n_do_payment_form = "bank"

# -- 3. Terceros y producto ---------------------------------------------------
Partner = env["res.partner"]
iterativo = Partner.create(
    {
        "name": "ITERATIVO SRL",
        "vat": "131566332",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
        "l10n_do_related": "1",
        "country_id": do.id,
        "street": "Calle El Vergel 23",
        "city": "Santo Domingo",
    }
)
jose = Partner.create(
    {
        "name": "JOSE LUIS LOPEZ",
        "vat": "22400559690",
        "l10n_do_dgii_tax_payer_type": "non_payer",
        "country_id": do.id,
    }
)
aws = Partner.create(
    {
        "name": "Amazon Web Services Inc",
        "vat": "911986281",
        "l10n_do_dgii_tax_payer_type": "foreigner",
        "country_id": env.ref("base.us").id,
        "city": "Seattle",
    }
)
product = env["product.product"].create(
    {"name": "Servicio de consultoria", "type": "service", "lst_price": 10000, "standard_price": 6000}
)

docs = {
    "fiscal": env.ref("l10n_do_accounting.ncf_fiscal_client"),
    "consumer": env.ref("l10n_do_accounting.ncf_consumer_supplier"),
    "informal": env.ref("l10n_do_accounting.ncf_informal_supplier"),
    "exterior": env.ref("l10n_do_accounting.ncf_exterior_supplier"),
}


def make_move(move_type, partner, journal, doc, number, taxes, price, date="2026-08-05", **extra):
    if move_type == "in_invoice":
        extra.setdefault("l10n_do_expense_type", "02")
    move = env["account.move"].create(
        {
            "move_type": move_type,
            "partner_id": partner.id,
            "journal_id": journal.id,
            "invoice_date": date,
            "date": date,
            "l10n_latam_document_type_id": doc.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": product.name,
                        "quantity": 1,
                        "price_unit": price,
                        "tax_ids": [(6, 0, taxes.ids)],
                    },
                )
            ],
            **extra,
        }
    )
    move.l10n_latam_document_number = number
    move.action_post()
    return move


def pay(move, journal, date):
    env["account.payment.register"].with_context(
        active_model="account.move", active_ids=move.ids, l10n_do_active_test=True
    ).create({"journal_id": journal.id, "payment_date": date}).action_create_payments()


# -- 4. Compras (606) ---------------------------------------------------------
bill_fiscal = make_move("in_invoice", iterativo, purchase_journal, docs["fiscal"], "B0100000045", itbis_purch, 25000)
pay(bill_fiscal, bank_journal, "2026-08-20")

bill_informal = make_move(
    "in_invoice", jose, purchase_journal, docs["informal"], "B1100000012",
    itbis_purch | ret_itbis_100 | ret_isr_10, 8000, date="2026-08-10",
)
pay(bill_informal, bank_journal, "2026-08-25")

# -- 5. Pago al exterior (609) ------------------------------------------------
detail = env.ref("dgii_reports.honorarios_seriviocs_profesionales_morales")
bill_exterior = make_move(
    "in_invoice", aws, purchase_journal, docs["exterior"], "B1700000003", env["account.tax"], 1500,
    date="2026-08-12", l10n_do_service_type="02", l10n_do_service_type_detail=detail.id,
)

# -- 6. Ventas (607) y anulacion (608) ---------------------------------------
inv_fiscal = make_move("out_invoice", iterativo, sale_journal, docs["fiscal"], "B0100000101", itbis_sale, 50000)
pay(inv_fiscal, cash_journal, "2026-08-18")
inv_consumer = make_move("out_invoice", jose, sale_journal, docs["consumer"], "B0200000310", itbis_sale, 3000)

inv_cancel = make_move("out_invoice", iterativo, sale_journal, docs["fiscal"], "B0100000102", itbis_sale, 12000)
inv_cancel.l10n_do_cancellation_type = "05"
inv_cancel.with_user(admin).with_context(skip_cancel_wizard=True).button_cancel()

# -- 7. Declaraciones -------------------------------------------------------
Report = env["dgii.reports"]
july = Report.create({"name": "07/2026", "company_id": company.id})
july.generate_report()
july.state_sent()
august = Report.create({"name": "08/2026", "company_id": company.id})
august.generate_report()
draft = Report.create({"name": "09/2026", "company_id": company.id})


# -- 8. Acciones demo para las capturas ---------------------------------------
def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


def form_action(xmlid, name, model, res_id):
    demo_action(xmlid, {"name": name, "res_model": model, "view_mode": "form", "res_id": res_id})


def lines_action(xmlid, name, model, view_xmlid, report):
    demo_action(
        xmlid,
        {
            "name": name,
            "res_model": model,
            "view_mode": "list",
            "view_id": env.ref("dgii_reports.%s" % view_xmlid).id,
            "domain": "[('dgii_report_id', '=', %d)]" % report.id,
        },
    )


form_action("demo_account_itbis", "Cuenta de retencion ITBIS", "account.account", ret_itbis_account.id)
form_action("demo_account_isr", "Cuenta de retencion ISR", "account.account", ret_isr_account.id)
form_action("demo_partner", "ITERATIVO SRL", "res.partner", iterativo.id)
form_action("demo_bill_exterior", "Pago al exterior", "account.move", bill_exterior.id)
form_action("demo_bill_informal", "Compra informal", "account.move", bill_informal.id)
form_action("demo_invoice_fiscal", "Venta fiscal", "account.move", inv_fiscal.id)
form_action("demo_report_draft", "Declaracion 09/2026", "dgii.reports", draft.id)
form_action("demo_report_generated", "Declaracion 08/2026", "dgii.reports", august.id)
form_action("demo_report_sent", "Declaracion 07/2026", "dgii.reports", july.id)
lines_action("demo_606", "606 - 08/2026", "dgii.reports.purchase.line", "dgii_report_purchase_line_list", august)
lines_action("demo_607", "607 - 08/2026", "dgii.reports.sale.line", "dgii_report_sale_line_list", august)
lines_action("demo_608", "608 - 08/2026", "dgii.reports.cancel.line", "dgii_cancel_report_line_list", august)
lines_action("demo_609", "609 - 08/2026", "dgii.reports.exterior.line", "dgii_exterior_report_line_list", august)

env.cr.commit()

print(
    "SEED OK | 08/2026:",
    august.state,
    "606=%s 607=%s 608=%s 609=%s" % (august.purchase_records, august.sale_records, august.cancel_records, august.exterior_records),
    "| informal wh ITBIS/ISR:", bill_informal.l10n_do_withholded_itbis, bill_informal.l10n_do_income_withholding,
    "| files:", august.purchase_filename, august.sale_filename, august.cancel_filename, august.exterior_filename,
)
for label, field in (("606", "purchase_binary"), ("607", "sale_binary"), ("608", "cancel_binary"), ("609", "exterior_binary")):
    print("----", label)
    print(august[field].content.decode())
