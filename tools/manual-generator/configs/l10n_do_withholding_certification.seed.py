# Seed for the manual of l10n_do_withholding_certification.
# Builds, from a CLEAN DB, a Dominican company with:
#
#   * Chart of accounts 'do', diario de compras con documentos fiscales (NCF).
#   * Las retenciones del plan marcadas, y sus cuentas anotadas con el nombre
#     del impuesto y la base legal que exige el certificado.
#   * Una factura de proveedor de RD$800 + ITBIS 18% pagada con retencion,
#     de modo que el pago quede marcado y se pueda imprimir el certificado.
#
# Ejecutado dentro de `odoo shell` (`env` disponible). Termina con commit.

from odoo import Command

MODULE = "l10n_do_withholding_certification"

company = env.ref("base.main_company")
do = env.ref("base.do")

# -- 0. Espanol --------------------------------------------------------------
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

env["ir.module.module"].search(
    [
        ("name", "in", [MODULE, "l10n_do_account_withholding_tax",
                        "l10n_account_withholding_tax", "l10n_do_accounting", "l10n_do"]),
        ("state", "=", "installed"),
    ]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Compania RD + plan contable dominicano -------------------------------
company.write(
    {
        "name": "INDEXA SRL",
        "country_id": do.id,
        "vat": "131793916",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
        "phone": "809-472-9292",
    }
)
company.partner_id.lang = "es_DO"
env["account.chart.template"].try_loading("do", company=company, install_demo=False)

# -- 2. Tipo de certificacion ------------------------------------------------
company.write(
    {
        "l10n_do_withholding_cert_type": "private",
        "l10n_do_sign_table": """
            <div class="l10n_do_sign_table"><br/><br/>
                <div class="col-4 float-left" style="position:absolute;">
                    <strong><span>Luis Fernández</span></strong><br/>
                    <span>Gerente Financiero</span></div>
                <div class="col-4"></div>
                <div class="col-4 float-right" style="text-align:center;">
                    <strong><span>Ana Martínez</span></strong><br/>
                    <span>Contralora</span></div>
            </div>
        """,
    }
)

# -- 3. Retenciones y sus cuentas --------------------------------------------
def tax_ref(xmlid):
    return env.ref("account.%s_%s" % (company.id, xmlid), raise_if_not_found=False)


itbis18 = tax_ref("tax_18_purch")
ret_itbis = tax_ref("ret_100_tax_security")  # -18   -> 100% del ITBIS
ret_isr = tax_ref("ret_10_income_person")    # -10   -> 10% del subtotal

for tax in (ret_itbis, ret_isr):
    tax.write(
        {
            "is_withholding_tax": True,
            "tax_exigibility": "on_invoice",
            "price_include_override": "tax_excluded",
        }
    )

# Las cuentas de retencion llevan el nombre del impuesto y la base legal:
# es de ahi que el certificado saca su texto.
for tax, tax_name, legal_base in (
    (ret_itbis, "ITBIS", "la Norma General 02-05 de la DGII"),
    (ret_isr, "ISR", "el Art. 309 del Código Tributario"),
):
    account = tax.invoice_repartition_line_ids.filtered(
        lambda r: r.repartition_type == "tax" and r.account_id
    )[:1].account_id
    account.write(
        {
            "is_l10n_do_withholding_account": True,
            "l10n_do_tax_name": tax_name,
            "l10n_do_legal_base": legal_base,
        }
    )

itbis_account = ret_itbis.invoice_repartition_line_ids.filtered(
    lambda r: r.repartition_type == "tax" and r.account_id
)[:1].account_id

# -- 4. Diarios y tercero -----------------------------------------------------
purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
)
purchase_journal.write({"name": "Compras Fiscales", "l10n_latam_use_documents": True})
bank_journal = env["account.journal"].search(
    [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
)

proveedor = env["res.partner"].create(
    {
        "name": "ITERATIVO SRL",
        "vat": "131566332",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
        "country_id": do.id,
        "street": "Calle El Vergel 23",
        "city": "Santo Domingo",
    }
)

product = env["product.product"].create(
    {"name": "Servicio de consultoria", "type": "service", "lst_price": 800, "standard_price": 800}
)
doc_fiscal = env.ref("l10n_do_accounting.ncf_fiscal_client")

# -- 5. Factura de proveedor con retenciones, publicada ----------------------
bill = env["account.move"].create(
    {
        "move_type": "in_invoice",
        "partner_id": proveedor.id,
        "journal_id": purchase_journal.id,
        "invoice_date": "2026-09-01",
        "date": "2026-09-01",
        "l10n_do_expense_type": "02",
        "l10n_latam_document_type_id": doc_fiscal.id,
        "invoice_line_ids": [
            (0, 0, {
                "product_id": product.id,
                "name": "Consultoria — analisis funcional",
                "quantity": 1,
                "price_unit": 800,
                "tax_ids": [(6, 0, (itbis18 | ret_itbis | ret_isr).ids)],
            }),
        ],
    }
)
bill.l10n_latam_document_number = "B0100000001"
bill.action_post()

# -- 6. Pago con retencion ----------------------------------------------------
wizard = (
    env["account.payment.register"]
    .with_context(active_model="account.move", active_ids=bill.ids)
    .create({"journal_id": bank_journal.id})
)
wizard.action_create_payments()
pago = env["account.payment"].search(
    [("partner_id", "=", proveedor.id)], order="id desc", limit=1
)

# -- 7. Acciones demo para las capturas ---------------------------------------
def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {
            "module": MODULE,
            "name": xmlid,
            "model": "ir.actions.act_window",
            "res_id": act.id,
            "noupdate": True,
        }
    )
    return act


demo_action("demo_wh_account", {
    "name": "Cuenta de retencion ITBIS",
    "res_model": "account.account",
    "view_mode": "form",
    "res_id": itbis_account.id,
})
demo_action("demo_payment", {
    "name": "Pago con retencion",
    "res_model": "account.payment",
    "view_mode": "form",
    "res_id": pago.id,
})
demo_action("demo_payment_list", {
    "name": "Pagos con retencion",
    "res_model": "account.payment",
    "view_mode": "list,form",
    "domain": "[('has_l10n_do_withholding', '=', True)]",
})
env.cr.commit()

print(
    "SEED OK | bill:", bill.name,
    "| pago:", pago.name,
    "| flag:", pago.has_l10n_do_withholding,
    "| retenciones:", [(l.tax_id.name, l.amount) for l in pago.withholding_line_ids],
)
