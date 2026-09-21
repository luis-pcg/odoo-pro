# Seed for the manual of l10n_do_account_withholding_tax (Retencion en el pago).
# Builds, from a CLEAN DB, a Dominican company with:
#
#   * Chart of accounts 'do', diario de compras con documentos fiscales (NCF).
#   * Las retenciones del plan dominicano marcadas como "Retencion"
#     (is_withholding_tax), que el plan NO trae marcadas de fabrica.
#   * Dos facturas de proveedor identicas de RD$800 + ITBIS 18% (RD$144):
#       - una publicada y SIN pagar, para capturar el asistente de pago;
#       - una publicada y YA pagada con retencion, para capturar el asiento.
#
# Ejecutado dentro de `odoo shell` (`env` disponible). Termina con commit.

MODULE = "l10n_do_account_withholding_tax"

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
        ("name", "in", [MODULE, "l10n_account_withholding_tax", "l10n_do_accounting", "l10n_do"]),
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
    }
)
company.partner_id.lang = "es_DO"
env["account.chart.template"].try_loading("do", company=company, install_demo=False)

# -- 2. Marcar las retenciones -----------------------------------------------
# El plan dominicano trae las tasas correctas (-18 = 100% de un ITBIS 18%,
# -5.4 = 30%, -10 = ISR honorarios) pero NO marca is_withholding_tax, asi que
# el asistente de pago no las ofrece hasta que alguien las habilita.
def tax_ref(xmlid):
    return env.ref("account.%s_%s" % (company.id, xmlid), raise_if_not_found=False)


itbis18 = tax_ref("tax_18_purch")
ret_itbis_100 = tax_ref("ret_100_tax_security")   # -18   -> 100% del ITBIS
ret_itbis_30 = tax_ref("ret_30_tax_moral")        # -5.4  ->  30% del ITBIS
ret_isr_10 = tax_ref("ret_10_income_person")      # -10   ->  10% del subtotal

for tax in (ret_itbis_100, ret_itbis_30, ret_isr_10):
    tax.write(
        {
            "is_withholding_tax": True,
            "tax_exigibility": "on_invoice",
            "price_include_override": "tax_excluded",
        }
    )

# -- 3. Diario de compras fiscal ---------------------------------------------
purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
)
purchase_journal.write({"name": "Compras Fiscales", "l10n_latam_use_documents": True})

bank_journal = env["account.journal"].search(
    [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
)

# -- 4. Tercero y producto ----------------------------------------------------
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
    {
        "name": "Servicio de consultoria",
        "type": "service",
        "lst_price": 500,
        "standard_price": 500,
    }
)

doc_fiscal = env.ref("l10n_do_accounting.ncf_fiscal_client")


def make_bill(number, taxes):
    """Factura de proveedor de RD$800 (500 + 300), con ITBIS y retenciones."""
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
                    "price_unit": 500,
                    "tax_ids": [(6, 0, taxes.ids)],
                }),
                (0, 0, {
                    "product_id": product.id,
                    "name": "Consultoria — acompanamiento",
                    "quantity": 1,
                    "price_unit": 300,
                    "tax_ids": [(6, 0, taxes.ids)],
                }),
            ],
        }
    )
    bill.l10n_latam_document_number = number
    bill.action_post()
    return bill


todas = itbis18 | ret_itbis_100 | ret_isr_10

# -- 5. Factura publicada SIN pagar (para capturar el asistente) -------------
bill_pendiente = make_bill("B0100000001", todas)

# -- 6. Factura publicada Y pagada con retencion (para capturar el asiento) --
bill_pagada = make_bill("B0100000002", todas)

wizard = (
    env["account.payment.register"]
    .with_context(active_model="account.move", active_ids=bill_pagada.ids)
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


demo_action("demo_tax_itbis_ret", {
    "name": "Retencion ITBIS 100%",
    "res_model": "account.tax",
    "view_mode": "form",
    "res_id": ret_itbis_100.id,
})
demo_action("demo_tax_isr_ret", {
    "name": "Retencion ISR 10%",
    "res_model": "account.tax",
    "view_mode": "form",
    "res_id": ret_isr_10.id,
})
demo_action("demo_bill_pendiente", {
    "name": "Factura de proveedor pendiente",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": bill_pendiente.id,
})
demo_action("demo_bill_pagada", {
    "name": "Factura de proveedor pagada con retencion",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": bill_pagada.id,
})
demo_action("demo_pago", {
    "name": "Pago con retenciones",
    "res_model": "account.payment",
    "view_mode": "form",
    "res_id": pago.id,
})
demo_action("demo_asiento", {
    "name": "Apuntes del asiento del pago",
    "res_model": "account.move.line",
    "view_mode": "list",
    "domain": "[('move_id', '=', %d)]" % pago.move_id.id,
    "context": "{'search_default_group_by_move': 0}",
})
demo_action("demo_taxes_list", {
    "name": "Retenciones del plan dominicano",
    "res_model": "account.tax",
    "view_mode": "list,form",
    "domain": "[('is_withholding_tax', '=', True)]",
})

env.cr.commit()

print("SEED OK | pendiente:", bill_pendiente.name, "| pagada:", bill_pagada.name,
      "| pago:", pago.name, "| retenciones:", [(l.tax_id.name, l.base_amount, l.amount) for l in pago.withholding_line_ids])
