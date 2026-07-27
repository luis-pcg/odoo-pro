# Carga una factura cuyo e-CF YA fue aceptado por DGII, sin reenviarlo.
# Ejecutar con: odoo shell -c /etc/odoo/odoo.conf -d <DB>

# ----------------------------- EDITAR -----------------------------
COMPANY_ID = 1
PARTNER_VAT = "131234567"          # RNC del cliente tal como aparece en el e-CF
NCF = "E310000001609"
INVOICE_DATE = "2026-07-15"        # FechaEmision del e-CF reportado
BASE = 9508.18                     # monto facturado (base gravada)
ITBIS = 1711.54                    # ITBIS exacto reportado a DGII
DESCRIPTION = "Servicios facturados - carga de e-CF reportado en DGII"

# Opcional: si tienes la representacion impresa / XML original, ponlos aqui
# para que el sello (QR) del PDF de Odoo apunte al e-CF real en DGII.
ECF_SECURITY_CODE = ""             # 6 caracteres, ej. "aB3xY9"
ECF_SIGN_DATE = ""                 # "2026-07-15 10:32:00" (UTC)
ECF_TRACKID = ""
# ------------------------------------------------------------------

company = env["res.company"].browse(COMPANY_ID)
env = env(context=dict(env.context, allowed_company_ids=[company.id]))  # fija env.company

partner = env["res.partner"].search([("vat", "=", PARTNER_VAT)], limit=1)
assert partner, "Cliente no encontrado por RNC %s" % PARTNER_VAT
assert partner.l10n_do_dgii_tax_payer_type, "El cliente requiere tipo de contribuyente"

journal = env["account.journal"].search(
    [("type", "=", "sale"), ("company_id", "=", company.id), ("l10n_latam_use_documents", "=", True)],
    limit=1,
)
assert journal, "No hay diario de venta con documentos fiscales"

doc_type = env["l10n_latam.document.type"].search(
    [("doc_code_prefix", "=", "E31"), ("country_id.code", "=", "DO")], limit=1
)
assert doc_type, "Tipo de documento E31 no encontrado"

tax = env["account.tax"].search(
    [
        ("company_id", "=", company.id),
        ("type_tax_use", "=", "sale"),
        ("amount", "=", 18.0),
        ("amount_type", "=", "percent"),
    ],
    limit=1,
)
assert tax, "ITBIS 18% de venta no encontrado"

# Guarda: el NCF no debe existir ya
dup = env["account.move"].search([("name", "=", NCF), ("company_id", "=", company.id)])
assert not dup, "El NCF %s ya existe en el movimiento %s" % (NCF, dup.ids)

move = env["account.move"].create(
    {
        "move_type": "out_invoice",
        "journal_id": journal.id,
        "partner_id": partner.id,
        "invoice_date": INVOICE_DATE,
        "date": INVOICE_DATE,
        "l10n_latam_document_type_id": doc_type.id,
        "name": NCF,  # se respeta: _compute_name no sobreescribe un name ya puesto
        "invoice_line_ids": [
            (0, 0, {"name": DESCRIPTION, "quantity": 1.0, "price_unit": BASE, "tax_ids": [(6, 0, tax.ids)]})
        ],
    }
)

# Ajuste fino del ITBIS: el 18% calculado puede diferir en centavos del valor
# reportado a DGII. El e-CF ya emitido es la fuente de verdad, asi que se cuadra
# la linea de impuesto contra la de cobro.
diff = round(ITBIS - move.amount_tax, 2)
if diff:
    tax_line = move.line_ids.filtered("tax_line_id")[:1]
    term_line = move.line_ids.filtered(lambda line: line.display_type == "payment_term")[:1]
    assert tax_line and term_line, "No se pudo ubicar la linea de impuesto / cobro"
    tax_line.with_context(check_move_validity=False).write(
        {"amount_currency": tax_line.amount_currency - diff, "balance": tax_line.balance - diff}
    )
    term_line.with_context(check_move_validity=False).write(
        {"amount_currency": term_line.amount_currency + diff, "balance": term_line.balance + diff}
    )
    print("ITBIS ajustado en %s" % diff)

# Post sin firmar ni enviar. Se llama _post directamente (no action_post) para
# saltar tambien la validacion contra el WebService de l10n_do_ncf_validation.
move.with_context(l10n_do_active_test=True)._post(soft=False)
assert move.name == NCF, "Odoo cambio el NCF a %s" % move.name

# Estado terminal: evita que _compute_payment_state firme y envie el e-CF
# cuando la factura se cobre (l10n_do_ecf_invoicing/models/account_move.py:1472).
vals = {"l10n_do_ecf_send_state": "delivered_accepted"}
if ECF_SECURITY_CODE:
    vals["l10n_do_ecf_security_code"] = ECF_SECURITY_CODE
if ECF_SIGN_DATE:
    vals["l10n_do_ecf_sign_date"] = ECF_SIGN_DATE
if ECF_TRACKID:
    vals["l10n_do_ecf_trackid"] = ECF_TRACKID
move.write(vals)
move.message_post(
    body="e-CF %s cargado manualmente. Ya estaba reportado y aceptado en DGII; "
    "no se envio de nuevo desde Odoo." % NCF
)

env.cr.commit()
print(
    "OK id=%s name=%s total=%s itbis=%s estado_ecf=%s edi_file=%s"
    % (move.id, move.name, move.amount_total, move.amount_tax, move.l10n_do_ecf_send_state, bool(move.l10n_do_ecf_edi_file))
)
