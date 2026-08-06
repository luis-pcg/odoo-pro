#!/usr/bin/env python3
"""
Factura fiscal con varias líneas sobre la DB `test_do_ncf_ecf`.

Sirve para ver el Recibo Fiscal 60mm con una factura realista y comprobar que
el lote solo sale en las líneas que lo tienen, y que convive con lo que ya
imprimía el reporte (descuento, secciones, notas).

Se crea en FARMACIA DEMO RD SRL (ajuste "Mostrar Lote/Serie" ENCENDIDO,
comprobante NCF B01) con estas líneas:

    1. sección "MEDICAMENTOS"                    → sin lote (ver nota abajo)
    2. AMOXICILINA 500MG   lote, 3 uds           → DOS lotes con cantidad
    3. IBUPROFENO 400MG    lote, 5 uds           → UN lote, sin cantidad
    4. AMOXICILINA 500MG   lote, 2 uds, dto 15%  → lote + línea de descuento
    5. sección "EQUIPOS"                         → sin lote
    6. TENSIOMETRO DIGITAL serie, 3 uds          → TRES seriales
    7. GUANTES NITRILO     sin tracking, 10 uds  → sin lote
    8. CONSULTA MEDICA     servicio, 1 ud        → sin lote (no hay despacho)
    9. nota al pie                               → sin lote

Hallazgo PREEXISTENTE (no lo causa este diff): el reporte recorre
`o.invoice_line_ids` sin filtrar `display_type`, y solo imprime
`line.product_id`. Las secciones y notas salen como filas en blanco con
"0.00 RD$ 0.00 RD$ 0.00" en lugar de su texto. Se verifica solo que no
revientan ni arrastran la etiqueta de lote.

Uso:
    python3 add_multiline_invoice.py            # crea la factura o reusa la existente
    python3 add_multiline_invoice.py --force    # crea otra factura igual

Requisitos: DB `test_do_ncf_ecf` creada con setup_test_do_ncf_ecf.py.
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_do_ncf_ecf"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]

SEED_SCRIPT = r'''
env = env  # noqa: odoo shell provides env

FORCE = __FORCE__
MARK = 'RECIBO-MULTILINEA'

import re

from odoo import fields
from odoo.tools.misc import formatLang

REPORT = "l10n_do_accounting.l10n_do_invoice_receipt"
DO = env.ref('base.do')
DOC_B01 = env.ref('l10n_do_accounting.ncf_fiscal_client')

company = env['res.company'].search([('name', '=', 'FARMACIA DEMO RD SRL')], limit=1)
assert company, 'falta la compañía FARMACIA DEMO RD SRL: corre setup_test_do_ncf_ecf.py'
assert company.l10n_do_receipt_show_lot, 'el ajuste de lote está apagado en la compañía'

partner = env['res.partner'].search([('name', '=', 'ITERATIVO SRL')], limit=1)
assert partner, 'falta el cliente ITERATIVO SRL'

env = env(context=dict(env.context, allowed_company_ids=[company.id], lang='es_DO'))
cenv = env['ir.model'].with_company(company).env

taxes = env['account.tax'].search([
    ('type_tax_use', '=', 'sale'), ('amount', '=', 18),
    ('company_id', '=', company.id),
])
warehouse = cenv['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
stock_location = warehouse.lot_stock_id
quant_model = cenv['stock.quant'].with_company(company)


# ─── Productos ───────────────────────────────────────────────────────────────
def get_product(code, name, tracking, price, ptype='product'):
    product = env['product.product'].search([('default_code', '=', code)], limit=1)
    if not product:
        product = env['product.product'].create({
            'name': name,
            'default_code': code,
            'type': ptype,
            'tracking': tracking,
            'list_price': price,
            'company_id': company.id,
            'invoice_policy': 'order',
        })
    product.taxes_id = [(6, 0, taxes.ids)]
    return product


existing = env['account.move'].search([
    ('ref', '=', MARK), ('company_id', '=', company.id), ('state', '=', 'posted'),
], limit=1)

p_multi = get_product('AMOX-500', 'AMOXICILINA 500MG CAP', 'lot', 40.0)
p_single = get_product('IBUP-400', 'IBUPROFENO 400MG TAB', 'lot', 18.0)
p_serial = get_product('TENSIO-01', 'TENSIOMETRO DIGITAL', 'serial', 2500.0)
p_plain = get_product('GUAN-NIT-M', 'GUANTES NITRILO TALLA M', 'none', 12.0)
p_service = get_product('CONS-MED', 'CONSULTA MEDICA', 'none', 1200.0, ptype='service')


def stock_lot(product, lot_name, qty):
    lot = cenv['stock.lot'].search([
        ('name', '=', lot_name), ('product_id', '=', product.id),
        ('company_id', '=', company.id),
    ], limit=1)
    if not lot:
        lot = cenv['stock.lot'].create({
            'name': lot_name, 'product_id': product.id, 'company_id': company.id,
        })
    on_hand = sum(quant_model.search([
        ('product_id', '=', product.id), ('lot_id', '=', lot.id),
        ('location_id', '=', stock_location.id),
    ]).mapped('quantity'))
    if on_hand < qty:
        quant_model._update_available_quantity(
            product, stock_location, qty - on_hand, lot_id=lot)
    return lot


def seed_stock():
    # AMOXICILINA: existencia justa para que 3 uds tomen DOS lotes (2 + 1) y
    # las 2 uds de la línea con descuento salgan del segundo lote.
    stock_lot(p_multi, 'AMX-2601', 2)
    stock_lot(p_multi, 'AMX-2602', 3)
    # IBUPROFENO: un solo lote con existencia sobrada → línea con UN lote.
    stock_lot(p_single, 'IBU-2601', 50)
    # TENSIOMETRO: seguimiento por serie, un número de serie por unidad.
    for serial in ('SN-TEN-0001', 'SN-TEN-0002', 'SN-TEN-0003'):
        stock_lot(p_serial, serial, 1)
    # GUANTES: sin seguimiento.
    on_hand_plain = sum(quant_model.search([
        ('product_id', '=', p_plain.id), ('location_id', '=', stock_location.id),
    ]).mapped('quantity'))
    if on_hand_plain < 100:
        quant_model._update_available_quantity(
            p_plain, stock_location, 100 - on_hand_plain)
    env.cr.commit()


def build_invoice():
    """Pedido → entrega con lotes/series → factura fiscal publicada."""
    order_lines = [
        (p_multi, 3, 0.0),
        (p_single, 5, 0.0),
        (p_multi, 2, 15.0),
        (p_serial, 3, 0.0),
        (p_plain, 10, 0.0),
        (p_service, 1, 0.0),
    ]
    so = cenv['sale.order'].with_company(company).create({
        'partner_id': partner.id,
        'company_id': company.id,
        'order_line': [
            (0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'discount': discount,
            })
            for product, qty, discount in order_lines
        ],
    })
    so.action_confirm()

    picking = so.picking_ids
    picking.action_assign()
    picking.move_ids.picked = True
    picking.button_validate()
    assert picking.state == 'done', 'entrega no validada: %s' % picking.state

    invoice = so._create_invoices()
    invoice.invoice_date = invoice.invoice_date or fields.Date.context_today(invoice)
    invoice.l10n_latam_document_type_id = DOC_B01
    invoice.ref = MARK

    # Secciones y nota: el reporte recorre invoice_line_ids sin filtrar, así
    # que también hay que ver que estas líneas no revienten al pedir el lote.
    base_sequence = invoice.invoice_line_ids.filtered(
        lambda l: l.display_type == 'product')[0].sequence
    serial_line = invoice.invoice_line_ids.filtered(
        lambda l: l.product_id == p_serial)
    invoice.write({'invoice_line_ids': [
        (0, 0, {
            'display_type': 'line_section',
            'name': 'MEDICAMENTOS',
            'sequence': base_sequence - 1,
        }),
        (0, 0, {
            'display_type': 'line_section',
            'name': 'EQUIPOS Y SERVICIOS',
            'sequence': serial_line.sequence - 1 if serial_line else base_sequence + 50,
        }),
        (0, 0, {
            'display_type': 'line_note',
            'name': 'Medicamentos no tienen devolución. Gracias por su compra.',
            'sequence': 999,
        }),
    ]})
    invoice.with_context(l10n_do_active_test=True).action_post()
    env.cr.commit()
    return picking, invoice


if existing and not FORCE:
    invoice = existing
    picking = invoice.invoice_line_ids.move_line_ids.picking_id[:1]
    print(' [info] reusando la factura %s (ref %s); --force crea otra' % (
        invoice.name, MARK))
else:
    seed_stock()
    picking, invoice = build_invoice()

# ─── Render y verificación ───────────────────────────────────────────────────
report_model = env['ir.actions.report'].with_context(lang='es_DO')
invoice.invalidate_recordset()
html = report_model._render_qweb_html(REPORT, invoice.ids)[0].decode()
# El PDF no se puede armar desde `odoo shell --no-http`: wkhtmltopdf no puede
# bajar los assets y muere con ConnectionRefusedError. El PDF de verdad se saca
# desde la UI (Imprimir → Recibo Fiscal) o por /report/pdf/<report>/<id>.
try:
    pdf = report_model._render_qweb_pdf(REPORT, invoice.ids)[0]
    with open('/tmp/recibo_ncf_multilinea.pdf', 'wb') as fh:
        fh.write(pdf)
    pdf_note = '/tmp/recibo_ncf_multilinea.pdf dentro del contenedor'
except Exception as error:
    pdf_note = 'sin PDF en shell (%s); usar la UI' % type(error).__name__


def expected_lot_info(line):
    """Lo que debería imprimirse, reconstruido desde los movimientos reales."""
    move_lines = line.move_line_ids.filtered(
        lambda m: m.state == 'done').move_line_ids.filtered('lot_id')
    if not move_lines:
        return False
    qty_by_lot = {}
    for move_line in move_lines:
        qty_by_lot[move_line.lot_id] = (
            qty_by_lot.get(move_line.lot_id, 0.0) + move_line.quantity)
    if len(qty_by_lot) == 1:
        return next(iter(qty_by_lot)).name
    return ', '.join(
        '%s (%s)' % (lot.name, formatLang(env, qty, dp='Product Unit of Measure'))
        for lot, qty in qty_by_lot.items()
    )


rows = []
for line in invoice.invoice_line_ids.sorted('sequence'):
    rows.append((line, line._l10n_do_get_receipt_lot_info(), expected_lot_info(line)))

tracked = [r for r in rows if r[1]]
untracked = [r for r in rows if not r[1]]
lot_labels_in_html = len(re.findall(r'Lote:', html))

# Filas de la tabla de líneas del recibo, para ver qué imprime cada una.
tbody = re.search(r'<tbody>(.*?)</tbody>', html, re.S).group(1)
receipt_rows = [
    ' '.join(re.sub(r'<[^>]+>', ' ', row).split())
    for row in re.findall(r'<tr.*?</tr>', tbody, re.S)
]
blank_rows = [row for row in receipt_rows if not re.search(r'[a-z]', row)]
service_row = next(r for r in rows if r[0].product_id == p_service)
plain_row = next(r for r in rows if r[0].product_id == p_plain)
section_rows = [r for r in rows if r[0].display_type in ('line_section', 'line_note')]
multi_rows = [r for r in rows if r[0].product_id == p_multi]
serial_row = next(r for r in rows if r[0].product_id == p_serial)
discount_row = next(r for r in multi_rows if r[0].discount)
plain_multi_row = next(r for r in multi_rows if not r[0].discount)
single_row = next(r for r in rows if r[0].product_id == p_single)

checks = [
    ('NCF B01 asignado', invoice.l10n_do_fiscal_number.startswith('B01')),
    ('todas las líneas imprimen lo que dicen los movimientos',
     all(got == exp for _l, got, exp in rows)),
    ('4 líneas con lote/serie y 4 etiquetas "Lote:" en el recibo',
     len(tracked) == 4 and lot_labels_in_html == 4),
    ('línea de 3 uds toma dos lotes con cantidad',
     plain_multi_row[1].count(',') == 1 and '(' in plain_multi_row[1]),
    ('línea de un solo lote sin cantidad', single_row[1] == 'IBU-2601'),
    ('línea con serie lista los tres seriales',
     all(sn in serial_row[1] for sn in
         ('SN-TEN-0001', 'SN-TEN-0002', 'SN-TEN-0003'))),
    ('línea con descuento imprime lote y descuento',
     bool(discount_row[1]) and discount_row[1] in html and '15.0' in html),
    ('producto sin seguimiento no imprime lote', plain_row[1] is False),
    ('servicio no imprime lote', service_row[1] is False),
    ('secciones y nota no rompen el reporte ni piden lote',
     len(section_rows) == 3 and all(r[1] is False for r in section_rows)
     and len(receipt_rows) == len(invoice.invoice_line_ids)),
    ('QUIRK PREEXISTENTE: secciones/notas salen como filas en blanco',
     len(blank_rows) == 3
     and not any(w in html for w in
                 ('MEDICAMENTOS', 'EQUIPOS Y SERVICIOS', 'no tienen devoluci'))),
    ('cada lote impreso existe en la entrega',
     all(lot.name in html for lot in picking.move_line_ids.lot_id)),
]

base_url = 'http://localhost:8090'
print('')
print('=' * 88)
print(' DB %s   compañía %s (ajuste lote=%s)' % (
    env.cr.dbname, company.name, company.l10n_do_receipt_show_lot))
print(' Factura id %s  %s  NCF %s  total %s  (%s líneas)' % (
    invoice.id, invoice.name, invoice.l10n_do_fiscal_number,
    invoice.amount_total, len(invoice.invoice_line_ids)))
print(' Entrega %s (%s)' % (picking.name, picking.state))
print('=' * 88)
print(' %-32s %-8s %-6s %s' % ('LÍNEA', 'TIPO', 'CANT', 'LOTE IMPRESO'))
print('-' * 88)
for line, got, _exp in rows:
    kind = line.display_type if line.display_type != 'product' else (
        line.product_id.tracking if line.product_id.type != 'service' else 'servicio')
    print(' %-32s %-8s %-6s %s' % (
        (line.product_id.name or line.name or '')[:32],
        kind[:8],
        line.quantity if line.display_type == 'product' else '',
        got if got else '—'))
print('-' * 88)
for label, ok in checks:
    print(' [%s] %s' % ('OK' if ok else 'FALLA', label))
print('=' * 88)
print(' LINK: %s/web?db=%s#id=%s&model=account.move&view_type=form&cids=%s' % (
    base_url, env.cr.dbname, invoice.id, company.id))
print(' Imprimir → Recibo Fiscal.   PDF: %s' % pdf_note)
print('')

if not all(ok for _label, ok in checks):
    raise SystemExit('[error] alguna verificación falló')
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="crear otra factura aunque ya exista")
    args = parser.parse_args()

    script = SEED_SCRIPT.replace("__FORCE__", "True" if args.force else "False")
    result = subprocess.run(
        ["docker", "exec", "-i", CONTAINER, "odoo", "shell", "-d", DB_NAME, *DB_ARGS,
         "--http-port", "8072", "--log-level", "warn", "--no-http"],
        input=script.encode(),
    )
    if result.returncode != 0:
        print("[error] seed falló")
        sys.exit(1)


if __name__ == "__main__":
    main()
