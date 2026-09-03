#!/usr/bin/env python3
"""
Setup + simulación end-to-end de `l10n_do_ecf_purchase_reception` en Odoo 19.

Crea una DB dominicana y ejecuta el flujo completo del módulo con la API de
Fixcal **simulada** (se reemplazan los métodos de `ReceptionService`, no hay
salida a red), usando los mismos XML de prueba que los unit tests
(`l10n_do_ecf_purchase_reception/tests/fixtures.py`) para que lo que se ve aquí
y lo que verifican los tests sean el mismo documento.

Escenarios que deja montados y verifica en pantalla:

    UC-1  Proveedor nuevo, 3 líneas sin vínculo -> wizard -> alias aprendidos
    UC-2  Segunda factura del mismo proveedor    -> entra en `ready`, 0 clics
    UC-3  Ítem nuevo en proveedor conocido       -> se crea producto desde wizard
    UC-5  Factura ya digitada a mano             -> `duplicate` + vincular
    UC-6  OC + recepción + factura de proveedor  -> picking `done` + `in_invoice`
    UC-7  Factura en USD                         -> tasa fija 1/TipoCambio
    ---   Retenciones detectadas (se avisan, no se calculan)
    ---   Descuadre de totales -> `error`, no se factura
    ---   Aprobación y rechazo comercial (ACECF 1 / 2 + código)

Uso:
    python3 setup_v19_l10n_do_ecf_purchase_reception.py --reset          # simulación completa
    python3 setup_v19_l10n_do_ecf_purchase_reception.py --reset --inbox  # DB para probar a mano

Los dos modos:

* **por defecto** — corre el flujo completo con la API **simulada** y verifica cada
  paso en pantalla. No queda nada que clicar: todo termina en `done`.
* **`--inbox`** — DB para **pruebas funcionales en el navegador**. Sin simulación:
  la compañía se siembra con el RNC `131566332`, que es un comprador que existe en
  el sandbox de Fixcal, así que el cron importa **6 documentos reales** y los
  botones (Descargar XML, Aprobar, Rechazar) llaman a la API de verdad. Los
  documentos quedan **sin procesar**, cada uno en un estado distinto.

Requisitos:
    - Contenedor Odoo v19 corriendo (lfernandez_v19).
    - Para `--inbox`: la DB tiene que estar permitida en `dbfilter` (conf/odoo.conf)
      y el contenedor reiniciado, o el navegador no la ofrece. El modo por defecto
      no necesita HTTP.

A diferencia de la versión 17 de este script, aquí el módulo se instala de un
tiro sobre una DB vacía: las dos trampas del entorno v17 -- el `_auto_init` de
`l10n_do_accounting` prefetcheando columnas que aún no existían, y el
`auto_install` de `l10n_do_sign_to_xml` que no se podía importar -- ya no se
reproducen, así que no hay módulo puente ni `ALTER TABLE` previo ni
`--skip-auto-install`.

Para el manual funcional (portada, capturas y PDF) el camino es otro:
`tools/manual-generator/generate-manual.sh --module=l10n_do_ecf_purchase_reception`,
que construye su propia DB y siembra el escenario del manual.
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v19"
DB_NAME = "v19_l10n_do_ecf_purchase_reception"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
MODULES = "l10n_do_ecf_purchase_reception"


SIMULATION = r'''
env = env  # noqa: odoo shell provides env

from odoo import fields
from odoo.addons.l10n_do_ecf_purchase_reception.lib import reception_service as svc
from odoo.addons.l10n_do_ecf_purchase_reception.tests import fixtures

DO = env.ref("base.do")
STEP = [0]


def title(text):
    STEP[0] += 1
    print("\n" + "=" * 78)
    print("  %d. %s" % (STEP[0], text))
    print("=" * 78)


def show(label, value):
    print("   %-34s %s" % (label + ":", value))


# =============================================================================
# 1. Compañía dominicana emisora de e-CF, con diario de compras fiscal
# =============================================================================
title("Compañía, plan contable e impuestos")

company = env.ref("base.main_company")
company.write({
    "name": "INDEXA SRL",
    "country_id": DO.id,
    "vat": "131793916",
    "street": "Av. Winston Churchill 1099",
    "city": "Santo Domingo",
})
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
    env.cr.commit()

company.l10n_do_ecf_issuer = True
company.l10n_do_dgii_start_date = fields.Date.to_date("2020-01-01")

purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1)
if not purchase_journal.l10n_latam_use_documents:
    purchase_journal.l10n_latam_use_documents = True
else:
    purchase_journal._l10n_do_create_document_types()

company.write({
    "l10n_do_ecf_reception_enabled": True,
    "l10n_do_ecf_api_version": "v3",
    "l10n_do_ecf_service_env": "TesteCF",
    "l10n_do_ecf_reception_lookback_days": 0,
    "l10n_do_ecf_acecf_deadline_days": 30,
    "l10n_do_ecf_purchase_journal_id": purchase_journal.id,
})
env.cr.commit()

show("Compañía / RNC", "%s / %s" % (company.name, company.vat))
show("Plan contable", company.chart_template)
show("Diario de compras fiscal", purchase_journal.display_name)
show("ITBIS 18% compras", env.ref("account.%s_tax_18_purch" % company.id).display_name)

# Productos que YA existen en la base: el operario los elegirá en el wizard.
Product = env["product.product"]
product_meat = Product.search([("default_code", "=", "CARNE-2LB")], limit=1) or Product.create({
    "name": "Carne de res paquete 2lb",
    "default_code": "CARNE-2LB",
    "type": "consu",
    "purchase_ok": True,
})
product_cable = Product.search([("default_code", "=", "UTP6")], limit=1) or Product.create({
    "name": "Cable UTP categoría 6",
    # Referencia interna IGUAL al código del ítem del XML: este se vincula solo,
    # sin alias previo (tercer nivel de búsqueda).
    "default_code": "UTP6",
    "type": "consu",
    "purchase_ok": True,
})
show("Productos existentes", "%s / %s" % (product_meat.default_code, product_cable.default_code))


# =============================================================================
# 2. API simulada
# =============================================================================
title("API de recepción simulada (sin red)")

CALLS = {"acecf": []}
FEED = {"payloads": []}


def fetch_received_invoices(self, start_date, end_date, buyer_rnc=None):
    return svc.ReceptionResult(True, list(FEED["payloads"]))


def fetch_invoices_count(self, start_date, end_date, buyer_rnc=None):
    return svc.ReceptionSummary(total_invoices=len(FEED["payloads"]), total_amount=0.0)


def fetch_ecf_xml(self, encf, issuer_rnc):
    content = fixtures.XML_BY_ENCF.get(encf)
    if content is None:
        return svc.ReceptionResult(False, error="XML no disponible para %s" % encf)
    return svc.ReceptionResult(True, content.encode())


def submit_acecf(self, payload, submit_to_dgii=True):
    CALLS["acecf"].append(payload)
    return svc.ReceptionResult(True, {"status": "accepted"})


def fetch_taxpayer(self, rnc):
    return svc.ReceptionResult(True, {"name": "DOCUMENTOS ELECTRONICOS DE 02"})


def fetch_commercial_approval(self, encf):
    return svc.ReceptionResult(True, {"approval_status": "pending"})


svc.ReceptionService.fetch_received_invoices = fetch_received_invoices
svc.ReceptionService.fetch_invoices_count = fetch_invoices_count
svc.ReceptionService.fetch_ecf_xml = fetch_ecf_xml
svc.ReceptionService.submit_acecf = submit_acecf
svc.ReceptionService.fetch_taxpayer = fetch_taxpayer
svc.ReceptionService.fetch_commercial_approval = fetch_commercial_approval

Document = env["l10n_do.ecf.received.document"]
ProductMap = env["l10n_do.ecf.product.map"]

service = company._l10n_do_get_reception_service()
show("Base URL resuelta", service.base_url)
show("Headers", {k: (v[:8] + "..." if k == "x-api-key" else v)
                 for k, v in service._reception_headers().items()})
show("Formato de fecha del rango", service._format_header_date(fields.Date.today()))


def run_cron(*specs):
    """specs: (encf, total) -> corre el cron con esos documentos en el feed."""
    FEED["payloads"] = [fixtures.api_payload(encf, total) for encf, total in specs]
    Document._cron_fetch_received_documents()
    env.cr.commit()
    return Document.search([("encf", "in", [encf for encf, _t in specs])])


def dump_lines(document):
    print("   %-3s %-10s %-28s %8s %10s %-26s %-12s %s"
          % ("#", "código", "ítem del XML", "cant", "precio", "producto Odoo", "origen", "estado"))
    for line in document.line_ids:
        print("   %-3s %-10s %-28s %8.2f %10.2f %-26s %-12s %s" % (
            line.line_number,
            line.item_code or "-",
            (line.item_name or "")[:28],
            line.quantity,
            line.price_unit,
            (line.product_id.display_name or "")[:26] if line.product_id else "-- SIN VINCULAR --",
            line.match_source or "-",
            line.state,
        ))


# =============================================================================
# 3. UC-1: proveedor nuevo, ninguna línea vinculada
# =============================================================================
title("UC-1: primera factura de un proveedor nuevo (cron)")

doc1 = run_cron(("E310000000034", "3034.00"))
show("Documento", doc1.display_name)
show("Proveedor creado por el cron", "%s (RNC %s, tipo %s)" % (
    doc1.partner_id.name, doc1.partner_id.vat, doc1.partner_id.l10n_do_dgii_tax_payer_type))
show("Tipo fiscal Odoo", doc1.l10n_latam_document_type_id.display_name)
show("Fecha emisión / recepción", "%s / %s" % (doc1.date_issued, doc1.date_received))
show("Total API / XML / calculado", "%s / %s / %s" % (
    doc1.amount_total_api, doc1.amount_total_xml, doc1.amount_total_computed))
show("Descuadre", doc1.amount_check_diff)
show("Código de seguridad", doc1.security_code)
show("Orden de compra en el XML", doc1.po_number_xml)
show("XML adjunto", doc1.xml_attachment_id.name)
show("Estado", "%s (%s líneas por vincular)" % (doc1.state, doc1.pending_line_count))
print()
dump_lines(doc1)
print("\n   Nota: la línea 3 se vinculó sola por referencia interna (UTP6),")
print("   sin alias previo. Las otras dos van al wizard.")


# =============================================================================
# 4. Wizard de vinculación: vincular, crear producto, aprender
# =============================================================================
title("UC-1/UC-3: wizard de vinculación (vincular + crear producto)")

wizard = env["l10n_do.ecf.product.mapping.wizard"].create({"document_id": doc1.id})
show("Resumen del wizard", wizard.summary)

for wline in wizard.line_ids:
    if wline.line_number == 1:
        wline.product_id = product_meat            # vincular producto existente
        wline.action = "link"
    elif wline.line_number == 2:
        wline.action = "create"                    # crear producto nuevo
        wline.new_product_name = wline.item_name
wizard.remember = True
wizard.action_apply()
env.cr.commit()

show("Estado tras aplicar", "%s (%s pendientes)" % (doc1.state, doc1.pending_line_count))
created = doc1.line_ids.filtered(lambda line: line.line_number == 2).product_id
show("Producto creado desde el XML", "%s [%s] tipo=%s precio=%s" % (
    created.display_name, created.default_code, created.type, created.standard_price))
print()
dump_lines(doc1)

print("\n   Vínculos aprendidos para este proveedor (un producto, N formas de nombrarlo):")
for link in ProductMap.search([("partner_id", "=", doc1.partner_id.id)]):
    wordings = ", ".join(
        "%s%s" % ("[%s] " % item.item_code if item.item_code else "", item.item_name)
        for item in link.item_ids
    )
    print("     %-30s <- %s" % (link.product_id.display_name[:30], wordings[:70]))


# =============================================================================
# 5. UC-6: OC -> confirmar -> recibir -> factura de proveedor
# =============================================================================
title("UC-6: crear OC + recepción + factura de proveedor")

doc1.action_create_po_receive_invoice()
env.cr.commit()

order = doc1.purchase_order_id
move = doc1.move_id
show("Orden de compra", "%s (estado %s, ref proveedor %s)" % (order.name, order.state, order.partner_ref))
show("Transferencias", ", ".join("%s=%s" % (p.name, p.state) for p in order.picking_ids))
show("Factura", "%s (estado %s, tipo %s)" % (
    move.name, move.state, move.move_type))
show("NCF fiscal en la factura", move.name)
show("Tipo de documento", move.l10n_latam_document_type_id.display_name)
show("Código seguridad / firma", "%s / %s" % (move.l10n_do_ecf_security_code, move.l10n_do_ecf_sign_date))
show("Base / ITBIS / Total", "%s / %s / %s" % (move.amount_untaxed, move.amount_tax, move.amount_total))
show("XML adjunto a la factura", move.l10n_do_ecf_edi_file_name)
show("Estado del documento", doc1.state)

print("\n   Líneas de la OC (lo que ve el widget en compras):")
print("   %-26s %-28s %-10s %s" % ("producto", "ítem del proveedor (e-CF)", "código", "estado del vínculo"))
for line in order.order_line:
    print("   %-26s %-28s %-10s %s" % (
        line.product_id.display_name[:26],
        (line.l10n_do_ecf_item_name or "-")[:28],
        line.l10n_do_ecf_item_code or "-",
        line.l10n_do_ecf_map_state))

print("\n   Trazabilidad hasta el apunte contable:")
for line in move.invoice_line_ids:
    print("     %-26s <- línea %s del e-CF   impuestos: %s" % (
        line.product_id.display_name[:26] if line.product_id else "(sin producto)",
        line.l10n_do_ecf_document_line_id.line_number or "-",
        ", ".join(line.tax_ids.mapped("name")) or "-"))


# =============================================================================
# 6. UC-2: segunda factura del mismo proveedor -> cero clics
# =============================================================================
title("UC-2: segunda factura del mismo proveedor (alias aprendido)")

doc2 = run_cron(("E310000000035", "118.00"))
show("Documento", doc2.display_name)
show("Estado", "%s (%s pendientes)" % (doc2.state, doc2.pending_line_count))
print()
dump_lines(doc2)
print('\n   El proveedor escribió "CARNES  PAQ 2LB" y el alias aprendido era')
print('   "Carnes paq 2lb": el nombre normalizado coincide -> 0 clics.')

doc2.action_create_invoice()
env.cr.commit()
show("Factura creada", "%s total %s" % (
    doc2.move_id.name, doc2.move_id.amount_total))
show("Veces usado el alias", doc2.line_ids.map_id.hit_count)


# =============================================================================
# 7. UC-7: factura en USD
# =============================================================================
title("UC-7: factura en moneda extranjera (USD)")

doc3 = run_cron(("E310000000099", "7139.00"))
show("Moneda", doc3.currency_id.name)
show("TipoCambio del XML", doc3.exchange_rate_xml)
show("Tasa fija de la factura (1/TC)", doc3.currency_rate)
show("Total XML (OtraMoneda)", doc3.amount_total_xml)
show("Estado", "%s (%s pendientes)" % (doc3.state, doc3.pending_line_count))

wizard3 = env["l10n_do.ecf.product.mapping.wizard"].create({"document_id": doc3.id})
for wline in wizard3.line_ids:
    wline.action = "create"
    wline.new_product_name = wline.item_name
wizard3.action_apply()
doc3.action_approve_commercially()
doc3.action_create_invoice()
env.cr.commit()

show("Aprobación comercial", "%s (ACECF enviado: %s)" % (doc3.approval_state, doc3.acecf_sent))
show("Factura USD", "%s moneda=%s total=%s tasa=%s" % (
    doc3.move_id.name, doc3.move_id.currency_id.name,
    doc3.move_id.amount_total, doc3.move_id.invoice_currency_rate))
show("Payload ACECF enviado", CALLS["acecf"][-1])


# =============================================================================
# 8. Retenciones: se detectan y se avisan
# =============================================================================
title("Retenciones: detectadas y avisadas, no calculadas")

doc4 = run_cron(("E310000000101", "1180.00"))
show("Tiene retenciones", doc4.has_withholding)
show("ITBIS / ISR retenidos", "%s / %s" % (doc4.amount_itbis_withheld, doc4.amount_isr_withheld))
show("Aviso en el chatter", "sí" if "withholding" in "".join(doc4.message_ids.mapped("body")) else "NO")
show("Estado", doc4.state)


# =============================================================================
# 9. Descuadre de totales: no se factura a ciegas
# =============================================================================
title("Descuadre de totales -> estado error")

doc5 = run_cron(("E310000000500", "1180.00"))
show("Total XML / calculado", "%s / %s" % (doc5.amount_total_xml, doc5.amount_total_computed))
show("Descuadre", doc5.amount_check_diff)
show("Estado", doc5.state)
show("Detalle", (doc5.error_message or "").strip()[:150])

try:
    doc5.action_create_invoice()
    show("Intento de facturar", "PERMITIDO (mal)")
except Exception as error:
    show("Intento de facturar", "bloqueado: %s" % str(error)[:90])


# =============================================================================
# 10. Rechazo comercial (ACECF 2 + código)
# =============================================================================
title("Rechazo comercial (ACECF 2)")

reject = env["l10n_do.ecf.reject.wizard"].create({
    "document_id": doc5.id,
    "rejection_code": "1",
    "rejection_reason": "Mercancía no recibida",
})
reject.action_reject()
env.cr.commit()

show("Estado", doc5.state)
show("Aprobación", "%s código %s (%s)" % (
    doc5.approval_state, doc5.rejection_code, doc5.rejection_reason))
payload = CALLS["acecf"][-1]
show("approval_status enviado", payload["approval_status"])
show("rejection_code enviado", payload["rejection_code"])
print("\n   Es rechazo comercial, NO anulación: el receptor no puede anular el")
print("   comprobante del emisor (ANECF es del emisor).")


# =============================================================================
# 11. UC-5: factura ya digitada a mano -> duplicate + vincular
# =============================================================================
title("UC-5: e-CF que ya estaba digitada a mano")

vendor = doc1.partner_id
manual = env["account.move"].create({
    "move_type": "in_refund",
    "company_id": company.id,
    "journal_id": purchase_journal.id,
    "partner_id": vendor.id,
    "invoice_date": "2020-04-10",
    "invoice_line_ids": [(0, 0, {
        "product_id": product_meat.id, "quantity": 1, "price_unit": 100,
    })],
})
# El tipo de documento se resuelve por su tipo de NCF, no por xmlid: desde la 19
# el NCF *es* el nombre del asiento, y `l10n_latam_document_number` lo escribe a
# través de su inverse.
credit_note_type = env["l10n_latam.document.type"].search(
    [("l10n_do_ncf_type", "=", "e-credit_note"), ("country_id", "=", DO.id)], limit=1)
manual.write({
    "l10n_latam_document_type_id": credit_note_type.id,
    "l10n_latam_document_number": "E340000000007",
})
env.cr.commit()
show("Nota de crédito digitada a mano", "NCF %s (borrador)" % manual.name)

doc6 = run_cron(("E340000000007", "118.00"))
show("Estado del documento importado", doc6.state)
show("Enlaza con", doc6.duplicate_move_id.display_name)
show("Aviso", "".join(doc6.message_ids.mapped("body"))[:120].replace("<p>", "").strip())

doc6.action_link_existing_move()
env.cr.commit()
show("Tras vincular: estado", doc6.state)
show("La factura manual ganó", "código %s, XML %s" % (
    manual.l10n_do_ecf_security_code, manual.l10n_do_ecf_edi_file_name))


# =============================================================================
# 12. Resumen
# =============================================================================
title("Resumen de la bandeja de recepción")

print("   %-16s %-11s %-9s %-12s %-16s %s"
      % ("e-NCF", "estado", "aprob.", "total", "factura", "OC"))
for document in Document.search([], order="encf"):
    print("   %-16s %-11s %-9s %12.2f %-16s %s" % (
        document.encf,
        document.state,
        document.approval_state,
        document.amount_total_xml,
        document.move_id.name or "-",
        document.purchase_order_id.name or "-",
    ))

print("\n   Vínculos aprendidos (memoria del sistema):")
print("   %-30s %-44s %s" % ("producto", "formas de nombrarlo", "usos"))
for link in ProductMap.search([]):
    wordings = ", ".join(
        "%s%s" % ("[%s] " % item.item_code if item.item_code else "", item.item_name)
        for item in link.item_ids
    )
    print("   %-30s %-44s %s" % (
        link.product_id.display_name[:30], wordings[:44], link.hit_count))

env.cr.commit()
print("\n[ok] simulación completa")
'''


INBOX_SEED = r'''
env = env  # noqa: odoo shell provides env

from odoo import fields

DO = env.ref("base.do")

# RNC comprador que EXISTE en el sandbox de Fixcal: con este RNC la API devuelve
# 6 documentos recibidos reales, así que los botones del módulo (Descargar XML,
# Aprobar, Rechazar, Refrescar) funcionan de verdad contra el sandbox y no hay
# nada simulado en esta DB.
BUYER_RNC = "131566332"
VENDOR_RNC = "131880681"


def title(text):
    print("\n" + "=" * 78)
    print("  " + text)
    print("=" * 78)


def show(label, value):
    print("   %-32s %s" % (label + ":", value))


# =============================================================================
title("Compañía dominicana emisora de e-CF")
# =============================================================================
company = env.ref("base.main_company")
company.write({
    "name": "ITERATIVO SRL",
    "country_id": DO.id,
    "vat": BUYER_RNC,
    "street": "Av. 27 de Febrero 1762",
    "city": "Santo Domingo",
})
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
    env.cr.commit()

company.l10n_do_ecf_issuer = True
company.l10n_do_dgii_start_date = fields.Date.to_date("2020-01-01")

purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1)
if not purchase_journal.l10n_latam_use_documents:
    purchase_journal.l10n_latam_use_documents = True
else:
    purchase_journal._l10n_do_create_document_types()

company.write({
    "l10n_do_ecf_reception_enabled": True,
    "l10n_do_ecf_api_version": "v3",
    "l10n_do_ecf_service_env": "TesteCF",
    # Los documentos del sandbox se recibieron el 21-07-2026: la ventana tiene
    # que alcanzar esa fecha desde hoy.
    "l10n_do_ecf_reception_lookback_days": 120,
    "l10n_do_ecf_reception_xml_limit": 50,
    "l10n_do_ecf_acecf_deadline_days": 30,
    "l10n_do_ecf_purchase_journal_id": purchase_journal.id,
})

admin = env.ref("base.user_admin")
admin.group_ids |= (
    env.ref("purchase.group_purchase_manager")
    | env.ref("account.group_account_manager")
    | env.ref("stock.group_stock_user")
    | env.ref("base.group_no_one")
)
admin.password = "admin"

# Español dominicano: la interfaz del módulo tiene su es_DO.po y es como se ve en
# una instancia real del cliente, así que las capturas del manual salen en el
# idioma que el operario usa, no en el inglés de las cadenas fuente.
env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin.lang = "es_DO"
env.cr.commit()

# Y el sembrado en sí corre en es_DO: los mensajes del chatter y los cambios de
# estado se escriben AHORA, en el idioma de este shell.
env = env(context=dict(env.context, lang="es_DO"))

show("Idioma de la interfaz", admin.lang)
show("Compañía / RNC", "%s / %s" % (company.name, company.vat))
show("Diario de compras", purchase_journal.display_name)
show("Entorno e-CF", "%s (API %s)" % (company.l10n_do_ecf_service_env, company.l10n_do_ecf_api_version))
show("Usuario / clave", "admin / admin")

# =============================================================================
title("Productos y proveedor")
# =============================================================================
Product = env["product.product"]


def product(name, code, kind="consu"):
    existing = Product.search([("default_code", "=", code)], limit=1)
    if existing:
        return existing
    vals = {"name": name, "default_code": code, "type": kind, "purchase_ok": True}
    if kind == "service":
        # Un servicio facturado "por cantidades recibidas" nunca es facturable.
        vals["purchase_method"] = "purchase"
    return Product.create(vals)


p_leche = product("Leche entera 1L", "LECHE-1L")
p_galletas = product("Galletas surtidas", "GALLETAS-SUR")
p_lapices = product("Lápices HB caja", "LAPICES-HB")
p_gouda = product("Queso Gouda importado", "QUESO-GOUDA")
p_pan = product("Pan de agua", "PAN-AGUA")
p_publicidad = product("Servicio de publicidad", "PUBLICIDAD", kind="service")

vendor = env["res.partner"].search([("vat", "=", VENDOR_RNC)], limit=1)
if not vendor:
    vendor = env["res.partner"].create({
        "name": "DOCUMENTOS ELECTRONICOS DE 02",
        "vat": VENDOR_RNC,
        "company_type": "company",
        "supplier_rank": 1,
        "country_id": DO.id,
        "l10n_do_dgii_tax_payer_type": "taxpayer",
    })
show("Proveedor emisor", "%s (%s)" % (vendor.name, vendor.vat))
show("Productos", ", ".join(Product.browse([p_leche.id, p_galletas.id, p_lapices.id,
                                            p_gouda.id, p_pan.id, p_publicidad.id]).mapped("default_code")))

# Alias PRE-APRENDIDOS: así parte de las líneas entran ya vinculadas y se ve el
# efecto del aprendizaje desde la primera pantalla, sin tocar el wizard.
ProductMap = env["l10n_do.ecf.product.map"]
ProductMap._learn(vendor, "", "LECHE", p_leche, company=company)
ProductMap._learn(vendor, "", "GALLETAS", p_galletas, company=company)
# Segunda forma de nombrar la leche: un producto admite N etiquetas, y sin esto la
# memoria se vería con una sola por vínculo y el caso no se aprecia en pantalla.
ProductMap._learn(vendor, "", "LECHE ENTERA 1LT", p_leche, company=company)
# Código + nombre: el proveedor manda el MISMO código 1521 en las 6 líneas de
# E310000000008, así que el código solo no identifica nada.
ProductMap._learn(vendor, "1521", "Gouda Import", p_gouda, company=company)
env.cr.commit()
show("Alias pre-aprendidos", ProductMap.search_count([]))

# =============================================================================
title("Factura digitada a mano (para el caso duplicado)")
# =============================================================================
# E330000000001 se captura ANTES de importar: cuando el cron la traiga, el
# documento debe entrar en `duplicate` avisando, no crear una segunda factura.
manual = env["account.move"].search([("name", "=", "E330000000001")], limit=1)
if not manual:
    manual = env["account.move"].create({
        "move_type": "in_invoice",
        "company_id": company.id,
        "journal_id": purchase_journal.id,
        "partner_id": vendor.id,
        "invoice_date": "2020-04-02",
        "invoice_line_ids": [(0, 0, {
            "product_id": p_leche.id, "quantity": 10000, "price_unit": 40,
        })],
    })
    fiscal_type = env["l10n_latam.document.type"].search(
        [("l10n_do_ncf_type", "=", "e-debit_note"), ("country_id", "=", DO.id)], limit=1)
    manual.write({
        "l10n_latam_document_type_id": fiscal_type.id,
        "l10n_latam_document_number": "E330000000001",
    })
env.cr.commit()
show("Factura manual", "%s NCF %s por %s" % (manual.state, manual.name, manual.amount_total))

# =============================================================================
title("Importando del sandbox REAL (sin simulación)")
# =============================================================================
Document = env["l10n_do.ecf.received.document"]
imported = Document._cron_fetch_received_documents()
env.cr.commit()
show("Documentos en la bandeja", Document.search_count([]))

print()
print("   %-16s %-4s %-11s %-6s %14s %-7s %s"
      % ("e-NCF", "tipo", "estado", "incl", "total", "líneas", "por vincular"))
for d in Document.search([], order="encf"):
    print("   %-16s %-4s %-11s %-6s %14.2f %-7s %s" % (
        d.encf, d.ecf_type, d.state, "SI" if d.tax_included else "no",
        d.amount_total_xml, d.line_count, d.pending_line_count))

# =============================================================================
title("Documento vinculado sin recordar, con OC creada")
# =============================================================================
# E310000000005 mezcla ITBIS 18/16/0/exento y trae montos CON ITBIS incluido.
# Se vinculan sus líneas SIN recordar el vínculo, así en las líneas del documento
# conviven los dos estados del widget: las que entraron por alias en verde, las
# vinculadas a mano en naranja con la varita para guardarlas. Además queda con OC,
# que es el documento donde se ve la ruta A a medias: sólo "Recibir + Facturar".
doc_widget = Document.search([("encf", "=", "E310000000005")], limit=1)
if doc_widget and doc_widget.state in ("to_map", "ready"):
    wizard = env["l10n_do.ecf.product.mapping.wizard"].create({"document_id": doc_widget.id})
    wizard.remember = False
    for wline in wizard.line_ids:
        if wline.product_id:
            continue
        name = (wline.item_name or "").upper()
        wline.product_id = (
            p_lapices if "LAPIC" in name else
            p_pan if "PAN" in name else
            p_galletas if "SALSA" in name else
            p_leche
        )
        wline.action = "link"
    wizard.action_apply()
    doc_widget.action_create_purchase_order()
    env.cr.commit()

    order = doc_widget.purchase_order_id
    show("Orden de compra", "%s (%s)" % (order.name, order.state))
    print()
    print("   %-26s %-24s %-8s %s" % ("producto", "ítem del proveedor", "código", "estado del vínculo"))
    for line in doc_widget.line_ids:
        print("   %-26s %-24s %-8s %s" % (
            line.product_id.display_name[:26],
            (line.item_name or "-")[:24],
            line.item_code or "-",
            line.map_state))

# =============================================================================
title("Qué probar en el navegador")
# =============================================================================
print("""
   Compras -> Supplier e-CF -> Received e-CF

   E310000000034  to_map     5 líneas iguales exentas, 25 millones. Vincular en el
                             wizard y probar "Create PO + Receive + Bill".
   E310000000008  to_map     6 líneas con el MISMO código 1521. Sólo "Gouda Import"
                             entra por alias (código + nombre); las otras 5 van al
                             wizard: el código solo no identifica nada. Se pueden
                             mandar varias al mismo producto: un producto admite N
                             formas de nombrarlo. En esas 5 líneas también sirve el
                             botón "+" del widget: crea el producto desde el ítem del
                             proveedor y lo vincula, sin copiar el código 1521 como
                             referencia interna (repetido no identifica nada).
   E310000000005  ready      Vinculada sin recordar y con OC creada -> en sus líneas,
                             varita naranja = guardar la forma de nombrarlo, "+" rojo =
                             crear el producto que falta; en la cabecera sólo queda
                             "Recibir + Facturar" (ruta A). La OC sola NO cierra el
                             documento: sigue en ready hasta que exista factura.
                             Probar también facturar esa OC desde Compras (botón
                             "Crear factura" de la orden): la factura sale con NCF,
                             código de seguridad y XML, y el documento pasa a done.
   E310000000002  to_map     Lleva ISC (MontoImpuestoAdicional 731.32): aviso naranja
                             de que la factura saldrá corta por ese monto.
   E330000000001  duplicate  Ya estaba digitada a mano -> "Link to existing bill".
   E340000000015  error      MontoTotal 0.00 con una línea de 1.00: no cuadra y no se
                             factura. Probar "Retry" y "Reject".

   Rutas contables: son exclusivas. Con OC creada desaparece la factura directa, y
   con factura directa desaparecen las de OC. El documento llega a done cuando existe
   una factura relacionada, la cree quien la cree: desde aquí, desde la orden de
   compra, o con el autocompletado de la factura de proveedor. Si esa factura no suma
   el total del e-CF (se facturó parte de la orden) se enlaza igual y avisa el
   faltante en el chatter de ambos registros.

   Aprobación comercial: Aprobar / Rechazar llaman al sandbox de verdad (POST /acecf/
   con submit_to_dgii=true). Es el entorno de pruebas de DGII, pero es una escritura
   real: úsalos a conciencia. "Actualizar aprobación" sólo aparece cuando ya se envió
   un ACECF. Ambos siguen disponibles aunque el documento ya esté facturado: el plazo
   de la DGII corre desde la recepción.

   Ajustes: Contabilidad -> Ajustes -> Localización Dominicana -> bloque de
   recepción (ventana del cron, límite de XML, plazo de aprobación, tipo de costos y
   gastos por defecto, impuestos por indicador, sincronizar con la lista del
   proveedor).

   Memoria: Compras -> Supplier e-CF -> Vendor item links. Una fila por proveedor y
   producto, con sus formas de nombrarlo como etiquetas. También se ve desde la ficha
   del producto, pestaña "Artículos del proveedor (e-CF)". Crear una fila ahí -o
   agregarle otra etiqueta- resuelve al instante las líneas que ya estaban pendientes
   en la bandeja con esa misma forma de nombrarlo, y lo anota en el chatter.
""")
env.cr.commit()
print("[ok] bandeja lista")
'''


def run(cmd, **kwargs):
    print("[run]", " ".join(cmd[:6]), "...")
    return subprocess.run(cmd, **kwargs)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop & recreate DB")
    parser.add_argument(
        "--inbox",
        action="store_true",
        help="deja la bandeja lista para pruebas funcionales en el navegador, "
        "con documentos REALES del sandbox y sin procesar (no corre el flujo completo)",
    )
    args = parser.parse_args()

    if args.reset:
        run(["docker", "exec", CONTAINER, "bash", "-c",
             "PGPASSWORD=odoo_password psql -h odoo-db -U odoo postgres -c "
             f"\"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             f"WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();\" >/dev/null 2>&1; "
             f"PGPASSWORD=odoo_password dropdb -h odoo-db -U odoo --if-exists {DB_NAME}"])

    # 1. Módulo bajo prueba sobre DB vacía: arrastra l10n_do_accounting,
    #    l10n_do_ecf_invoicing, l10n_do_purchase y purchase_stock.
    #    `--without-demo=True`: desde la 19 el valor `all` ya no es booleano
    #    válido y Odoo avisa por consola antes de asumir True.
    result = run(["docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8073", "--log-level", "warn",
                  "--stop-after-init", "--no-http", "--without-demo=True",
                  "-i", MODULES])
    if result.returncode != 0:
        print("[error] instalación del módulo falló")
        sys.exit(1)

    # 2. Sembrado: bandeja para pruebas funcionales, o simulación completa.
    seed = INBOX_SEED if args.inbox else SIMULATION
    result = run(["docker", "exec", "-i", CONTAINER, "odoo", "shell",
                  "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8073", "--log-level", "warn", "--no-http"],
                 input=seed.encode())
    if result.returncode != 0:
        print("[error] sembrado falló")
        sys.exit(1)

    print(f"\n[done] DB '{DB_NAME}' lista.")


if __name__ == "__main__":
    main()
