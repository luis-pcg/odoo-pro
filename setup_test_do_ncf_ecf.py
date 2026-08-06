#!/usr/bin/env python3
"""
Setup: DB dominicana para validar los cambios pendientes de l10n_do_accounting.

Cambio bajo prueba (sin commitear, versión 17.0.1.4.0):

    Ajuste por compañía "Mostrar Lote/Serie en Recibo Fiscal"
    (`res.company.l10n_do_receipt_show_lot`, expuesto en Ajustes de
    Contabilidad → bloque "Dominican Localization") que imprime el
    lote/serie de cada producto despachado en el reporte
    `l10n_do_accounting.l10n_do_invoice_receipt` (Recibo Fiscal 60mm).

Crea una DB limpia en español (es_DO), sin datos demo, con TRES compañías
dominicanas (plan contable 'do', RNC válido, diario de ventas con documentos
fiscales), cada una con una factura publicada de un producto con seguimiento
por lote despachado por almacén:

    1. FARMACIA DEMO RD SRL   NCF  B01  ajuste ON   → recibo con DOS lotes
    2. FARMACIA ECF RD SRL    e-CF E31  ajuste ON   → recibo con UN lote
    3. OTRA EMPRESA RD SRL    NCF  B02  ajuste OFF  → recibo SIN lote

Así queda cubierto: NCF y e-CF, formato de un solo lote y de varios lotes con
cantidad, el caso negativo, y que el ajuste es por compañía.

Uso:
    python3 setup_test_do_ncf_ecf.py            # crea/reusa DB y siembra
    python3 setup_test_do_ncf_ecf.py --reset    # drop & recreate DB

Requisitos:
    - Contenedor Odoo corriendo (lfernandez_v17), UI en http://localhost:8090
    - `dbfilter` en conf/odoo.conf debe permitir la DB de abajo.

Nota e-CF: la numeración e-CF (prefijos E31/E32, `is_ecf_invoice`) la aporta
`l10n_do_accounting`. El módulo de envío a DGII (`l10n_do_ecf_invoicing`) NO se
instala: en este contenedor `signxml==3.2.2` truena con `cryptography 49.0.0`
(su requirements.txt pide `cryptography<37`), fallo de entorno ajeno a estos
cambios.
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
MODULES = ",".join([
    "l10n_do_accounting",           # NCF / e-CF + Recibo Fiscal 60mm (cambio bajo prueba)
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
DOC_B01 = env.ref('l10n_do_accounting.ncf_fiscal_client')
DOC_B02 = env.ref('l10n_do_accounting.ncf_consumer_supplier')
DOC_E31 = env.ref('l10n_do_accounting.ecf_fiscal_client')


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
def setup_company(company, name, rnc_base, show_lot, ecf_issuer):
    """Compañía dominicana emisora de NCF o de e-CF, con/sin lote en recibo."""
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
    company.l10n_do_dgii_start_date = fields.Date.to_date('2024-01-01')

    if company.chart_template != 'do':
        env['account.chart.template'].try_loading(
            'do', company=company, install_demo=False)
        env.cr.commit()

    # Emisor de e-CF: los tipos de comprobante pasan a ser los E (E31/E32...).
    company.l10n_do_ecf_issuer = ecf_issuer

    # Diario de ventas con documentos fiscales: crea los tipos de comprobante
    # (NCF y e-CF, ambos juegos) y sus secuencias.
    journal = env['account.journal'].search(
        [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
    if not journal.l10n_latam_use_documents:
        journal.l10n_latam_use_documents = True
    else:
        journal._l10n_do_create_document_types()
    journal.l10n_do_payment_form = 'cash'

    # EL AJUSTE DE ESTA TAREA (por compañía).
    company.l10n_do_receipt_show_lot = show_lot
    return journal


def get_company(name):
    company = env['res.company'].search([('name', '=', name)], limit=1)
    if not company:
        company = env['res.company'].create({'name': name, 'country_id': DO.id})
        env.cr.commit()
    return company


company_ncf = env.ref('base.main_company')
journal_ncf = setup_company(
    company_ncf, 'FARMACIA DEMO RD SRL', '13000002',
    show_lot=True, ecf_issuer=False)

company_ecf = get_company('FARMACIA ECF RD SRL')
journal_ecf = setup_company(
    company_ecf, 'FARMACIA ECF RD SRL', '13000003',
    show_lot=True, ecf_issuer=True)

company_off = get_company('OTRA EMPRESA RD SRL')
journal_off = setup_company(
    company_off, 'OTRA EMPRESA RD SRL', '13000004',
    show_lot=False, ecf_issuer=False)

companies = company_ncf | company_ecf | company_off
admin.company_ids |= companies
env = env(context=dict(env.context, allowed_company_ids=companies.ids))

# ─── 3. Clientes ─────────────────────────────────────────────────────────────
def get_partner(name, vat, payer_type):
    partner = env['res.partner'].search([('name', '=', name)], limit=1)
    if not partner:
        partner = env['res.partner'].create({
            'name': name,
            'vat': vat,
            'l10n_do_dgii_tax_payer_type': payer_type,
            'country_id': DO.id,
        })
    partner.lang = 'es_DO'
    return partner


# Contribuyente (RNC) → Crédito Fiscal: B01 en NCF, E31 en e-CF.
partner_fiscal = get_partner('ITERATIVO SRL', '131566332', 'taxpayer')
# Consumidor final (cédula) → Factura de Consumo B02.
partner_consumo = get_partner('JUAN PEREZ (CONSUMIDOR)', '22400559690', 'non_payer')

# ─── 4. Producto con seguimiento por lote (compartido) ───────────────────────
taxes = env['account.tax'].search([
    ('type_tax_use', '=', 'sale'),
    ('amount', '=', 18),
    ('company_id', 'in', companies.ids),
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


# ─── 5. Ciclo venta → entrega con lotes → factura fiscal ─────────────────────
def sales_cycle(company, partner, lot_specs, qty, document_type):
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
    available = invoice.l10n_latam_available_document_type_ids
    assert document_type in available, (
        'tipo %s no disponible en %s (disponibles: %s)' % (
            document_type.doc_code_prefix, company.name,
            available.mapped('doc_code_prefix')))
    invoice.l10n_latam_document_type_id = document_type
    invoice.with_context(l10n_do_active_test=True).action_post()
    return so, picking, invoice


# NCF: 3 unidades agotan el primer lote (2) y toman 1 del segundo, así la línea
# sale con DOS lotes y se ve el formato con cantidades.
so_ncf, picking_ncf, invoice_ncf = sales_cycle(
    company_ncf, partner_fiscal, [('L2601-A', 2), ('L2602-B', 8)], 3, DOC_B01)
# e-CF: un único lote, se ve el formato simple (solo el nombre del lote).
so_ecf, picking_ecf, invoice_ecf = sales_cycle(
    company_ecf, partner_fiscal, [('E2601-A', 10)], 4, DOC_E31)
# Caso negativo (ajuste OFF), también con dos lotes.
so_off, picking_off, invoice_off = sales_cycle(
    company_off, partner_consumo, [('X2601-A', 2), ('X2602-B', 8)], 3, DOC_B02)

# ─── 6. Renderizar los recibos y verificar ───────────────────────────────────
report_model = env['ir.actions.report'].with_context(lang='es_DO')


def render(invoice, path=None):
    invoice.invalidate_recordset()
    html = report_model._render_qweb_html(REPORT, invoice.ids)[0].decode()
    if path:
        with open(path, 'wb') as fh:
            fh.write(report_model._render_qweb_pdf(REPORT, invoice.ids)[0])
    return html


html_ncf = render(invoice_ncf, '/tmp/recibo_ncf_b01_con_lote.pdf')
html_ecf = render(invoice_ecf, '/tmp/recibo_ecf_e31_con_lote.pdf')
html_off = render(invoice_off, '/tmp/recibo_ncf_b02_sin_lote.pdf')

# Contraprueba del toggle en la misma compañía: apagar, renderizar, volver a
# encender (el estado final de la DB queda ENCENDIDO).
company_ncf.l10n_do_receipt_show_lot = False
html_toggle_off = render(invoice_ncf, '/tmp/recibo_ncf_toggle_apagado.pdf')
company_ncf.l10n_do_receipt_show_lot = True

# El ajuste tiene que llegar también por res.config.settings (campo related).
settings = env['res.config.settings'].with_company(company_off).create({})
settings.l10n_do_receipt_show_lot = True
settings.execute()
setting_writes_company = company_off.l10n_do_receipt_show_lot
company_off.l10n_do_receipt_show_lot = False

env.cr.commit()

# ─── 7. Resultado ────────────────────────────────────────────────────────────
def product_line(invoice):
    return invoice.invoice_line_ids.filtered(
        lambda l: l.display_type == 'product')


line_ncf = product_line(invoice_ncf)
line_ecf = product_line(invoice_ecf)
line_off = product_line(invoice_off)

checks = [
    ('es_DO activo y admin en es_DO', es_do.active and admin.lang == 'es_DO'),
    ('las tres compañías son de RD',
     all(c.country_id == DO for c in companies)),
    ('NCF B01 en %s' % company_ncf.name,
     invoice_ncf.l10n_do_fiscal_number.startswith('B01')
     and not invoice_ncf.is_ecf_invoice),
    ('e-CF E31 en %s' % company_ecf.name,
     invoice_ecf.l10n_do_fiscal_number.startswith('E31')
     and invoice_ecf.is_ecf_invoice),
    ('NCF B02 en %s' % company_off.name,
     invoice_off.l10n_do_fiscal_number.startswith('B02')
     and not invoice_off.is_ecf_invoice),
    ('etiqueta traducida "Lote:" en el recibo NCF', 'Lote:' in html_ncf),
    ('etiqueta traducida "Lote:" en el recibo e-CF', 'Lote:' in html_ecf),
    ('recibo NCF con dos lotes y cantidades',
     'L2601-A' in html_ncf and 'L2602-B' in html_ncf
     and '2.00' in line_ncf._l10n_do_get_receipt_lot_info()),
    ('recibo e-CF con un solo lote, sin cantidad',
     line_ecf._l10n_do_get_receipt_lot_info() == 'E2601-A'
     and 'E2601-A' in html_ecf),
    ('compañía con ajuste OFF no muestra sus lotes',
     'X2601-A' not in html_off and 'X2602-B' not in html_off
     and 'Lote:' not in html_off),
    ('mismo recibo sin lotes al apagar el ajuste',
     'L2601-A' not in html_toggle_off and 'Lote:' not in html_toggle_off),
    ('el ajuste se guarda desde res.config.settings', setting_writes_company),
]

base_url = 'http://localhost:8090'


def link(invoice):
    return '%s/web?db=%s#id=%s&model=account.move&view_type=form&cids=%s' % (
        base_url, env.cr.dbname, invoice.id, invoice.company_id.id)


print('')
print('=' * 78)
print(' DB : %s   (admin / admin)   %s' % (env.cr.dbname, base_url))
print('=' * 78)
for company, journal, invoice, line, expected in (
    (company_ncf, journal_ncf, invoice_ncf, line_ncf, 'MUESTRA dos lotes'),
    (company_ecf, journal_ecf, invoice_ecf, line_ecf, 'MUESTRA un lote'),
    (company_off, journal_off, invoice_off, line_off, 'NO muestra lote'),
):
    print(' Compañía        : %s (id %s, RNC %s)' % (
        company.name, company.id, company.vat))
    print(' Emisor e-CF     : %s' % company.l10n_do_ecf_issuer)
    print(' Ajuste lote     : %s  → %s' % (
        company.l10n_do_receipt_show_lot, expected))
    print(' Diario ventas   : %s  documentos=%s  tipos=%s' % (
        journal.code, journal.l10n_latam_use_documents,
        len(journal.l10n_do_document_type_ids)))
    print(' Factura         : id %s  %s  comprobante %s (%s)  total %s' % (
        invoice.id, invoice.name, invoice.l10n_do_fiscal_number,
        invoice.l10n_latam_document_type_id.name, invoice.amount_total))
    print(' Lotes de la línea: %s' % line._l10n_do_get_receipt_lot_info())
    print(' LINK            : %s' % link(invoice))
    print('-' * 78)
for label, ok in checks:
    print(' [%s] %s' % ('OK' if ok else 'FALLA', label))
print('=' * 78)
print(' En cada factura: Imprimir → Recibo Fiscal')
print(' PDFs dentro del contenedor: /tmp/recibo_*.pdf')
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

    # 2. Sembrar datos + verificar los escenarios vía odoo shell
    result = run(["docker", "exec", "-i", CONTAINER, "odoo", "shell",
                  "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn", "--no-http"],
                 input=SEED_SCRIPT.encode())
    if result.returncode != 0:
        print("[error] seed falló"); sys.exit(1)

    print(f"\n[done] DB '{DB_NAME}' lista.")


if __name__ == "__main__":
    main()
