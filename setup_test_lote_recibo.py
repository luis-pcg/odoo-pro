#!/usr/bin/env python3
"""
Setup script: lote/serie visible en el Recibo Fiscal 60mm (tarea #70841)

Crea una DB limpia, en español (es_DO), multiempresa, para validar que el lote
del producto se imprime en el reporte "Recibo Fiscal"
(`l10n_do_accounting.l10n_do_invoice_receipt`, formato 60mm tipo POS) solo
cuando la compañía lo tiene configurado.

Dos compañías dominicanas (plan contable 'do', RNC válido, diario de ventas con
documentos fiscales y sus tipos de comprobante NCF/e-CF creados), cada una con
UNA factura publicada de un producto con seguimiento por lote despachado en dos
lotes:

    FARMACIA DEMO RD SRL   → ajuste ENCENDIDO  → el recibo muestra el lote
    OTRA EMPRESA RD SRL    → ajuste APAGADO    → el recibo NO muestra el lote

Así se valida de una sola pasada el caso positivo, el negativo y que el ajuste
es por compañía (multiempresa).

Nota e-CF: la numeración e-CF (prefijos E31/E32, `is_ecf_invoice`) la aporta
`l10n_do_accounting` y los tipos E quedan creados en el diario. El módulo de
envío a DGII (`l10n_do_ecf_invoicing`) NO se instala: en este contenedor
`signxml==3.2.2` truena con `cryptography 49.0.0` (requirements.txt pide
`cryptography<37`), fallo de entorno ajeno a esta tarea.

Uso:
    python3 setup_test_lote_recibo.py            # crea/reusa DB y siembra
    python3 setup_test_lote_recibo.py --reset    # drop & recreate DB

Requisitos:
    - Contenedor Odoo corriendo (lfernandez_v17), UI en http://localhost:8090
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_lote_recibo"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
MODULES = ",".join([
    "l10n_do_accounting",           # NCF / e-CF (numeración) + Recibo Fiscal 60mm
    "l10n_do_receipt_lot",          # lote/serie en el Recibo Fiscal (ajuste por compañía)
    "l10n_do_sale",                 # ventas con localización RD
    "stock_picking_invoice_link",   # enlace factura ↔ picking (de aquí sale el lote)
    "sale_management",              # UI de pedidos de venta
])

SEED_SCRIPT = r'''
env = env  # noqa: odoo shell provides env

from stdnum.do import rnc as rnc_mod

from odoo import fields

REPORT = "l10n_do_accounting.l10n_do_invoice_receipt"
DO = env.ref('base.do')


def make_rnc(base8):
    """RNC dominicano válido (9 dígitos): base de 8 + dígito verificador."""
    for d in range(10):
        cand = base8 + str(d)
        if rnc_mod.is_valid(cand):
            return cand
    raise ValueError("no check digit for %s" % base8)


# ─── 1. Idioma es_DO ─────────────────────────────────────────────────────────
es_do = env['res.lang'].with_context(active_test=False).search(
    [('code', '=', 'es_DO')], limit=1)
env['base.language.install'].create({
    'lang_ids': [(6, 0, es_do.ids)],
    'overwrite': True,
}).lang_install()

admin = env.ref('base.user_admin')
admin.lang = 'es_DO'
admin.groups_id |= (
    env.ref('stock.group_production_lot')
    | env.ref('stock.group_stock_multi_locations')
    | env.ref('account.group_account_manager')
    | env.ref('base.group_multi_company')
)
env.cr.commit()


# ─── 2. Compañías dominicanas ────────────────────────────────────────────────
def setup_company(company, name, rnc_base, show_lot):
    """Compañía dominicana emisora de NCF, con o sin lote en el recibo."""
    company.write({
        'name': name,
        'country_id': DO.id,
        'vat': make_rnc(rnc_base),
        'street': 'Av. Winston Churchill 1099',
        'city': 'Santo Domingo',
        'phone': '+1 809 000 0000',
    })
    # DB de desarrollo sin salida a los servicios de DGII.
    if 'ncf_validation_target' in company._fields:
        company.ncf_validation_target = 'none'
    if 'l10_do_can_validate_rnc' in company._fields:
        company.l10_do_can_validate_rnc = False
    company.partner_id.lang = 'es_DO'

    if company.chart_template != 'do':
        env['account.chart.template'].try_loading(
            'do', company=company, install_demo=False)
        env.cr.commit()

    # Diario de ventas con documentos fiscales: crea los tipos de comprobante.
    journal = env['account.journal'].search(
        [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
    if not journal.l10n_latam_use_documents:
        journal.l10n_latam_use_documents = True
    else:
        journal._l10n_do_create_document_types()

    # EL AJUSTE DE ESTA TAREA (por compañía).
    company.l10n_do_receipt_show_lot = show_lot
    return journal


company_on = env.ref('base.main_company')
journal_on = setup_company(
    company_on, 'FARMACIA DEMO RD SRL', '13000002', show_lot=True)

company_off = env['res.company'].search(
    [('name', '=', 'OTRA EMPRESA RD SRL')], limit=1)
if not company_off:
    company_off = env['res.company'].create({
        'name': 'OTRA EMPRESA RD SRL',
        'country_id': DO.id,
    })
    env.cr.commit()
journal_off = setup_company(
    company_off, 'OTRA EMPRESA RD SRL', '13000003', show_lot=False)

admin.company_ids |= (company_on | company_off)
env = env(context=dict(
    env.context, allowed_company_ids=[company_on.id, company_off.id]))

# ─── 3. Cliente consumidor final ─────────────────────────────────────────────
partner = env['res.partner'].search(
    [('name', '=', 'JUAN PEREZ (CONSUMIDOR)')], limit=1)
if not partner:
    partner = env['res.partner'].create({
        'name': 'JUAN PEREZ (CONSUMIDOR)',
        'vat': '22400559690',
        'l10n_do_dgii_tax_payer_type': 'non_payer',
        'country_id': DO.id,
    })
partner.lang = 'es_DO'

# ─── 4. Producto de farmacia con seguimiento por lote (compartido) ───────────
taxes = env['account.tax'].search([
    ('type_tax_use', '=', 'sale'),
    ('amount', '=', 18),
    ('company_id', 'in', [company_on.id, company_off.id]),
])
product = env['product.product'].search([('default_code', '=', 'ACET-500')], limit=1)
if not product:
    product = env['product.product'].create({
        'name': 'ACETAMINOFEN 500MG TAB',
        'default_code': 'ACET-500',
        'type': 'product',
        'tracking': 'lot',
        'list_price': 25.0,
        'company_id': False,
    })
product.taxes_id = [(6, 0, taxes.ids)]


# ─── 5. Ciclo venta → entrega con lotes → factura ────────────────────────────
def sales_cycle(company, lot_specs, qty):
    """Existencia por lotes, pedido, entrega validada y factura publicada."""
    cenv = env(context=dict(env.context, allowed_company_ids=[company.id]))
    warehouse = cenv['stock.warehouse'].search(
        [('company_id', '=', company.id)], limit=1)
    stock_location = warehouse.lot_stock_id
    quant_model = cenv['stock.quant'].with_company(company)

    for lot_name, lot_qty in lot_specs:
        lot = cenv['stock.lot'].search([
            ('name', '=', lot_name), ('product_id', '=', product.id),
            ('company_id', '=', company.id),
        ], limit=1)
        if not lot:
            lot = cenv['stock.lot'].create({
                'name': lot_name,
                'product_id': product.id,
                'company_id': company.id,
            })
        on_hand = sum(quant_model.search([
            ('product_id', '=', product.id), ('lot_id', '=', lot.id),
            ('location_id', '=', stock_location.id),
        ]).mapped('quantity'))
        if on_hand < lot_qty:
            quant_model._update_available_quantity(
                product, stock_location, lot_qty - on_hand, lot_id=lot)

    so = cenv['sale.order'].with_company(company).create({
        'partner_id': partner.id,
        'company_id': company.id,
        'order_line': [(0, 0, {'product_id': product.id, 'product_uom_qty': qty})],
    })
    so.action_confirm()

    picking = so.picking_ids
    picking.action_assign()
    picking.move_ids.picked = True
    picking.button_validate()
    assert picking.state == 'done', 'entrega no validada: %s' % picking.state

    invoice = so._create_invoices()
    invoice.invoice_date = invoice.invoice_date or fields.Date.context_today(invoice)
    invoice.with_context(l10n_do_active_test=True).action_post()
    return so, picking, invoice


# 3 unidades: agota el primer lote (2) y toma 1 del segundo, así la línea sale
# con dos lotes y se ve el formato con cantidades.
so_on, picking_on, invoice_on = sales_cycle(
    company_on, [('L2601-A', 2), ('L2602-B', 8)], 3)
so_off, picking_off, invoice_off = sales_cycle(
    company_off, [('X2601-A', 2), ('X2602-B', 8)], 3)

# ─── 6. Verificar los tres escenarios ────────────────────────────────────────
report_model = env['ir.actions.report'].with_context(lang='es_DO')


def render(invoice, path=None):
    invoice.invalidate_recordset()
    html = report_model._render_qweb_html(REPORT, invoice.ids)[0].decode()
    if path:
        with open(path, 'wb') as fh:
            fh.write(report_model._render_qweb_pdf(REPORT, invoice.ids)[0])
    return html


html_on = render(invoice_on, '/tmp/recibo_con_lote.pdf')
html_off = render(invoice_off, '/tmp/recibo_otra_empresa_sin_lote.pdf')

# Contraprueba del toggle en la misma compañía: apagar, renderizar, volver a
# encender (el estado final de la DB queda ENCENDIDO).
company_on.l10n_do_receipt_show_lot = False
html_toggle_off = render(invoice_on, '/tmp/recibo_toggle_apagado.pdf')
company_on.l10n_do_receipt_show_lot = True

env.cr.commit()

# ─── 7. Resultado ────────────────────────────────────────────────────────────
line_on = invoice_on.invoice_line_ids.filtered(lambda l: l.display_type == 'product')
line_off = invoice_off.invoice_line_ids.filtered(lambda l: l.display_type == 'product')

checks = [
    ('es_DO activo', es_do.active and admin.lang == 'es_DO'),
    ('ambas compañías son de RD', company_on.country_id == DO and company_off.country_id == DO),
    ('ajuste ON en %s' % company_on.name, company_on.l10n_do_receipt_show_lot),
    ('ajuste OFF en %s' % company_off.name, not company_off.l10n_do_receipt_show_lot),
    ('etiqueta traducida "Lote:" en el recibo', 'Lote:' in html_on),
    ('L2601-A y L2602-B en el recibo (ajuste ON)',
     'L2601-A' in html_on and 'L2602-B' in html_on),
    ('la otra empresa NO muestra sus lotes',
     'X2601-A' not in html_off and 'X2602-B' not in html_off),
    ('mismo recibo sin lotes al apagar el ajuste', 'L2601-A' not in html_toggle_off),
    ('NCF asignado en ambas facturas',
     bool(invoice_on.l10n_do_fiscal_number) and bool(invoice_off.l10n_do_fiscal_number)),
]

base_url = 'http://localhost:8090'
link = '%s/web?db=%s#id=%s&model=account.move&view_type=form&cids=%s' % (
    base_url, env.cr.dbname, invoice_on.id, company_on.id)

print('')
print('=' * 74)
print(' DB : %s   (admin / admin)' % env.cr.dbname)
print('=' * 74)
for company, journal, invoice, line, expected in (
    (company_on, journal_on, invoice_on, line_on, 'MUESTRA el lote'),
    (company_off, journal_off, invoice_off, line_off, 'NO muestra el lote'),
):
    print(' Compañía        : %s (id %s, RNC %s, país %s)' % (
        company.name, company.id, company.vat, company.country_id.code))
    print(' Ajuste lote     : %s  → %s' % (
        company.l10n_do_receipt_show_lot, expected))
    print(' Diario ventas   : %s  documentos=%s  tipos=%s' % (
        journal.code, journal.l10n_latam_use_documents,
        len(journal.l10n_do_document_type_ids)))
    print(' Factura         : id %s  %s  NCF %s  total %s' % (
        invoice.id, invoice.name, invoice.l10n_do_fiscal_number,
        invoice.amount_total))
    print(' Lotes de la línea: %s' % line._l10n_do_get_receipt_lot_info())
    print('-' * 74)
for label, ok in checks:
    print(' [%s] %s' % ('OK' if ok else 'FALLA', label))
print('=' * 74)
print(' LINK (factura con lote, DB preseleccionada):')
print('   %s' % link)
print('')
print(' Imprimir → Recibo Fiscal')
print('')
print(' Factura de la otra empresa (no debe mostrar lote):')
print('   %s/web?db=%s#id=%s&model=account.move&view_type=form&cids=%s' % (
    base_url, env.cr.dbname, invoice_off.id, company_off.id))
print('')

if not all(ok for _label, ok in checks):
    raise SystemExit('[error] alguna verificación falló')
'''


def run(cmd, **kw):
    print("[run]", " ".join(cmd[:6]), "...")
    return subprocess.run(cmd, **kw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop & recreate DB")
    args = parser.parse_args()

    if args.reset:
        run(["docker", "exec", CONTAINER, "bash", "-c",
             f"PGPASSWORD=odoo_password psql -h odoo-db -U odoo postgres -c "
             f"\"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             f"WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();\" >/dev/null 2>&1; "
             f"PGPASSWORD=odoo_password dropdb -h odoo-db -U odoo --if-exists {DB_NAME}"])

    # 1. Crear DB e instalar módulos (sin demo data, con traducciones es_DO)
    result = run(["docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn",
                  "--stop-after-init", "--no-http", "--without-demo=all",
                  "--load-language", "es_DO", "-i", MODULES])
    if result.returncode != 0:
        print("[error] instalación falló"); sys.exit(1)

    # 2. Sembrar datos + verificar los tres escenarios vía odoo shell
    result = run(["docker", "exec", "-i", CONTAINER, "odoo", "shell",
                  "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn", "--no-http"],
                 input=SEED_SCRIPT.encode())
    if result.returncode != 0:
        print("[error] seed falló"); sys.exit(1)

    print(f"\n[done] DB '{DB_NAME}' lista.")


if __name__ == "__main__":
    main()
