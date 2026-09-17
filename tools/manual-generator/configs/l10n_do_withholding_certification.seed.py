# Seed del manual de l10n_do_withholding_certification (Certificacion de
# Retenciones RD). Desde una base LIMPIA arma:
#
#   * Compania "Constructora del Caribe SRL" (RD, DOP) con plan contable 'do'.
#   * Dos cuentas de retencion propias (ITBIS e ISR) marcadas como cuentas de
#     retencion, con su nombre de impuesto y su base legal -- que es lo que
#     imprime el certificado.
#   * La tabla de firmas y el lema del ano de la compania.
#   * Un suplidor persona fisica (honorarios profesionales).
#   * Las dos formas de retencion que el modulo entiende:
#       A) retencion SOBRE LA FACTURA (como se hacia hasta la v17 y como llegan
#          las bases migradas): la factura sale neta de retencion,
#       B) retencion AL REGISTRAR EL PAGO (flujo nativo v19): la factura se debe
#          completa y la retencion se captura en el pago.
#   * Una tercera factura sin pagar, para ilustrar el asistente de registro de
#     pago con sus lineas de retencion.
#   * El certificado del pago nativo ya impreso, para que el chatter lo muestre.
#
# Se ejecuta dentro de `odoo shell` (el global `env` esta disponible) y termina
# con env.cr.commit().

from odoo import Command, fields

company = env.ref("base.main_company")
do = env.ref("base.do")
admin = env.ref("base.user_admin")


def show(label, value):
    print("   %-34s %s" % (label + ":", value))


# ── 0. Espanol dominicano ────────────────────────────────────────────────────
# Las capturas van en es_DO; hay que traducir TODOS los modulos instalados, no
# solo el propio, o el resto de la interfaz sale en ingles.
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
company = company.with_env(env)
admin = admin.with_env(env)

# ── 1. Permisos del administrador ────────────────────────────────────────────
# Una base sin datos de demostracion no le da al admin los grupos de
# contabilidad ni los grupos fiscales dominicanos.
admin.group_ids |= env.ref("account.group_account_manager")
# El asistente de apariencia del certificado esta restringido a
# account.group_account_user ("Mostrar caracteristicas de contabilidad
# completas"), que no viene implicito en group_account_manager.
admin.group_ids |= env.ref("account.group_account_user")
for group in (
    "l10n_do_accounting.group_l10n_do_fiscal_credit_note",
    "l10n_do_accounting.group_l10n_do_fiscal_invoice_cancel",
    "l10n_do_accounting.group_l10n_do_debit_note",
    "l10n_do_accounting.group_l10n_do_edit_fiscal_partner",
):
    admin.group_ids |= env.ref(group)

# ── 2. Compania dominicana y plan contable 'do' ──────────────────────────────
dop = env.ref("base.DOP")
dop.active = True
company.write(
    {
        "name": "Constructora del Caribe SRL",
        "country_id": do.id,
        "state_id": env.ref("base.state_DO_01").id,
        "city": "Santo Domingo",
        "street": "Av. Winston Churchill 1099, Torre Acropolis",
        "phone": "+1 809 555 0142",
        "email": "contabilidad@constructoradelcaribe.do",
        "website": "https://www.constructoradelcaribe.do",
        "vat": "131793916",
        "l10n_do_withholding_cert_type": "private",
    }
)
company.partner_id.write({"lang": "es_DO", "l10n_do_dgii_tax_payer_type": "taxpayer"})

# Un logo propio, para que el membrete del certificado no salga con el marcador
# "Your logo" de Odoo. Se dibuja aqui para no arrastrar un binario al repo.
try:
    import base64
    import io

    from PIL import Image, ImageDraw, ImageFont

    canvas = Image.new("RGBA", (900, 260), (255, 255, 255, 0))
    draw = ImageDraw.Draw(canvas)
    font_big = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 78)
    font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    draw.rectangle((0, 40, 26, 220), fill=(0, 145, 196, 255))
    draw.text((60, 44), "CONSTRUCTORA", font=font_big, fill=(7, 55, 99, 255))
    draw.text((64, 150), "DEL CARIBE   S R L", font=font_small, fill=(0, 145, 196, 255))
    buffer = io.BytesIO()
    canvas.save(buffer, format="PNG")
    company.logo = base64.b64encode(buffer.getvalue())
except Exception as error:  # noqa: BLE001 - el manual no depende del logo
    print("AVISO: no se pudo generar el logo (%s)" % error)
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
if company.currency_id != dop:
    company.currency_id = dop
if company.account_fiscal_country_id != do:
    company.account_fiscal_country_id = do

prefix = "account.%s_" % company.id
itbis_18 = env.ref(prefix + "tax_18_purch")
ret_itbis = env.ref(prefix + "ret_100_tax_person")  # -18% == 100% del ITBIS
ret_isr = env.ref(prefix + "ret_10_income_person")  # -10% sobre el subtotal

# ── 3. Cuentas de retencion ──────────────────────────────────────────────────
# El certificado NO lee nada del impuesto: el nombre de la columna y la base
# legal salen de la CUENTA en la que el impuesto de retencion asienta. El plan
# dominicano ya trae una cuenta por tipo de retencion; aqui solo se configuran.


def withholding_account(code, tax_name, legal_base):
    account = env["account.account"].search(
        [("code", "=", code), ("company_ids", "in", company.id)], limit=1
    )
    if not account:
        raise Exception("No existe la cuenta %s en el plan de la compania" % code)
    account.write(
        {
            "is_l10n_do_withholding_account": True,
            "l10n_do_tax_name": tax_name,
            "l10n_do_legal_base": legal_base,
        }
    )
    return account


# 21030202 ITBIS Retenido a Persona Fisica (R293-11)
itbis_account = withholding_account("21030202", "ITBIS", "la Norma General 02-05 de la DGII")
# 21030301 ISR Retenido por Honorarios Profesionales de Personas Fisicas
isr_account = withholding_account("21030301", "ISR", "el Art. 309 del Código Tributario")

# El impuesto tiene que asentar en esa cuenta: el modulo lee la cuenta de la
# linea de reparto de tipo "impuesto".
for tax, account in ((ret_itbis, itbis_account), (ret_isr, isr_account)):
    tax.invoice_repartition_line_ids.filtered(lambda line: line.repartition_type == "tax").account_id = account
    tax.refund_repartition_line_ids.filtered(lambda line: line.repartition_type == "tax").account_id = account

# ── 4. Maqueta del certificado: firmas y lema del ano ────────────────────────
company.l10n_do_sign_table = """
<div class="l10n_do_sign_table">
    <br/><br/><br/><br/>
    <table width="100%" style="text-align:center;">
        <tr>
            <td width="45%">
                <strong><span>Lic. Yohanna Belliard Pimentel</span></strong><br/>
                <span>Gerente de Contabilidad</span>
            </td>
            <td width="10%"></td>
            <td width="45%">
                <strong><span>Ing. Rafael Antonio Guzmán</span></strong><br/>
                <span>Director Financiero</span>
            </td>
        </tr>
    </table>
</div>
"""
company.l10n_do_year_tag_line = """
<div class="l10n_do_year_tag_line" style="text-align:center;">
    <br/><br/>
    <span><strong>AÑO DE LA CONSOLIDACIÓN DE LA SEGURIDAD ALIMENTARIA</strong></span><br/>
    <span><strong>“AVANZANDO PARA TI”</strong></span>
</div>
"""

# ── 5. Suplidor, diario fiscal y tipo de documento ───────────────────────────
supplier = env["res.partner"].create(
    {
        "name": "Ing. Ramón Emilio Peña Ureña",
        "company_type": "person",
        "country_id": do.id,
        "state_id": env.ref("base.state_DO_01").id,
        "city": "Santo Domingo",
        "vat": "00113918205",
        "l10n_do_dgii_tax_payer_type": "non_payer",
        "supplier_rank": 1,
        "lang": "es_DO",
    }
)

purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
)
purchase_journal.l10n_latam_use_documents = True
bank_journal = env["account.journal"].search(
    [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1
)
if "l10n_do_payment_form" in bank_journal._fields:
    bank_journal.l10n_do_payment_form = "bank"

doc_type = env["l10n_latam.document.type"].search(
    [("l10n_do_ncf_type", "=", "fiscal"), ("internal_type", "=", "invoice")], limit=1
)

service = env["product.product"].create(
    {
        "name": "Honorarios por servicios profesionales de ingeniería",
        "type": "service",
        "standard_price": 25000.00,
        "supplier_taxes_id": [Command.clear()],
    }
)

today = fields.Date.context_today(admin)


def create_bill(number, price_unit, taxes, label):
    bill = env["account.move"].create(
        {
            "move_type": "in_invoice",
            "partner_id": supplier.id,
            "journal_id": purchase_journal.id,
            "invoice_date": today,
            "date": today,
            "l10n_do_expense_type": "02",
            "invoice_line_ids": [
                Command.create(
                    {
                        "product_id": service.id,
                        "name": label,
                        "quantity": 1,
                        "price_unit": price_unit,
                        "tax_ids": [Command.set(taxes.ids)],
                    }
                )
            ],
        }
    )
    bill.l10n_latam_document_type_id = doc_type.id
    bill.l10n_latam_document_number = number
    bill.action_post()
    return bill


def pay(bill):
    wizard = (
        env["account.payment.register"]
        .with_context(active_model="account.move", active_ids=bill.ids)
        .create({"journal_id": bank_journal.id})
    )
    wizard.action_create_payments()
    env.flush_all()
    return bill.matched_payment_ids[:1]


# ── 6A. Retencion SOBRE LA FACTURA (forma pre-v19 / bases migradas) ──────────
# Con "Retención en el pago" apagado, el impuesto negativo se aplica en la
# factura: su total ya sale neto de retencion y el pago no lleva lineas.
(ret_itbis + ret_isr).is_withholding_tax_on_payment = False
bill_on_invoice = create_bill(
    "B0100000015",
    18000.00,
    itbis_18 + ret_itbis + ret_isr,
    "Supervisión de obra — corte de octubre",
)
payment_on_invoice = pay(bill_on_invoice)

# ── 6B. Retencion AL REGISTRAR EL PAGO (flujo nativo v19) ────────────────────
# Con el flag encendido el impuesto queda fuera de la factura -- se debe
# completa -- y se captura al registrar el pago.
(ret_itbis + ret_isr).is_withholding_tax_on_payment = True
bill_on_payment = create_bill(
    "B0100000016",
    25000.00,
    itbis_18 + ret_itbis + ret_isr,
    "Diseño estructural — Torre Anacaona",
)
payment_on_payment = pay(bill_on_payment)

# ── 6C. Factura sin pagar, para el asistente de registro de pago ─────────────
bill_to_pay = create_bill(
    "B0100000017",
    32000.00,
    itbis_18 + ret_itbis + ret_isr,
    "Levantamiento topográfico — Proyecto Bávaro",
)

# ── 7. Imprimir el certificado del pago nativo (deja el adjunto en el chatter) ─
report = env.ref("l10n_do_withholding_certification.l10n_do_withholding_cert")
payment_on_payment._post_printing_message(report)

# ── 8. xmlids fijos: el generador abre los registros por xmlid ───────────────
env["ir.model.data"]._update_xmlids(
    [
        {"xml_id": "__manual__.cuenta_ret_isr", "record": isr_account},
        {"xml_id": "__manual__.cuenta_ret_itbis", "record": itbis_account},
        {"xml_id": "__manual__.impuesto_ret_isr", "record": ret_isr},
        {"xml_id": "__manual__.suplidor", "record": supplier},
        {"xml_id": "__manual__.factura_en_factura", "record": bill_on_invoice},
        {"xml_id": "__manual__.factura_en_pago", "record": bill_on_payment},
        {"xml_id": "__manual__.factura_por_pagar", "record": bill_to_pay},
        {"xml_id": "__manual__.pago_en_factura", "record": payment_on_invoice},
        {"xml_id": "__manual__.pago_en_pago", "record": payment_on_payment},
    ]
)

env.cr.commit()

print("SEED OK")
show("Compañía", "%s (%s, %s)" % (company.name, company.currency_id.name, company.chart_template))
show("Tipo de certificación", company.l10n_do_withholding_cert_type)
show("Cuenta ITBIS", "%s %s [%s]" % (itbis_account.code, itbis_account.name, itbis_account.l10n_do_tax_name))
show("Cuenta ISR", "%s %s [%s]" % (isr_account.code, isr_account.name, isr_account.l10n_do_tax_name))
show("Suplidor", "%s (%s)" % (supplier.name, supplier.vat))
for label, bill, payment in (
    ("Retención en la factura", bill_on_invoice, payment_on_invoice),
    ("Retención en el pago", bill_on_payment, payment_on_payment),
):
    show(label, "%s total=%s pago=%s" % (bill.name, bill.amount_total, payment.name or "-"))
    show("  líneas de retención", len(payment.withholding_line_ids))
    show("  detectado en la factura", {a.l10n_do_tax_name: v for a, v in payment._get_invoice_withholding_by_account().items()})
    payment.invalidate_recordset(["has_l10n_do_withholding"])
    show("  has_l10n_do_withholding", payment.has_l10n_do_withholding)
    data = payment.get_certification_data()
    show("  bruto / retenido / neto", "%s / %s / %s" % (
        data["payments_amount"], sum(data["withholding_values"].values()), data["paid_amount"]))
    show("  columnas", [a.l10n_do_tax_name for a in data["withholding_values"]])
    show("  en letras", data["amount_in_words"])
show("Factura por pagar", "%s total=%s" % (bill_to_pay.name, bill_to_pay.amount_total))
