#!/usr/bin/env python3
"""
Setup script: l10n_do_it1_report
Crea la DB de prueba, instala el módulo, configura la compañía DO (plan
contable 'do') y siembra las facturas del escenario de validación del IT-1
(mismo escenario numérico que tests/test_it1_report.py y que el manual
docs/manual_calculo_it1.md). Al final imprime las casillas calculadas del
período y genera el carryover de mayo → junio (casilla 34 → 29).

Uso:
    python3 setup_test_it1_report.py            # crea/reusa DB y siembra
    python3 setup_test_it1_report.py --reset    # drop & recreate DB

Requisitos:
    - Contenedor Odoo corriendo (lfernandez_v17), UI en http://localhost:8090
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_it1_mvp"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
PERIOD = "2026-05"  # período a declarar (mayo 2026)

SEED_SCRIPT = r'''
from datetime import date
import json

env = env  # noqa: odoo shell provides env

PERIOD_DATE = date(2026, 5, 15)
DATE_FROM, DATE_TO = date(2026, 5, 1), date(2026, 5, 31)

company = env.ref('base.main_company')
company.country_id = env.ref('base.do')

# Cargar plan contable dominicano (crea impuestos con las etiquetas del IT-1).
if company.chart_template != 'do':
    env['account.chart.template'].try_loading('do', company=company, install_demo=False)
    env.cr.commit()

env = env(context=dict(env.context, allowed_company_ids=[company.id]))
ct = env['account.chart.template'].with_company(company)

TAXES = {
    'tax_18_sale': ct.ref('tax_18_sale'),
    'tax_16_sale': ct.ref('tax_16_sale'),
    'tax_0_sale': ct.ref('tax_0_sale'),
    'tax_18_sale_depreciable': ct.ref('tax_18_sale_depreciable'),
    'tax_0_sale_export_goods': ct.ref('tax_0_sale_export_goods'),
    'ret_itbis_sale_state': ct.ref('ret_itbis_sale_state'),
    'tax_18_purch': ct.ref('tax_18_purch'),
    'tax_16_purch': ct.ref('tax_16_purch'),
    'tax_18_purch_serv': ct.ref('tax_18_purch_serv'),
    'tax_18_importation': ct.ref('tax_18_importation'),
    'ret_100_tax_person': ct.ref('ret_100_tax_person'),
    'ret_100_tax_nonprofit': ct.ref('ret_100_tax_nonprofit'),
    'ret_100_tax_security': ct.ref('ret_100_tax_security'),
    'ret_30_tax_moral': ct.ref('ret_30_tax_moral'),
    'ret_100_tax_rst_18': ct.ref('ret_100_tax_rst_18'),
    'ret_100_tax_rst_16': ct.ref('ret_100_tax_rst_16'),
    'ret_itbis_purch_receipt_18': ct.ref('ret_itbis_purch_receipt_18'),
}

Partner = env['res.partner']


def get_partner(name):
    partner = Partner.search([('name', '=', name)], limit=1)
    return partner or Partner.create({'name': name, 'country_id': env.ref('base.do').id})


def create_invoice(move_type, partner_name, amount, taxes, label):
    journal_type = 'sale' if move_type == 'out_invoice' else 'purchase'
    journal = env['account.journal'].search(
        [('type', '=', journal_type), ('company_id', '=', company.id)], limit=1)
    move = env['account.move'].create({
        'move_type': move_type,
        'partner_id': get_partner(partner_name).id,
        'invoice_date': PERIOD_DATE,
        'journal_id': journal.id,
        'invoice_line_ids': [(0, 0, {
            'name': label,
            'quantity': 1.0,
            'price_unit': amount,
            'account_id': journal.default_account_id.id,
            'tax_ids': [(6, 0, taxes.ids)],
        })],
    })
    move.action_post()
    return move


already = env['account.move'].search_count([
    ('company_id', '=', company.id), ('state', '=', 'posted'),
    ('invoice_date', '>=', DATE_FROM), ('invoice_date', '<=', DATE_TO),
])
if already:
    print(f"[seed] Ya existen {already} facturas posteadas en el período; no se duplica.")
else:
    # ── Ventas (mayo 2026) ────────────────────────────────────────────────
    create_invoice('out_invoice', 'Cliente Local A', 1000.0,
                   TAXES['tax_18_sale'], 'Venta gravada 18%')
    create_invoice('out_invoice', 'Cliente Local B', 500.0,
                   TAXES['tax_16_sale'], 'Venta gravada 16%')
    create_invoice('out_invoice', 'Cliente Exterior', 2000.0,
                   TAXES['tax_0_sale_export_goods'], 'Exportación de bienes')
    create_invoice('out_invoice', 'Cliente Local A', 300.0,
                   TAXES['tax_0_sale'], 'Venta exenta (Art. 343)')
    create_invoice('out_invoice', 'Cliente Local B', 700.0,
                   TAXES['tax_18_sale_depreciable'], 'Venta activo depreciable Cat. 2')
    create_invoice('out_invoice', 'Ministerio de Obras (Estado)', 1000.0,
                   TAXES['tax_18_sale'] + TAXES['ret_itbis_sale_state'],
                   'Venta al Estado (retiene 30% del ITBIS)')

    # ── Compras (mayo 2026) ───────────────────────────────────────────────
    create_invoice('in_invoice', 'Proveedor Bienes SRL', 400.0,
                   TAXES['tax_18_purch'], 'Compra local de bienes 18%')
    create_invoice('in_invoice', 'Proveedor Servicios SRL', 200.0,
                   TAXES['tax_18_purch_serv'], 'Servicio deducible 18%')
    create_invoice('in_invoice', 'Aduanas DGA', 100.0,
                   TAXES['tax_18_importation'], 'Importación de bienes')
    create_invoice('in_invoice', 'Juan Pérez (persona física)', 250.0,
                   TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_person'],
                   'Servicio profesional PF (ret. 100% ITBIS R293-11)')
    create_invoice('in_invoice', 'Fundación Esperanza (ENL)', 150.0,
                   TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_nonprofit'],
                   'Servicio ENL (ret. 100% ITBIS N01-11)')
    create_invoice('in_invoice', 'Seguridad Total SRL', 350.0,
                   TAXES['tax_18_purch_serv'] + TAXES['ret_100_tax_security'],
                   'Servicio de seguridad (ret. 100% ITBIS N07-09)')
    create_invoice('in_invoice', 'Consultores Asociados SRL', 600.0,
                   TAXES['tax_18_purch_serv'] + TAXES['ret_30_tax_moral'],
                   'Servicio profesional sociedad (ret. 30% ITBIS N02-05)')
    create_invoice('in_invoice', 'Colmado Don José (RST)', 800.0,
                   TAXES['tax_18_purch'] + TAXES['ret_100_tax_rst_18'],
                   'Compra a RST gravada 18% (ret. 100%)')
    create_invoice('in_invoice', 'Panadería La Espiga (RST)', 500.0,
                   TAXES['tax_16_purch'] + TAXES['ret_100_tax_rst_16'],
                   'Compra a RST gravada 16% (ret. 100%)')
    create_invoice('in_invoice', 'Productor Informal', 900.0,
                   TAXES['tax_18_purch'] + TAXES['ret_itbis_purch_receipt_18'],
                   'Comprobante de compras 18% (ret. 100% N05-19)')
    print("[seed] 16 facturas creadas y posteadas (mayo 2026).")

env.cr.commit()

# ── Calcular casillas del IT-1 para mayo 2026 ────────────────────────────────
report = env.ref('l10n_do_it1_report.report_it1').with_company(company)
options = report.get_options({
    'selected_variant_id': report.id,
    'date': {'date_from': str(DATE_FROM), 'date_to': str(DATE_TO),
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
print("\n=== IT-1 mayo 2026 — casillas calculadas ===")
for code in sorted(casillas, key=lambda c: (len(c), c)):
    print(f"  {code:10s} {casillas[code]:>12,.2f}")

# ── Carryover: casilla 34 (mayo) → casilla 29 (junio) ────────────────────────
existing_carryover = env['account.report.external.value'].search_count([
    ('company_id', '=', company.id), ('date', '=', DATE_TO),
])
if not existing_carryover:
    report._generate_carryover_external_values(options)
    env.cr.commit()
    print(f"\n[carryover] Generado: casilla 34 mayo ({casillas.get('IT1_34', 0):,.2f}) "
          f"disponible como casilla 29 en junio 2026.")
else:
    print("\n[carryover] Ya existía para el período; no se regenera.")

options_june = report.get_options({
    'selected_variant_id': report.id,
    'date': {'date_from': '2026-06-01', 'date_to': '2026-06-30',
             'mode': 'range', 'filter': 'custom'},
    'unfold_all': True,
})
totals_june = next(iter(report._compute_expression_totals_for_each_column_group(
    report.line_ids.expression_ids, options_june).values()))
c29 = next((v['value'] for e, v in totals_june.items()
            if e.report_line_id.code == 'IT1_29' and e.label == 'balance'), None)
print(f"[carryover] Casilla 29 en junio 2026 = {c29:,.2f}")
print("\nListo. UI: http://localhost:8090 (db: %s, admin/admin)" % env.cr.dbname)
print("Contabilidad > Reportes > Declaración de Impuestos > variante IT-1")
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

    # 1. Crear DB e instalar módulo (sin demo data)
    result = run(["docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn",
                  "--stop-after-init", "--no-http", "--without-demo=all",
                  "-i", "l10n_do_it1_report"])
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
