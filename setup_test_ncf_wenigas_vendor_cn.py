#!/usr/bin/env python3
"""
Repro del caso WENI GAS: la nota de crédito de proveedor (in_refund) sobre un
comprobante de compra autoemitido (E41) recibe un e-NCF fuera del rango
autorizado y la DGII lo rechaza.

Estado real reproducido (prod WeniGas, verificado 2026-08-26):

    pool E34 vigente (diario de ventas)      : 25-974, valid
    diario de compras                        : SIN pool E34
    filas E34 con manual_document_number='f' fuera de rango:
        E340000000991  (serie propia vieja de compras)
        E340009896399  (envenenada por PR #1013 el 2026-07-23)

    BILL   (E) Compras Electrónica  E410000000120  posted
    RBILL  (E) Nota de Crédito      E340009896400  <-- fuera de rango

Mecánica: `_l10n_do_get_last_fiscal_sequence_domain` suelta los filtros
move_type/journal en refunds (correcto: la DGII autoriza UN rango E34 por RNC),
así que ventas y compras comparten el contador. El único filtro que acota es el
clamp de rango del pool, y ese solo se aplica cuando el movimiento tiene
`l10n_do_journal_document_type_id`. El diario de compras nunca recibe pool E34
(`account_journal._l10n_do_create_document_types` excluye credit_note en
diarios purchase, por diseño) => sin clamp => MAX global => 9896399 + 1.

Uso:
    python3 setup_test_ncf_wenigas_vendor_cn.py --reset   # clona DB + módulos
    python3 setup_test_ncf_wenigas_vendor_cn.py           # solo re-siembra
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_ncf_wenigas"
TEMPLATE_DB = "test_do_ncf_ecf"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
MODULES = "l10n_do_document_pools"

SEED_SCRIPT = r'''
from odoo import fields

DO = env.ref('base.do')
DOC_E31 = env.ref('l10n_do_accounting.ecf_fiscal_client')
DOC_E34 = env.ref('l10n_do_accounting.ecf_credit_note_client')
DOC_E41 = env.ref('l10n_do_accounting.ecf_informal_supplier')

RANGE_START, RANGE_END = 25, 974
LEGACY_OWN = 'E340000000991'      # serie propia vieja de compras, fuera de rango
POISONED = 'E340009896399'        # numero heredado del NCF del suplidor (PR #1013)
SUPPLIER_CN = 'E340009896398'     # NCF de nota de credito del suplidor (manual)

company = env['res.company'].search([('name', '=', 'FARMACIA ECF RD SRL')], limit=1)
assert company, 'falta la compania e-CF en la DB plantilla'
company.l10n_do_sequence_manager = True
company.l10n_do_ecf_issuer = True
env = env(context=dict(env.context, allowed_company_ids=[company.id]))
env.user.company_ids |= company
env.user.company_id = company

Journal = env['account.journal'].with_company(company)
Move = env['account.move'].with_company(company)
Partner = env['res.partner'].with_company(company)
DocType = env['l10n_do.account.journal.document_type'].sudo()


def pool(journal, document_type):
    return DocType.search([
        ('journal_id', '=', journal.id),
        ('l10n_latam_document_type_id', '=', document_type.id),
    ], limit=1)


def set_pool(journal, document_type, start, end, auth):
    row = pool(journal, document_type)
    assert row, 'no existe tipo de documento %s en %s' % (
        document_type.doc_code_prefix, journal.code)
    row.write({
        'sequence_start': start,
        'sequence_end': end,
        'state': 'valid',
        'auth_number': auth,
        'l10n_do_first_sequence': False,
        'l10n_do_ncf_expiration_date': fields.Date.to_date('2027-12-31'),
    })
    return row


journal_sale = Journal.search(
    [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
if not journal_sale.l10n_latam_use_documents:
    journal_sale.l10n_latam_use_documents = True
journal_sale._l10n_do_create_document_types()

journal_purchase = Journal.search(
    [('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
if not journal_purchase:
    journal_purchase = Journal.create({
        'name': 'Facturas de proveedor RD', 'code': 'BILLD', 'type': 'purchase',
        'company_id': company.id, 'l10n_latam_use_documents': True,
    })
if not journal_purchase.l10n_latam_use_documents:
    journal_purchase.l10n_latam_use_documents = True
journal_purchase._l10n_do_create_document_types()

# El fix (PR #1124) apunta el diario de compras al diario de ventas que si
# tiene pools de nota de credito. Con --no-fix se deja vacio para reproducir
# el bug original.
journal_purchase.l10n_do_credit_note_sequence_journal_id = (
    journal_sale if __SET_CN_JOURNAL__ else False
)


def get_partner(name, vat, payer_type):
    partner = Partner.search([('name', '=', name)], limit=1)
    if not partner:
        partner = Partner.create({
            'name': name, 'vat': vat, 'country_id': DO.id,
            'l10n_do_dgii_tax_payer_type': payer_type,
        })
    partner.l10n_do_dgii_tax_payer_type = payer_type
    return partner


customer = get_partner('ITERATIVO SRL', '131566332', 'taxpayer')
supplier_formal = get_partner('SUPLIDOR FORMAL SRL', '130862346', 'taxpayer')
supplier_informal = get_partner('FRANCISCO ROSARIO (INFORMAL)', '05400674841', 'non_payer')

product = env['product.product'].search([('default_code', '=', 'ACET-500')], limit=1)
assert product, 'falta el producto de la DB plantilla'


def new_move(move_type, journal, partner, document_type, price=1000.0):
    move = Move.create({
        'move_type': move_type,
        'journal_id': journal.id,
        'partner_id': partner.id,
        'invoice_date': fields.Date.context_today(Move),
        'l10n_latam_document_type_id': document_type.id,
        'invoice_line_ids': [(0, 0, {
            'product_id': product.id, 'quantity': 1,
            'price_unit': price, 'tax_ids': [(5, 0, 0)],
        })],
    })
    move.l10n_latam_document_type_id = document_type
    return move


def force_number(move, number):
    """Reescribe el e-NCF ya asignado (siembra del estado danado en prod)."""
    move.sudo().write({'l10n_do_fiscal_number': number})
    move.flush_recordset()


# 1. Rango E34 autorizado vigente en el diario de ventas
e34_pool = set_pool(journal_sale, DOC_E34, RANGE_START, RANGE_END, 'A25974')

# 2. Dos notas de credito de venta dentro de rango -> 25 y 26
sale_cn_1 = new_move('out_refund', journal_sale, customer, DOC_E34)
sale_cn_1.action_post()
sale_cn_2 = new_move('out_refund', journal_sale, customer, DOC_E34)
sale_cn_2.action_post()

# 3. Filas E34 manual='f' FUERA de rango (serie vieja + fila envenenada #1013)
legacy = new_move('out_refund', journal_sale, customer, DOC_E34)
legacy.action_post()
force_number(legacy, LEGACY_OWN)

poisoned = new_move('out_refund', journal_sale, customer, DOC_E34)
poisoned.action_post()
force_number(poisoned, POISONED)

# 4. Nota de credito DEL SUPLIDOR (manual='t'): numero alto tecleado
formal_bill = new_move('in_invoice', journal_purchase, supplier_formal, DOC_E31, price=5000.0)
formal_bill.l10n_latam_document_number = 'E310000000001'
formal_bill.action_post()
formal_reversal = env['account.move.reversal'].with_company(company).create({
    'move_ids': [(6, 0, formal_bill.ids)],
    'journal_id': journal_purchase.id,
    'reason': 'NC del suplidor',
})
formal_reversal.reverse_moves()
supplier_cn = formal_bill.reversal_move_id
supplier_cn.l10n_latam_document_type_id = DOC_E34
supplier_cn.l10n_latam_document_number = SUPPLIER_CN
supplier_cn.action_post()

# 5. Comprobante de compra autoemitido (E41) + su reversion (E34)
set_pool(journal_purchase, DOC_E41, 120, 371, 'A120371')
bill = new_move('in_invoice', journal_purchase, supplier_informal, DOC_E41, price=6000.0)
bill.action_post()

reversal = env['account.move.reversal'].with_company(company).create({
    'move_ids': [(6, 0, bill.ids)],
    'journal_id': journal_purchase.id,
    'reason': 'Anulacion comprobante de compra',
    'l10n_do_ecf_modification_code': '1',
})
reversal.reverse_moves()
vendor_cn = bill.reversal_move_id
vendor_cn.l10n_latam_document_type_id = DOC_E34
vendor_cn.action_post()

env.cr.commit()

e34_purchase_pool = pool(journal_purchase, DOC_E34)
number = vendor_cn.l10n_do_sequence_number
in_range = RANGE_START <= number <= RANGE_END
expected = sale_cn_2.l10n_do_sequence_number + 1

print('')
print('=' * 78)
print(' DB %s  |  compania %s' % (env.cr.dbname, company.name))
print('=' * 78)
print(' Rango E34 autorizado (diario %-6s)  : %s-%s' % (
    journal_sale.code, RANGE_START, RANGE_END))
print(' Pool E34 en diario de compras %-8s : %s' % (
    journal_purchase.code, e34_purchase_pool.id or 'NO EXISTE'))
print('-' * 78)
print(' NC venta 1 (en rango)                  : %s' % sale_cn_1.l10n_do_fiscal_number)
print(' NC venta 2 (en rango)                  : %s' % sale_cn_2.l10n_do_fiscal_number)
print(' Serie propia vieja, fuera de rango     : %s  manual=%s' % (
    legacy.l10n_do_fiscal_number, legacy.l10n_latam_manual_document_number))
print(' Fila envenenada PR #1013               : %s  manual=%s' % (
    poisoned.l10n_do_fiscal_number, poisoned.l10n_latam_manual_document_number))
print(' NC del suplidor (tecleada)             : %s  manual=%s' % (
    supplier_cn.l10n_do_fiscal_number, supplier_cn.l10n_latam_manual_document_number))
print(' Comprobante de compra E41              : %s' % bill.l10n_do_fiscal_number)
print('-' * 78)
print(' NOTA DE CREDITO DE PROVEEDOR           : %s   (%s)' % (
    vendor_cn.l10n_do_fiscal_number, vendor_cn.name))
print(' pool asignado al movimiento            : %s' % (
    vendor_cn.l10n_do_journal_document_type_id.display_name
    if vendor_cn.l10n_do_journal_document_type_id else 'False -> sin clamp de rango'))
print(' diario de NC del diario de compras     : %s' % (
    journal_purchase.l10n_do_credit_note_sequence_journal_id.code or 'vacio'))
print('=' * 78)
print(' [%s] cae dentro del rango autorizado %s-%s' % (
    'OK   ' if in_range else 'FALLA', RANGE_START, RANGE_END))
print(' [%s] continua la serie E34 de la compania (esperado %s, obtenido %s)' % (
    'OK   ' if number == expected else 'FALLA', expected, number))
print('=' * 78)
print('')
'''


def run(cmd, **kw):
    print("[run]", " ".join(cmd[:8]), "...")
    return subprocess.run(cmd, **kw)


def psql(sql):
    return run(["docker", "exec", "odoo-db", "psql", "-U", "odoo", "-d", "postgres", "-c", sql])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="re-clone DB from template")
    parser.add_argument("--no-fix", action="store_true",
                        help="deja l10n_do_credit_note_sequence_journal_id vacio (reproduce el bug)")
    args = parser.parse_args()

    seed = SEED_SCRIPT.replace("__SET_CN_JOURNAL__", "False" if args.no_fix else "True")

    if args.reset:
        for db in (TEMPLATE_DB, DB_NAME):
            psql(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname='{db}' AND pid <> pg_backend_pid();"
            )
        psql(f"DROP DATABASE IF EXISTS {DB_NAME};")
        if psql(f"CREATE DATABASE {DB_NAME} TEMPLATE {TEMPLATE_DB};").returncode != 0:
            print("[error] clonar la DB fallo")
            sys.exit(1)
        result = run([
            "docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
            "--http-port", "8072", "--no-http", "--stop-after-init",
            "--log-level", "warn", "-u", "l10n_do_accounting", "-i", MODULES,
        ])
        if result.returncode != 0:
            print("[error] instalacion de modulos fallo")
            sys.exit(1)

    result = run(
        ["docker", "exec", "-i", CONTAINER, "odoo", "shell", "-d", DB_NAME, *DB_ARGS,
         "--http-port", "8072", "--no-http", "--log-level", "warn"],
        input=seed.encode(),
    )
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
