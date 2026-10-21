# Seed del manual de account_invoice_discount_display_amount (Descuento total
# debajo del subtotal de la factura). Desde una base LIMPIA arma:
#
#   * Compania "Materiales del Cibao SRL" (RD, DOP, plan dominicano), emisora e-CF.
#   * Un cliente contribuyente y tres productos con ITBIS 18%.
#   * Factura e-CF (E31) con descuentos en las lineas, publicada.
#   * Factura NCF de credito fiscal (B01) con descuentos, publicada.
#   * Factura B01 sin descuento (la fila no debe salir).
#   * Factura de un diario sin comprobantes fiscales (plantilla estandar de Odoo).
#   * Factura e-CF en borrador para mostrar el calculo en vivo.
#
# Se ejecuta dentro de `odoo shell` (el global `env` esta disponible) y termina
# con env.cr.commit().

from odoo import Command, fields

company = env.ref("base.main_company")
do = env.ref("base.do")
admin = env.ref("base.user_admin")


def show(label, value):
    print("   %-34s %s" % (label + ":", value))


es = env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
company = company.with_env(env)
admin = admin.with_env(env)

admin.group_ids |= env.ref("account.group_account_manager")
admin.group_ids |= env.ref("account.group_account_user")
admin.group_ids |= env.ref("uom.group_uom")
for group in (
    "l10n_do_accounting.group_l10n_do_fiscal_credit_note",
    "l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel",
    "l10n_do_accounting.group_l10n_do_debit_note",
    "l10n_do_accounting.group_l10n_do_edit_fiscal_partner",
):
    admin.group_ids |= env.ref(group)

dop = env.ref("base.DOP")
dop.active = True
company.write(
    {
        "name": "Materiales del Cibao SRL",
        "country_id": do.id,
        "vat": "131793916",
        "street": "Av. Estrella Sadhalá 45",
        "city": "Santiago de los Caballeros",
        "phone": "809-582-0000",
        "email": "facturacion@materialesdelcibao.do",
    }
)
company.partner_id.write({"lang": "es_DO", "l10n_do_dgii_tax_payer_type": "taxpayer"})
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
if company.currency_id != dop:
    company.currency_id = dop
if company.account_fiscal_country_id != do:
    company.account_fiscal_country_id = do
company.l10n_do_ecf_issuer = True
if "l10n_do_sequence_manager" in company._fields:
    company.l10n_do_sequence_manager = False

itbis_18 = env.ref("account.%s_tax_18_sale" % company.id)

customer = env["res.partner"].create(
    {
        "name": "Constructora Los Pinos SRL",
        "company_type": "company",
        "vat": "131566332",
        "l10n_do_dgii_tax_payer_type": "taxpayer",
        "country_id": do.id,
        "city": "Santo Domingo",
        "street": "C/ Max Henríquez Ureña 12",
        "lang": "es_DO",
    }
)


def product(name, price):
    return env["product.product"].create(
        {
            "name": name,
            "type": "consu",
            "list_price": price,
            "taxes_id": [Command.set(itbis_18.ids)],
        }
    )


cemento = product("Cemento gris 42.5 kg", 375.00)
varilla = product("Varilla corrugada 3/8\" x 20'", 245.00)
alambre = product("Alambre dulce calibre 18 (libra)", 95.00)

sale_journal = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id)], limit=1
)
sale_journal.l10n_latam_use_documents = True
plain_journal = env["account.journal"].create(
    {
        "name": "Ventas sin comprobante",
        "code": "VSC",
        "type": "sale",
        "company_id": company.id,
        "l10n_latam_use_documents": False,
    }
)

doc_type = {
    "B01": env.ref("l10n_do_accounting.ncf_fiscal_client"),
    "E31": env.ref("l10n_do_accounting.ecf_fiscal_client"),
}
today = fields.Date.context_today(admin)


def create_invoice(lines, document=None, number=None, journal=sale_journal, move_type="out_invoice", post=True):
    vals = {"l10n_latam_document_type_id": doc_type[document].id} if document else {}
    move = env["account.move"].create(
        {
            **vals,
            "move_type": move_type,
            "partner_id": customer.id,
            "journal_id": journal.id,
            "invoice_date": today,
            "date": today,
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": prod.id,
                        "quantity": qty,
                        "price_unit": prod.list_price,
                        "discount": discount,
                        "tax_ids": [Command.set(itbis_18.ids)],
                    }
                )
                for prod, qty, discount in lines
            ],
        }
    )
    if document:
        move.l10n_latam_document_number = number
    if post:
        move.action_post()
    return move


ecf = create_invoice(
    [(cemento, 120, 12.0), (varilla, 40, 8.0), (alambre, 10, 0.0)], "E31", "E310000000001"
)
ncf = create_invoice([(cemento, 30, 5.0), (varilla, 100, 10.0)], "B01", "B0100000001")
no_discount = create_invoice([(cemento, 20, 0.0), (alambre, 15, 0.0)], "B01", "B0100000002")
plain = create_invoice([(varilla, 25, 15.0), (alambre, 30, 0.0)], journal=plain_journal)
draft = create_invoice([(cemento, 50, 10.0), (varilla, 20, 0.0)], "E31", "E310000000002", post=False)

env["ir.model.data"]._update_xmlids(
    [
        {"xml_id": "__manual__.invoice_ecf", "record": ecf},
        {"xml_id": "__manual__.invoice_ncf", "record": ncf},
        {"xml_id": "__manual__.invoice_no_discount", "record": no_discount},
        {"xml_id": "__manual__.invoice_plain", "record": plain},
        {"xml_id": "__manual__.invoice_draft", "record": draft},
    ]
)

for label, move in (
    ("e-CF E31", ecf),
    ("NCF B01", ncf),
    ("B01 sin descuento", no_discount),
    ("Sin comprobante", plain),
    ("Borrador e-CF", draft),
):
    show(
        label,
        "%s | %s | subtotal=%.2f desc=%.2f desc_imp=%.2f total=%.2f sin_desc=%.2f ecf=%s"
        % (
            move.name,
            move.state,
            move.amount_untaxed,
            move.untaxed_discount_total,
            move.discount_total,
            move.amount_total,
            move.price_total_no_discount,
            move.is_ecf_invoice,
        ),
    )

env.cr.commit()
print("SEED OK")
