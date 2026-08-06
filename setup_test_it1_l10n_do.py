#!/usr/bin/env python3
"""
Setup script: l10n_do_it1_report + localización RD completa (odoo-pro)

Crea la DB de prueba con los módulos de localización dominicana de odoo-pro
instalados (l10n_do_accounting con NCF, validaciones RNC/NCF, bancos y
dgii_reports), configura la compañía DO (plan contable 'do', RNC válido,
diarios fiscales con documentos latam) y siembra dos períodos:

* Mayo 2026  — escenario de validación del manual (docs/manual_calculo_it1.md §8,
               mismos números que tests/test_it1_report.py).
* Junio 2026 — escenario de cobertura completa: todas las casillas de cálculo
               automático del IT-1 quedan distintas de cero (exportación de
               servicios, exentas por destino, construcción, comisiones,
               bienes exentos, tasas 9%/8%, retención 2% tarjetas,
               comprobante de compras al 16%), más el carryover de mayo
               (casilla 29 = 243).

Al final imprime los NCF asignados, las casillas calculadas de cada período
comparadas contra los valores esperados, y genera los carryovers
mayo → junio y junio → julio (casilla 34 → 29).

Casillas de entrada manual (28, 31, 32, 35-37, 61, 64-66): editables en el
reporte vía UI (valores externos); quedan en 0 por diseño.

Uso:
    python3 setup_test_it1_l10n_do.py            # crea/reusa DB y siembra
    python3 setup_test_it1_l10n_do.py --reset    # drop & recreate DB

Requisitos:
    - Contenedor Odoo corriendo (lfernandez_v17), UI en http://localhost:8090
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_it1_l10n_do"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
MODULES = ",".join([
    "l10n_do_it1_report",       # reporte IT-1 (arrastra l10n_do + account_reports)
    "l10n_do_accounting",       # NCF / documentos fiscales latam
    "l10n_do_ncf_validation",   # validación NCF contra DGII (se apaga en la seed)
    "l10n_do_rnc_validation",   # validación RNC contra DGII (se apaga en la seed)
    "l10n_do_banks",            # catálogo de bancos RD
    "dgii_reports",             # reportes 606/607/608 DGII
])

SEED_SCRIPT = r'''
from datetime import date

env = env  # noqa: odoo shell provides env

MAY_DATE = date(2026, 5, 15)
MAY_FROM, MAY_TO = date(2026, 5, 1), date(2026, 5, 31)
JUN_DATE = date(2026, 6, 15)
JUN_FROM, JUN_TO = date(2026, 6, 1), date(2026, 6, 30)

from stdnum.do import rnc as rnc_mod


def make_rnc(base8):
    """RNC dominicano válido (9 dígitos): base de 8 + dígito verificador."""
    for d in range(10):
        cand = base8 + str(d)
        if rnc_mod.is_valid(cand):
            return cand
    raise ValueError("no check digit for %s" % base8)


company = env.ref('base.main_company')
company.write({
    'name': 'Empresa Demo RD SRL',
    'country_id': env.ref('base.do').id,
    'vat': make_rnc('13000001'),
})
# DB de desarrollo sin salida a los servicios de DGII: se apagan las
# validaciones en línea (los módulos quedan instalados y configurables).
if 'ncf_validation_target' in company._fields:
    company.ncf_validation_target = 'none'
if 'l10_do_can_validate_rnc' in company._fields:
    company.l10_do_can_validate_rnc = False

# Cargar plan contable dominicano (crea impuestos con las etiquetas del IT-1).
if company.chart_template != 'do':
    env['account.chart.template'].try_loading('do', company=company, install_demo=False)
    env.cr.commit()

env = env(context=dict(env.context, allowed_company_ids=[company.id]))
ct = env['account.chart.template'].with_company(company)

# Diarios de venta/compra con documentos fiscales (NCF).
journals = {}
for jtype in ('sale', 'purchase'):
    journal = env['account.journal'].search(
        [('type', '=', jtype), ('company_id', '=', company.id)], limit=1)
    if not journal.l10n_latam_use_documents:
        journal.l10n_latam_use_documents = True
    journals[jtype] = journal

TAXES = {
    # ventas por tasa
    'tax_18_sale': ct.ref('tax_18_sale'),
    'tax_16_sale': ct.ref('tax_16_sale'),
    'tax_9_sale': ct.ref('tax_9_sale'),
    'tax_8_sale': ct.ref('tax_8_sale'),
    'tax_18_sale_depreciable': ct.ref('tax_18_sale_depreciable'),
    # ventas no gravadas (casillas 2-8)
    'tax_0_sale_export_goods': ct.ref('tax_0_sale_export_goods'),
    'tax_0_sale_export_services': ct.ref('tax_0_sale_export_services'),
    'tax_0_sale': ct.ref('tax_0_sale'),
    'tax_0_sale_destination': ct.ref('tax_0_sale_destination'),
    'tax_0_sale_construction': ct.ref('tax_0_sale_construction'),
    'tax_0_sale_commissions': ct.ref('tax_0_sale_commissions'),
    'tax_0_sale_goods_exempt': ct.ref('tax_0_sale_goods_exempt'),
    # retenciones que nos hacen (casilla 30)
    'ret_itbis_sale_state': ct.ref('ret_itbis_sale_state'),
    'ret_itbis_sale_card': ct.ref('ret_itbis_sale_card'),
    # compras (casillas 22-24)
    'tax_18_purch': ct.ref('tax_18_purch'),
    'tax_16_purch': ct.ref('tax_16_purch'),
    'tax_18_purch_serv': ct.ref('tax_18_purch_serv'),
    'tax_18_importation': ct.ref('tax_18_importation'),
    # retenciones que hacemos (sección A)
    'ret_100_tax_person': ct.ref('ret_100_tax_person'),
    'ret_100_tax_nonprofit': ct.ref('ret_100_tax_nonprofit'),
    'ret_100_tax_security': ct.ref('ret_100_tax_security'),
    'ret_30_tax_moral': ct.ref('ret_30_tax_moral'),
    'ret_100_tax_rst_18': ct.ref('ret_100_tax_rst_18'),
    'ret_100_tax_rst_16': ct.ref('ret_100_tax_rst_16'),
    'ret_itbis_purch_receipt_18': ct.ref('ret_itbis_purch_receipt_18'),
    'ret_itbis_purch_receipt_16': ct.ref('ret_itbis_purch_receipt_16'),
}

Partner = env['res.partner']

# (tipo contribuyente DGII, base RNC o None, país)
PARTNERS = {
    'Cliente Local A':               ('taxpayer',     '13000002', 'base.do'),
    'Cliente Local B':               ('taxpayer',     '13000003', 'base.do'),
    'Cliente Exterior':              ('foreigner',    None,       'base.us'),
    'Ministerio de Obras (Estado)':  ('governmental', '40000001', 'base.do'),
    'Zona Franca Industrial SRL':    ('special',      '13000010', 'base.do'),
    'Consumidor Final':              ('non_payer',    None,       'base.do'),
    'Proveedor Bienes SRL':          ('taxpayer',     '13000004', 'base.do'),
    'Proveedor Servicios SRL':       ('taxpayer',     '13000005', 'base.do'),
    'Aduanas DGA':                   ('foreigner',    None,       'base.do'),
    'Juan Pérez (persona física)':   ('non_payer',    None,       'base.do'),
    'Fundación Esperanza (ENL)':     ('taxpayer',     '43000001', 'base.do'),
    'Seguridad Total SRL':           ('taxpayer',     '13000006', 'base.do'),
    'Consultores Asociados SRL':     ('taxpayer',     '13000007', 'base.do'),
    'Colmado Don José (RST)':        ('taxpayer',     '13000008', 'base.do'),
    'Panadería La Espiga (RST)':     ('taxpayer',     '13000009', 'base.do'),
    'Productor Informal':            ('non_payer',    None,       'base.do'),
    'Vendedora Informal 16%':        ('non_payer',    None,       'base.do'),
}


def get_partner(name):
    payer_type, rnc_base, country = PARTNERS[name]
    vals = {
        'name': name,
        'country_id': env.ref(country).id,
        'l10n_do_dgii_tax_payer_type': payer_type,
    }
    if rnc_base:
        vals['vat'] = make_rnc(rnc_base)
    elif payer_type == 'foreigner' and name == 'Cliente Exterior':
        vals['vat'] = '123456789'  # tax id extranjero (B16 exige VAT)
    partner = Partner.search([('name', '=', name)], limit=1)
    if partner:
        partner.write(vals)
    else:
        partner = Partner.create(vals)
    return partner


def get_product(name, detailed_type):
    Product = env['product.product']
    product = Product.search([('name', '=', name)], limit=1)
    return product or Product.create(
        {'name': name, 'detailed_type': detailed_type, 'taxes_id': False,
         'supplier_taxes_id': False})


def create_invoice(move_type, partner_name, amount, taxes, label, inv_date,
                   ncf=None, doc_type=None, product=None):
    journal = journals['sale' if move_type == 'out_invoice' else 'purchase']
    line_vals = {
        'name': label,
        'quantity': 1.0,
        'price_unit': amount,
        'account_id': journal.default_account_id.id,
        'tax_ids': [(6, 0, taxes.ids)],
    }
    if product:
        line_vals['product_id'] = product.id
    vals = {
        'move_type': move_type,
        'partner_id': get_partner(partner_name).id,
        'invoice_date': inv_date,
        'journal_id': journal.id,
        'invoice_line_ids': [(0, 0, line_vals)],
    }
    if ncf:
        vals['l10n_do_fiscal_number'] = ncf  # NCF del suplidor (documento manual)
    if doc_type:
        vals['l10n_latam_document_type_id'] = env.ref(doc_type).id
    move = env['account.move'].create(vals)
    move.action_post()
    return move


def posted_in(date_from, date_to):
    return env['account.move'].search_count([
        ('company_id', '=', company.id), ('state', '=', 'posted'),
        ('invoice_date', '>=', date_from), ('invoice_date', '<=', date_to),
    ])


export_product = get_product('Mercancía de Exportación', 'consu')

# ═════════════════════ MAYO 2026 — escenario del manual (§8) ════════════════
if posted_in(MAY_FROM, MAY_TO):
    print(f"[seed] Mayo: ya hay {posted_in(MAY_FROM, MAY_TO)} facturas; no se duplica.")
else:
    inv = lambda *a, **kw: create_invoice(*a, inv_date=MAY_DATE, **kw)
    # Ventas — NCF emitidos automáticamente
    inv('out_invoice', 'Cliente Local A', 1000.0,
        TAXES['tax_18_sale'], 'Venta gravada 18%')
    inv('out_invoice', 'Cliente Local B', 500.0,
        TAXES['tax_16_sale'], 'Venta gravada 16%')
    inv('out_invoice', 'Cliente Exterior', 2000.0,
        TAXES['tax_0_sale_export_goods'], 'Exportación de bienes',
        doc_type='l10n_do_accounting.ncf_export_client', product=export_product)
    inv('out_invoice', 'Cliente Local A', 300.0,
        TAXES['tax_0_sale'], 'Venta exenta (Art. 343)')
    inv('out_invoice', 'Cliente Local B', 700.0,
        TAXES['tax_18_sale_depreciable'], 'Venta activo depreciable Cat. 2')
    inv('out_invoice', 'Ministerio de Obras (Estado)', 1000.0,
        TAXES['tax_18_sale'] + TAXES['ret_itbis_sale_state'],
        'Venta al Estado (retiene 30% del ITBIS)')
    # Compras — NCF del suplidor manual (B01) o interno (B11/B17)
    inv('in_invoice', 'Proveedor Bienes SRL', 400.0,
        TAXES['tax_18_purch'], 'Compra local de bienes 18%', ncf='B0100000101')
    inv('in_invoice', 'Proveedor Servicios SRL', 200.0,
        TAXES['tax_18_purch_serv'], 'Servicio deducible 18%', ncf='B0100000102')
    inv('in_invoice', 'Aduanas DGA', 100.0,
        TAXES['tax_18_importation'], 'Importación de bienes')
    inv('in_invoice', 'Juan Pérez (persona física)', 250.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_person'],
        'Servicio profesional PF (ret. 100% ITBIS R293-11)')
    inv('in_invoice', 'Fundación Esperanza (ENL)', 150.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_nonprofit'],
        'Servicio ENL (ret. 100% ITBIS N01-11)', ncf='B0100000103')
    inv('in_invoice', 'Seguridad Total SRL', 350.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_security'],
        'Servicio de seguridad (ret. 100% ITBIS N07-09)', ncf='B0100000104')
    inv('in_invoice', 'Consultores Asociados SRL', 600.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_30_tax_moral'],
        'Servicio profesional sociedad (ret. 30% ITBIS N02-05)', ncf='B0100000105')
    inv('in_invoice', 'Colmado Don José (RST)', 800.0,
        TAXES['tax_18_purch'] + TAXES['ret_100_tax_rst_18'],
        'Compra a RST gravada 18% (ret. 100%)', ncf='B0100000106')
    inv('in_invoice', 'Panadería La Espiga (RST)', 500.0,
        TAXES['tax_16_purch'] + TAXES['ret_100_tax_rst_16'],
        'Compra a RST gravada 16% (ret. 100%)', ncf='B0100000107')
    inv('in_invoice', 'Productor Informal', 900.0,
        TAXES['tax_18_purch'] + TAXES['ret_itbis_purch_receipt_18'],
        'Comprobante de compras 18% (ret. 100% N05-19)')
    print(f"[seed] Mayo 2026: {posted_in(MAY_FROM, MAY_TO)} facturas posteadas.")

# ══════════════ JUNIO 2026 — cobertura completa de casillas ═════════════════
if posted_in(JUN_FROM, JUN_TO):
    print(f"[seed] Junio: ya hay {posted_in(JUN_FROM, JUN_TO)} facturas; no se duplica.")
else:
    inv = lambda *a, **kw: create_invoice(*a, inv_date=JUN_DATE, **kw)
    # Ventas gravadas por tasa (casillas 11-15 / 16-20)
    inv('out_invoice', 'Cliente Local A', 1000.0,
        TAXES['tax_18_sale'], 'Venta gravada 18%')
    inv('out_invoice', 'Cliente Local B', 500.0,
        TAXES['tax_16_sale'], 'Venta gravada 16%')
    inv('out_invoice', 'Cliente Local A', 400.0,
        TAXES['tax_9_sale'], 'Venta gravada 9% (L690-16)')
    inv('out_invoice', 'Cliente Local B', 300.0,
        TAXES['tax_8_sale'], 'Venta gravada 8% (L690-16)')
    inv('out_invoice', 'Cliente Local B', 700.0,
        TAXES['tax_18_sale_depreciable'], 'Venta activo depreciable Cat. 3')
    # Ventas no gravadas (casillas 2-8)
    inv('out_invoice', 'Cliente Exterior', 2000.0,
        TAXES['tax_0_sale_export_goods'], 'Exportación de bienes',
        doc_type='l10n_do_accounting.ncf_export_client', product=export_product)
    inv('out_invoice', 'Cliente Exterior', 1500.0,
        TAXES['tax_0_sale_export_services'], 'Exportación de servicios (Art. 344)')
    inv('out_invoice', 'Cliente Local A', 300.0,
        TAXES['tax_0_sale'], 'Venta exenta (Art. 343)')
    inv('out_invoice', 'Zona Franca Industrial SRL', 250.0,
        TAXES['tax_0_sale_destination'], 'Venta exenta por destino (zona franca)')
    inv('out_invoice', 'Cliente Local A', 800.0,
        TAXES['tax_0_sale_construction'], 'Servicio de construcción (no sujeto)')
    inv('out_invoice', 'Cliente Local B', 200.0,
        TAXES['tax_0_sale_commissions'], 'Comisión por venta de exentos (no sujeta)')
    inv('out_invoice', 'Cliente Local A', 350.0,
        TAXES['tax_0_sale_goods_exempt'], 'Venta bienes exentos (Párr. III/IV Art. 343)')
    # Retenciones que nos hacen (casilla 30)
    inv('out_invoice', 'Ministerio de Obras (Estado)', 1000.0,
        TAXES['tax_18_sale'] + TAXES['ret_itbis_sale_state'],
        'Venta al Estado (retiene 30% del ITBIS)')
    inv('out_invoice', 'Consumidor Final', 500.0,
        TAXES['tax_18_sale'] + TAXES['ret_itbis_sale_card'],
        'Venta con tarjeta (ret. 2% ITBIS N08-04)')
    # Compras deducibles (casillas 22-24)
    inv('in_invoice', 'Proveedor Bienes SRL', 400.0,
        TAXES['tax_18_purch'], 'Compra local de bienes 18%', ncf='B0100000201')
    inv('in_invoice', 'Proveedor Servicios SRL', 200.0,
        TAXES['tax_18_purch_serv'], 'Servicio deducible 18%', ncf='B0100000202')
    inv('in_invoice', 'Aduanas DGA', 100.0,
        TAXES['tax_18_importation'], 'Importación de bienes')
    # Retenciones que hacemos (sección A completa)
    inv('in_invoice', 'Juan Pérez (persona física)', 250.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_person'],
        'Servicio profesional PF (ret. 100% ITBIS R293-11)')
    inv('in_invoice', 'Fundación Esperanza (ENL)', 150.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_nonprofit'],
        'Servicio ENL (ret. 100% ITBIS N01-11)', ncf='B0100000203')
    inv('in_invoice', 'Seguridad Total SRL', 350.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_security'],
        'Servicio de seguridad (ret. 100% ITBIS N07-09)', ncf='B0100000204')
    inv('in_invoice', 'Consultores Asociados SRL', 600.0,
        TAXES['tax_18_purch_serv'] + TAXES['ret_30_tax_moral'],
        'Servicio profesional sociedad (ret. 30% ITBIS N02-05)', ncf='B0100000205')
    inv('in_invoice', 'Colmado Don José (RST)', 800.0,
        TAXES['tax_18_purch'] + TAXES['ret_100_tax_rst_18'],
        'Compra a RST gravada 18% (ret. 100%)', ncf='B0100000206')
    inv('in_invoice', 'Panadería La Espiga (RST)', 500.0,
        TAXES['tax_16_purch'] + TAXES['ret_100_tax_rst_16'],
        'Compra a RST gravada 16% (ret. 100%)', ncf='B0100000207')
    inv('in_invoice', 'Productor Informal', 900.0,
        TAXES['tax_18_purch'] + TAXES['ret_itbis_purch_receipt_18'],
        'Comprobante de compras 18% (ret. 100% N05-19)')
    inv('in_invoice', 'Vendedora Informal 16%', 600.0,
        TAXES['tax_16_purch'] + TAXES['ret_itbis_purch_receipt_16'],
        'Comprobante de compras 16% (ret. 100% N05-19)')
    print(f"[seed] Junio 2026: {posted_in(JUN_FROM, JUN_TO)} facturas posteadas.")

env.cr.commit()

# ── NCF asignados ────────────────────────────────────────────────────────────
period_moves = env['account.move'].search([
    ('company_id', '=', company.id), ('state', '=', 'posted'),
    ('invoice_date', '>=', MAY_FROM), ('invoice_date', '<=', JUN_TO),
], order='invoice_date, move_type desc, id')
print("\n=== Comprobantes fiscales (mayo + junio 2026) ===")
for m in period_moves:
    print(f"  {str(m.invoice_date)}  {m.name:22s} {m.l10n_do_fiscal_number or '(sin NCF)':14s} "
          f"{(m.l10n_latam_document_type_id.name or ''):22.22s} "
          f"{m.partner_id.name:30.30s} {m.amount_untaxed:>10,.2f}")

# ── Cálculo y verificación de casillas ───────────────────────────────────────
report = env.ref('l10n_do_it1_report.report_it1').with_company(company)


def compute_casillas(date_from, date_to):
    options = report.get_options({
        'selected_variant_id': report.id,
        'date': {'date_from': str(date_from), 'date_to': str(date_to),
                 'mode': 'range', 'filter': 'custom'},
        'unfold_all': True,
    })
    totals = next(iter(report._compute_expression_totals_for_each_column_group(
        report.line_ids.expression_ids, options).values()))
    casillas = {
        expr.report_line_id.code: vals['value']
        for expr, vals in totals.items()
        if expr.report_line_id.code and expr.label == 'balance'
    }
    return options, casillas


def verify(casillas, expected, label):
    print(f"\n=== IT-1 {label} — casillas calculadas vs. esperadas ===")
    failures = 0
    for code in sorted(casillas, key=lambda c: (len(c), c)):
        val = casillas[code]
        if code in expected:
            ok = abs(val - expected[code]) < 0.005
            mark = 'OK ' if ok else '** DIFIERE (esperado %.2f)' % expected[code]
            failures += 0 if ok else 1
            print(f"  {code:10s} {val:>12,.2f}  {mark}")
        else:
            print(f"  {code:10s} {val:>12,.2f}")
    missing = [c for c in expected if c not in casillas]
    if missing:
        failures += len(missing)
        print(f"  ** Casillas esperadas ausentes: {missing}")
    print(f"[verificación {label}] "
          f"{'TODAS LAS CASILLAS OK' if not failures else '%d DIFERENCIAS' % failures}")
    return failures


def ensure_carryover(options, date_to, c34, target_month):
    existing = env['account.report.external.value'].search_count([
        ('company_id', '=', company.id), ('date', '=', date_to),
    ])
    if not existing:
        report._generate_carryover_external_values(options)
        env.cr.commit()
        print(f"[carryover] Casilla 34 ({c34:,.2f}) → casilla 29 de {target_month}.")
    else:
        print(f"[carryover] {target_month}: ya existía; no se regenera.")


EXPECTED_MAY = {
    'IT1_1': 5500.00, 'IT1_2': 2000.00, 'IT1_3': 0.00, 'IT1_4': 300.00,
    'IT1_5': 0.00, 'IT1_6': 0.00, 'IT1_7': 0.00, 'IT1_8': 0.00,
    'IT1_9': 2300.00, 'IT1_10': 3200.00,
    'IT1_11': 2000.00, 'IT1_12': 500.00, 'IT1_13': 0.00, 'IT1_14': 0.00,
    'IT1_15': 700.00,
    'IT1_16': 360.00, 'IT1_17': 80.00, 'IT1_18': 0.00, 'IT1_19': 0.00,
    'IT1_20': 126.00, 'IT1_21': 566.00,
    'IT1_22': 458.00, 'IT1_23': 279.00, 'IT1_24': 18.00, 'IT1_25': 755.00,
    'IT1_26': 0.00, 'IT1_27': 189.00, 'IT1_29': 0.00, 'IT1_30': 54.00,
    'IT1_33': 0.00, 'IT1_34': 243.00, 'IT1_38': 0.00,
    'IT1_A39': 250.00, 'IT1_A40': 150.00, 'IT1_A41': 400.00,
    'IT1_A42': 350.00, 'IT1_A43': 600.00,
    'IT1_A44': 800.00, 'IT1_A45': 500.00, 'IT1_A46': 1300.00,
    'IT1_A47': 900.00, 'IT1_A48': 0.00, 'IT1_A49': 900.00,
    'IT1_A50': 72.00, 'IT1_A51': 63.00, 'IT1_A52': 32.40,
    'IT1_A53': 144.00, 'IT1_A54': 80.00, 'IT1_A55': 224.00,
    'IT1_A56': 162.00, 'IT1_A57': 0.00, 'IT1_A58': 162.00,
    'IT1_A59': 0.00, 'IT1_A60': 553.40, 'IT1_A61': 0.00, 'IT1_A62': 553.40,
    'IT1_A63': 0.00, 'IT1_B64': 0.00, 'IT1_B65': 0.00, 'IT1_B66': 0.00,
    'IT1_C67': 553.40, 'IT1_68': 553.40,
}

EXPECTED_JUN = {
    # II. Ingresos
    'IT1_1': 9800.00,
    'IT1_2': 2000.00, 'IT1_3': 1500.00, 'IT1_4': 300.00, 'IT1_5': 250.00,
    'IT1_6': 800.00, 'IT1_7': 200.00, 'IT1_8': 350.00, 'IT1_9': 5400.00,
    'IT1_10': 4400.00,
    'IT1_11': 2500.00, 'IT1_12': 500.00, 'IT1_13': 400.00, 'IT1_14': 300.00,
    'IT1_15': 700.00,
    # III. Liquidación
    'IT1_16': 450.00, 'IT1_17': 80.00, 'IT1_18': 36.00, 'IT1_19': 24.00,
    'IT1_20': 126.00, 'IT1_21': 716.00,
    'IT1_22': 554.00, 'IT1_23': 279.00, 'IT1_24': 18.00, 'IT1_25': 851.00,
    'IT1_26': 0.00, 'IT1_27': 135.00,
    'IT1_29': 243.00,                      # carryover de mayo
    'IT1_30': 64.00,                       # 54 Estado + 10 tarjetas (2% de 90)
    'IT1_33': 0.00, 'IT1_34': 442.00,      # 135 + 243 + 64
    'IT1_38': 0.00,
    # A. Retenciones a terceros
    'IT1_A39': 250.00, 'IT1_A40': 150.00, 'IT1_A41': 400.00,
    'IT1_A42': 350.00, 'IT1_A43': 600.00,
    'IT1_A44': 800.00, 'IT1_A45': 500.00, 'IT1_A46': 1300.00,
    'IT1_A47': 900.00, 'IT1_A48': 600.00, 'IT1_A49': 1500.00,
    'IT1_A50': 72.00, 'IT1_A51': 63.00, 'IT1_A52': 32.40,
    'IT1_A53': 144.00, 'IT1_A54': 80.00, 'IT1_A55': 224.00,
    'IT1_A56': 162.00, 'IT1_A57': 96.00, 'IT1_A58': 258.00,
    'IT1_A59': 0.00, 'IT1_A60': 649.40, 'IT1_A61': 0.00, 'IT1_A62': 649.40,
    'IT1_A63': 0.00, 'IT1_B64': 0.00, 'IT1_B65': 0.00, 'IT1_B66': 0.00,
    'IT1_C67': 649.40, 'IT1_68': 649.40,
}

failures = 0

options_may, casillas_may = compute_casillas(MAY_FROM, MAY_TO)
failures += verify(casillas_may, EXPECTED_MAY, 'mayo 2026')
ensure_carryover(options_may, MAY_TO, casillas_may.get('IT1_34', 0), 'junio')

options_jun, casillas_jun = compute_casillas(JUN_FROM, JUN_TO)
failures += verify(casillas_jun, EXPECTED_JUN, 'junio 2026')
ensure_carryover(options_jun, JUN_TO, casillas_jun.get('IT1_34', 0), 'julio')

_, casillas_jul = compute_casillas(date(2026, 7, 1), date(2026, 7, 31))
print(f"\n[carryover] Casilla 29 en julio 2026 = {casillas_jul.get('IT1_29', 0):,.2f} "
      f"(esperado {casillas_jun.get('IT1_34', 0):,.2f})")

if failures:
    raise SystemExit(1)

print("\nListo. UI: http://localhost:8090 (db: %s, admin/admin)" % env.cr.dbname)
print("Contabilidad > Reportes > Declaración de Impuestos > variante IT-1")
print("Períodos con data: mayo 2026 (escenario manual §8) y junio 2026 "
      "(cobertura completa). Casillas 28/31/32/35-37/61/64-66 son de entrada "
      "manual en el reporte.")
'''


def run(cmd, **kw):
    print(f"[cmd] {' '.join(cmd[:6])} ...")
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

    # 1. Crear DB e instalar módulos (sin demo data)
    result = run(["docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn",
                  "--stop-after-init", "--no-http", "--without-demo=all",
                  "-i", MODULES])
    if result.returncode != 0:
        print("[error] instalación falló"); sys.exit(1)

    # 2. Sembrar datos + calcular casillas vía odoo shell
    result = run(["docker", "exec", "-i", CONTAINER, "odoo", "shell",
                  "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn", "--no-http"],
                 input=SEED_SCRIPT.encode())
    if result.returncode != 0:
        print("[error] seed falló"); sys.exit(1)

    print(f"\n[done] DB '{DB_NAME}' lista.")


if __name__ == "__main__":
    main()
