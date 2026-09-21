# Seed for the manual of l10n_do_ncf_validation (Validacion de NCF contra DGII).
# Builds, from a CLEAN DB, a Dominican company with:
#
#   * Chart of accounts 'do', diario de ventas y de compras con documentos
#     fiscales (NCF).
#   * ncf_validation_target = "both": se validan tanto los NCF que genera la
#     compania como los que vienen de un tercero.
#   * Dos facturas de cliente y dos facturas de proveedor, elegidas para que la
#     consulta real a la DGII devuelva un resultado conocido:
#       - B0100000001 de 131793916 (INDEXA SRL)  -> valido
#       - B0200000999 de 131793916               -> desconocido
#       - B0100000001 de 131566332 (ITERATIVO)   -> valido
#       - B0100009999 de 131566332 (ITERATIVO)   -> desconocido
#
# Las dos facturas validas quedan publicadas (la validacion corrio de verdad
# contra dgii.gov.do durante el seed); las dos desconocidas quedan en borrador
# para que el manual capture el error al intentar publicarlas.
#
# Ejecutado dentro de `odoo shell` (`env` disponible). Termina con commit.

MODULE = "l10n_do_ncf_validation"

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

# El modulo se instala antes de que exista es_DO, asi que sus traducciones no
# entran solas: hay que recargarlas una vez el idioma esta activo.
env["ir.module.module"].search(
    [
        ("name", "in", ["l10n_do_ncf_validation", "l10n_do_accounting", "l10n_do"]),
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

# -- 2. Configuracion del modulo ---------------------------------------------
company.ncf_validation_target = "both"
company.validate_ecf = False

# -- 3. Diarios fiscales ------------------------------------------------------
sale_journal = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
)
sale_journal.write({"name": "Ventas Fiscales", "l10n_latam_use_documents": True})

purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
)
purchase_journal.write({"name": "Compras Fiscales", "l10n_latam_use_documents": True})

# -- 4. Terceros --------------------------------------------------------------
Partner = env["res.partner"]
iterativo = Partner.create(
    {
        "name": "ITERATIVO SRL",
        "vat": "131566332",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
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
# -- 5. Producto --------------------------------------------------------------
product = env["product.product"].create(
    {
        "name": "Servicio de consultoria",
        "type": "service",
        "lst_price": 10000,
        "standard_price": 6000,
    }
)

sale_tax = company.account_sale_tax_id
purchase_tax = company.account_purchase_tax_id

doc_fiscal = env.ref("l10n_do_accounting.ncf_fiscal_client")
doc_consumer = env.ref("l10n_do_accounting.ncf_consumer_supplier")


def make_move(move_type, partner, journal, doc_type, number, tax, price=10000):
    vals_extra = {}
    if move_type in ("in_invoice", "in_refund"):
        # Requerido en el formulario de factura de proveedor (reporte 606).
        vals_extra["l10n_do_expense_type"] = "02"
    move = env["account.move"].create(
        {
            "move_type": move_type,
            "partner_id": partner.id,
            "journal_id": journal.id,
            "invoice_date": "2026-09-01",
            "l10n_latam_document_type_id": doc_type.id,
            "invoice_line_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "name": product.name,
                        "quantity": 1,
                        "price_unit": price,
                        "tax_ids": [(6, 0, tax.ids)],
                    },
                )
            ],
            **vals_extra,
        }
    )
    move.l10n_latam_document_number = number
    return move


# -- 6. Facturas de cliente (NCF interno, generado por la compania) -----------
# B0100000001 emitido por 131793916: la DGII lo reconoce -> se publica.
inv_ok = make_move(
    "out_invoice", iterativo, sale_journal, doc_fiscal, "B0100000001", sale_tax
)
inv_ok.action_post()

# B0200000999 emitido por 131793916: la DGII no lo conoce -> queda en borrador
# para que el manual capture el bloqueo al publicar.
inv_ko = make_move(
    "out_invoice", jose, sale_journal, doc_consumer, "B0200000999", sale_tax, price=4500
)

# -- 7. Facturas de proveedor (NCF externo, emitido por un tercero) -----------
# B0100000001 emitido por ITERATIVO SRL (131566332): la DGII lo reconoce.
bill_ok = make_move(
    "in_invoice", iterativo, purchase_journal, doc_fiscal, "B0100000001", purchase_tax,
    price=7500,
)
bill_ok.action_post()

# B0100009999 atribuido al mismo proveedor: la DGII no lo conoce -> queda en
# borrador. Es el caso real que este modulo persigue: un NCF inventado en una
# factura de compra.
bill_ko = make_move(
    "in_invoice", iterativo, purchase_journal, doc_fiscal, "B0100009999", purchase_tax,
    price=3200,
)


# -- 8. Acciones demo para las capturas ---------------------------------------
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


demo_action("demo_invoice_ok", {
    "name": "Factura validada",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": inv_ok.id,
})
demo_action("demo_invoice_ko", {
    "name": "Factura con NCF desconocido",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": inv_ko.id,
})
demo_action("demo_bill_ok", {
    "name": "Factura de proveedor validada",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": bill_ok.id,
})
demo_action("demo_bill_ko", {
    "name": "Factura de proveedor con NCF desconocido",
    "res_model": "account.move",
    "view_mode": "form",
    "res_id": bill_ko.id,
})
demo_action("demo_invoice_list", {
    "name": "Facturas fiscales",
    "res_model": "account.move",
    "view_mode": "list,form",
    "domain": "[('move_type', 'in', ('out_invoice', 'in_invoice'))]",
})

env.cr.commit()
print(
    "SEED OK: objetivo=%s, publicadas=%s, borradores=%s"
    % (
        company.ncf_validation_target,
        env["account.move"].search_count([("state", "=", "posted"), ("move_type", "!=", "entry")]),
        env["account.move"].search_count([("state", "=", "draft"), ("move_type", "!=", "entry")]),
    )
)
