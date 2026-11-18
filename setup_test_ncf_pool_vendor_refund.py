#!/usr/bin/env python3
"""
Repro: la nota de crédito de proveedor (in_refund) recibe un e-NCF fuera de
rango autorizado, por lo que la DGII la rechaza.

Caso real (WENI GAS, SRL — staging odoo-wenigas-staging-36590123):

    BILL/2026/2271   (E) Compras Electrónica     E410000000188   posted
    RBILL/2026/0090  (E) Nota de Crédito Elec.   E340009896401   cancel
                     l10n_do_ecf_send_state = delivered_refused

Causa: `l10n_do_document_pools` (NCF Sequence Manager) solo crea/busca el pool
de secuencias por (journal_id, l10n_latam_document_type_id). Los diarios de
compra NUNCA reciben un tipo de documento de nota de crédito
(`account_journal._l10n_do_create_document_types` excluye `credit_note` en
diarios `purchase`), pero una nota de crédito de proveedor SÍ puede/debe usar
E34 (el rango es del contribuyente, no del diario). Resultado:

    move.l10n_do_journal_document_type_id == False
      → `_l10n_do_get_last_fiscal_sequence` no aplica el filtro de rango
      → cae al MAX global del tipo de documento (l10n_do_accounting)
      → toma el número más alto que exista en E34 (rangos viejos, números
        heredados) y suma 1 → e-NCF fuera de todo rango autorizado.

Escenario sembrado (compañía FARMACIA ECF RD SRL, emisora de e-CF):

    Diario de ventas  INV : pool E34 viejo 900-984 (agotado) → NC = E340000000900
                            pool E34 vigente 25-899 (valid)  → NC = E340000000025, 26
    Diario de compras BILL: pool E41 120-371 (valid), SIN pool E34
                            factura E41 = E410000000120 → se revierte

    Nota de crédito de proveedor esperada : dentro de 25-899 (E340000000027)
    Nota de crédito de proveedor con bug  : E340000000901 (fuera de rango)

Uso:
    python3 setup_test_ncf_pool_vendor_refund.py --reset   # clona DB + módulos
    python3 setup_test_ncf_pool_vendor_refund.py           # solo re-siembra

Requisitos: contenedor lfernandez_v17 arriba y DB plantilla `test_do_ncf_ecf`
(la crea setup_test_do_ncf_ecf.py) con l10n_do_accounting instalado.
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_ncf_pool_refund"
TEMPLATE_DB = "test_do_ncf_ecf"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
MODULES = "l10n_do_document_pools"

SEED_SCRIPT = r'''
env = env  # noqa: odoo shell provides env

from odoo import fields

DO = env.ref('base.do')
DOC_E31 = env.ref('l10n_do_accounting.ecf_fiscal_client')
DOC_E34 = env.ref('l10n_do_accounting.ecf_credit_note_client')
DOC_E41 = env.ref('l10n_do_accounting.ecf_informal_supplier')

company = env['res.company'].search([('name', '=', 'FARMACIA ECF RD SRL')], limit=1)
assert company, 'falta la compañía e-CF en la DB plantilla'
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


def set_pool(journal, document_type, start, end, state, auth):
    """Rango autorizado (pool) del tipo de documento en el diario."""
    row = pool(journal, document_type)
    assert row, 'no existe tipo de documento %s en %s' % (
        document_type.doc_code_prefix, journal.code)
    row.write({
        'sequence_start': start,
        'sequence_end': end,
        'state': state,
        'auth_number': auth,
        'l10n_do_ncf_expiration_date': fields.Date.to_date('2027-12-31'),
    })
    return row


# ─── 1. Diarios: ventas (ya existe) y compras con documentos fiscales ────────
journal_sale = Journal.search(
    [('type', '=', 'sale'), ('company_id', '=', company.id)], limit=1)
if not journal_sale.l10n_latam_use_documents:
    journal_sale.l10n_latam_use_documents = True
journal_sale._l10n_do_create_document_types()

journal_purchase = Journal.search(
    [('type', '=', 'purchase'), ('company_id', '=', company.id)], limit=1)
if not journal_purchase:
    journal_purchase = Journal.create({
        'name': 'Facturas de proveedor RD',
        'code': 'BILLD',
        'type': 'purchase',
        'company_id': company.id,
        'l10n_latam_use_documents': True,
    })
elif not journal_purchase.l10n_latam_use_documents:
    journal_purchase.l10n_latam_use_documents = True
journal_purchase._l10n_do_create_document_types()

# ─── 2. Terceros ─────────────────────────────────────────────────────────────
def get_partner(name, vat, payer_type):
    partner = Partner.search([('name', '=', name)], limit=1)
    if not partner:
        partner = Partner.create({
            'name': name,
            'vat': vat,
            'l10n_do_dgii_tax_payer_type': payer_type,
            'country_id': DO.id,
        })
    partner.l10n_do_dgii_tax_payer_type = payer_type
    return partner


customer = get_partner('ITERATIVO SRL', '131566332', 'taxpayer')
# Suplidor informal (sin NCF propio): sus facturas se registran con E41 y las
# emite la propia compañía, igual que BILL/2026/2271 del caso real.
supplier = get_partner('FRANCISCO ROSARIO (INFORMAL)', '05400674841', 'non_payer')

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
            'product_id': product.id,
            'quantity': 1,
            'price_unit': price,
            'tax_ids': [(5, 0, 0)],
        })],
    })
    move.l10n_latam_document_type_id = document_type
    return move


# ─── 3. Rango E34 viejo (900-984): deja un número heredado alto ──────────────
set_pool(journal_sale, DOC_E34, 900, 984, 'valid', 'A900984')
legacy_cn = new_move('out_refund', journal_sale, customer, DOC_E34)
legacy_cn.action_post()
legacy_number = legacy_cn.l10n_do_fiscal_number

# ─── 4. Rango E34 vigente (25-899) ──────────────────────────────────────────
set_pool(journal_sale, DOC_E34, 25, 899, 'valid', 'A25899')
sale_cn_1 = new_move('out_refund', journal_sale, customer, DOC_E34)
sale_cn_1.action_post()
sale_cn_2 = new_move('out_refund', journal_sale, customer, DOC_E34)
sale_cn_2.action_post()

# ─── 5. Factura de compra E41 y su reversión (nota de crédito E34) ───────────
set_pool(journal_purchase, DOC_E41, 120, 371, 'valid', 'A120371')
bill = new_move('in_invoice', journal_purchase, supplier, DOC_E41, price=6000.0)
bill.action_post()

reversal = env['account.move.reversal'].with_company(company).create({
    'move_ids': [(6, 0, bill.ids)],
    'journal_id': journal_purchase.id,
    'reason': 'Suplidor registrado en DGII',
    'l10n_do_ecf_modification_code': '1',
})
reversal.reverse_moves()
vendor_cn = bill.reversal_move_id
# La compañía es emisora de e-CF: la nota de crédito del E41 es un E34.
vendor_cn.l10n_latam_document_type_id = DOC_E34
vendor_cn.action_post()

env.cr.commit()

# ─── 6. Resultado ───────────────────────────────────────────────────────────
e34_sale_pool = pool(journal_sale, DOC_E34)
e34_purchase_pool = pool(journal_purchase, DOC_E34)
in_range = (
    e34_sale_pool.sequence_start
    <= vendor_cn.l10n_do_sequence_number
    <= e34_sale_pool.sequence_end
)

print('')
print('=' * 78)
print(' DB: %s   compañía: %s (e-CF)' % (env.cr.dbname, company.name))
print('=' * 78)
print(' Rango E34 autorizado vigente (diario %s) : %s-%s  próximo=%s' % (
    journal_sale.code, e34_sale_pool.sequence_start,
    e34_sale_pool.sequence_end, e34_sale_pool.l10n_do_next_sequence))
print(' Pool E34 en el diario de compras %s      : %s' % (
    journal_purchase.code, e34_purchase_pool.id or 'NO EXISTE'))
print('-' * 78)
print(' NC de venta con rango viejo 900-984  : %s  (%s)' % (
    legacy_number, legacy_cn.name))
print(' NC de venta rango vigente 25-899     : %s  (%s)' % (
    sale_cn_1.l10n_do_fiscal_number, sale_cn_1.name))
print(' NC de venta rango vigente 25-899     : %s  (%s)' % (
    sale_cn_2.l10n_do_fiscal_number, sale_cn_2.name))
print(' Factura de compra E41                : %s  (%s)' % (
    bill.l10n_do_fiscal_number, bill.name))
print('-' * 78)
print(' NOTA DE CRÉDITO DE PROVEEDOR         : %s  (%s)' % (
    vendor_cn.l10n_do_fiscal_number, vendor_cn.name))
print(' Tipo de documento                    : %s' % (
    vendor_cn.l10n_latam_document_type_id.name))
print(' Pool asignado al movimiento          : %s' % (
    vendor_cn.l10n_do_journal_document_type_id.display_name
    if vendor_cn.l10n_do_journal_document_type_id else 'False  → sin control de rango'))
print(' Reversión de                         : %s (%s)' % (
    bill.name, vendor_cn.l10n_do_origin_ncf))
print('=' * 78)
print(' [%s] la NC de proveedor cae dentro del rango autorizado %s-%s' % (
    'OK' if in_range else 'FALLA', e34_sale_pool.sequence_start,
    e34_sale_pool.sequence_end))
print(' [%s] la NC de proveedor continúa la serie E34 de la compañía' % (
    'OK' if vendor_cn.l10n_do_sequence_number == sale_cn_2.l10n_do_sequence_number + 1
    else 'FALLA'))
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
    args = parser.parse_args()

    if args.reset:
        for db in (TEMPLATE_DB, DB_NAME):
            psql(
                "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                f"WHERE datname='{db}' AND pid <> pg_backend_pid();"
            )
        psql(f"DROP DATABASE IF EXISTS {DB_NAME};")
        result = psql(f"CREATE DATABASE {DB_NAME} TEMPLATE {TEMPLATE_DB};")
        if result.returncode != 0:
            print("[error] clonar la DB falló")
            sys.exit(1)
        result = run([
            "docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
            "--http-port", "8072", "--no-http", "--stop-after-init",
            "--log-level", "warn", "-u", "l10n_do_accounting", "-i", MODULES,
        ])
        if result.returncode != 0:
            print("[error] instalación de módulos falló")
            sys.exit(1)

    result = run(
        ["docker", "exec", "-i", CONTAINER, "odoo", "shell", "-d", DB_NAME, *DB_ARGS,
         "--http-port", "8072", "--no-http", "--log-level", "warn"],
        input=SEED_SCRIPT.encode(),
    )
    if result.returncode != 0:
        print("[error] la siembra falló")
        sys.exit(1)


if __name__ == "__main__":
    main()
