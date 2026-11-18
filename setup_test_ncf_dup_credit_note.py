#!/usr/bin/env python3
"""
Repro: la nota de credito de CLIENTE y la de PROVEEDOR reciben el MISMO e-NCF.

Mecanismo:

  1. `l10n_do_journal_document_type_id` (el pool) es un compute ALMACENADO que
     depende de journal_id/partner_id/company_id/move_type, NO de
     `l10n_latam_document_type_id`. La NC de proveedor nace de la reversion de
     una E41, el usuario le cambia el tipo a E34 y el pool NO se recalcula:
     queda en False. Sin pool no hay clamp de rango, asi que
     `_l10n_do_get_last_fiscal_sequence` cae al MAX global del tipo E34.
     El fallback agregado en 65775efa (`l10n_do_credit_note_sequence_journal_id`)
     nunca llega a aplicarse por esto.

  2. `l10n_do.account.journal.document_type.l10n_do_first_sequence` busca
     movimientos con `journal_id = doc_type.journal_id`, o sea el DIARIO DE
     VENTAS dueño del pool E34. La NC de proveedor vive en el diario de
     compras: es invisible. Mientras ninguna NC de venta haya consumido el
     rango nuevo, `first_sequence` sigue True y
     `l10n_do_document_pools._l10n_do_get_last_fiscal_sequence` fuerza el
     resultado a `prefix + (sequence_start - 1)`, ignorando el numero que la
     NC de proveedor ya se llevo.

  3. El indice unico no lo detecta: la NC de cliente cae en
     `account_move_unique_l10n_do_fiscal_number_sales` y la de proveedor en
     `account_move_unique_l10n_do_fiscal_number_purchase_internal`, dos
     indices parciales disjuntos. Sin 23505 no hay reintento en
     `_l10n_do_set_fiscal_sequence` y el duplicado se persiste.

Escenario sembrado (compania FARMACIA ECF RD SRL, emisora de e-CF).
Rangos contiguos, que es como los autoriza la DGII:

    Diario de ventas  INV  : pool E34 viejo 23-24  -> se consume completo
                             pool E34 nuevo 25-899 -> sin usar (first_sequence=True)
    Diario de compras BILL : pool E41 120-371, SIN pool E34,
                             l10n_do_credit_note_sequence_journal_id = INV

    1. NC de cliente x2 agotan 23 y 24
    2. Se abre el rango 25-899
    3. Factura de compra E41 -> se revierte -> NC de PROVEEDOR tipo E34
       pool=False -> MAX global E34 = 24 -> E340000000025
    4. NC de CLIENTE: pool valido, first_sequence=True -> forzado a 24
       -> E340000000025  <-- DUPLICADO

Uso:
    python3 setup_test_ncf_dup_credit_note.py --reset   # clona DB + modulos
    python3 setup_test_ncf_dup_credit_note.py           # solo re-siembra

Requisitos: contenedor lfernandez_v17 arriba y DB plantilla `test_do_ncf_ecf`
(la crea setup_test_do_ncf_ecf.py) con l10n_do_accounting instalado.
"""

import argparse
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_ncf_dup_cn"
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

DOC_E34 = env.ref('l10n_do_accounting.ecf_credit_note_client')
DOC_E41 = env.ref('l10n_do_accounting.ecf_informal_supplier')
DO = env.ref('base.do')

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


def set_pool(journal, document_type, start, end, auth):
    row = pool(journal, document_type)
    assert row, 'no existe tipo de documento %s en %s' % (
        document_type.doc_code_prefix, journal.code)
    row.write({
        'sequence_start': start,
        'sequence_end': end,
        'state': 'valid',
        'auth_number': auth,
        'l10n_do_ncf_expiration_date': fields.Date.to_date('2027-12-31'),
    })
    return row


# --- 1. Diarios -------------------------------------------------------------
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
if not journal_purchase.l10n_latam_use_documents:
    journal_purchase.l10n_latam_use_documents = True
journal_purchase._l10n_do_create_document_types()
# Campo nuevo (65775efa): el diario de compras toma el pool de NC del de ventas
journal_purchase.l10n_do_credit_note_sequence_journal_id = journal_sale

# --- 2. Terceros ------------------------------------------------------------
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


def vendor_credit_note(reason):
    """NC de proveedor: reversión de una factura E41 emitida por la compañía."""
    set_pool(journal_purchase, DOC_E41, 120, 371, 'A120371')
    bill = new_move('in_invoice', journal_purchase, supplier, DOC_E41, price=6000.0)
    bill.action_post()
    reversal = env['account.move.reversal'].with_company(company).create({
        'move_ids': [(6, 0, bill.ids)],
        'journal_id': journal_purchase.id,
        'reason': reason,
        'l10n_do_ecf_modification_code': '1',
    })
    reversal.reverse_moves()
    cn = bill.reversal_move_id
    # El usuario elige E34 en el formulario (esta en
    # l10n_latam_available_document_type_ids). El pool NO se recalcula.
    cn.l10n_latam_document_type_id = DOC_E34
    cn.flush_recordset()
    before = (pool_e34().l10n_do_first_sequence, pool_e34().l10n_do_next_sequence,
              cn.l10n_do_journal_document_type_id.id or False)
    cn.action_post()
    return bill, cn, before


e34_pool = set_pool(journal_sale, DOC_E34, 23, 24, 'A2324')
trace = []


def pool_e34():
    e34_pool.invalidate_recordset(['l10n_do_first_sequence', 'l10n_do_next_sequence'])
    return e34_pool


def snapshot(label, move, before):
    trace.append((
        label,
        move.l10n_do_fiscal_number,
        move.move_type,
        move.journal_id.code,
        before[2],
        before[0],
        before[1],
    ))


def sale_credit_note():
    cn = new_move('out_refund', journal_sale, customer, DOC_E34)
    cn.flush_recordset()
    before = (pool_e34().l10n_do_first_sequence, pool_e34().l10n_do_next_sequence,
              cn.l10n_do_journal_document_type_id.id or False)
    cn.action_post()
    return cn, before


# --- 3. Rango viejo 23-24: se consume completo con NC de venta --------------
legacy_1, before_l1 = sale_credit_note()
snapshot('NC CLIENTE viejo', legacy_1, before_l1)
legacy_2, before_l2 = sale_credit_note()
snapshot('NC CLIENTE viejo', legacy_2, before_l2)

# --- 4. Rango nuevo contiguo 25-899, todavia sin usar en ventas -------------
set_pool(journal_sale, DOC_E34, 25, 899, 'A25899')

# --- 5. NC de proveedor primero, luego NC de cliente ------------------------
bill_1, vendor_cn_1, before_v1 = vendor_credit_note('Suplidor registrado en DGII')
snapshot('NC PROVEEDOR', vendor_cn_1, before_v1)

sale_cn_1, before_s1 = sale_credit_note()
snapshot('NC CLIENTE', sale_cn_1, before_s1)

env.cr.commit()

# --- 4. Resultado -----------------------------------------------------------
print('')
print('=' * 96)
print(' DB: %s   compania: %s   pool E34 vigente %s-%s en diario %s' % (
    env.cr.dbname, company.name, e34_pool.sequence_start,
    e34_pool.sequence_end, journal_sale.code))
print('=' * 96)
print(' %-16s %-16s %-11s %-6s %-8s %-14s %s' % (
    'documento', 'e-NCF', 'move_type', 'diario', 'pool_id',
    'first_seq_prev', 'next_seq_prev'))
print('-' * 96)
for row in trace:
    print(' %-16s %-16s %-11s %-6s %-8s %-14s %s' % row)
print('-' * 96)
print(' Factura de compra E41 : %s' % bill_1.l10n_do_fiscal_number)
print('-' * 96)

env.cr.execute("""
    SELECT l10n_do_fiscal_number, count(*) AS veces,
           array_agg(move_type ORDER BY id) AS tipos,
           array_agg(name ORDER BY id) AS nombres
    FROM account_move
    WHERE state = 'posted'
      AND l10n_do_fiscal_number LIKE 'E34%'
    GROUP BY l10n_do_fiscal_number
    HAVING count(*) > 1
    ORDER BY l10n_do_fiscal_number
""")
dups = env.cr.fetchall()
if dups:
    print(' e-NCF E34 DUPLICADOS EN LA MISMA COMPANIA:')
    for number, times, types, names in dups:
        print('   %s  x%s  %s  %s' % (number, times, list(types), list(names)))
else:
    print(' sin e-NCF E34 duplicados')
print('=' * 96)
print(' [%s] la NC de cliente y la de proveedor NO comparten e-NCF' % (
    'OK' if not dups else 'FALLA'))
print('=' * 96)
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
        input=SEED_SCRIPT.encode(),
    )
    if result.returncode != 0:
        print("[error] la siembra fallo")
        sys.exit(1)


if __name__ == "__main__":
    main()
