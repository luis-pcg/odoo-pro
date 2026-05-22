#!/usr/bin/env python3
"""
Setup script: l10n_do_report_invoices
Creates DB, installs modules, configures DO company, sets up NCF sequences/pools,
and seeds test data to validate Dominican invoice report format.

Usage:
    python3 setup_test_l10n_do_invoices.py
    python3 setup_test_l10n_do_invoices.py --reset          # drop & recreate DB
    python3 setup_test_l10n_do_invoices.py --skip-db-create # seed only

Requirements:
    - Odoo container running (lfernandez_v17)
    - Odoo accessible at http://localhost:8090
"""

import argparse
import subprocess
import sys
import time
import xmlrpc.client
from datetime import date

# ─── CONFIG ────────────────────────────────────────────────────────────────────
ODOO_URL = "http://localhost:8090"
DB_NAME = "test_l10n_do_invoices"
MASTER_PASSWD = "admin"
ADMIN_LOGIN = "admin"
ADMIN_PASSWD = "admin"
DEMO_DATA = False
LANG = "es_DO"

MODULES_TO_INSTALL = [
    "l10n_do_accounting",
    "l10n_do_document_pools",
    "l10n_do_report_invoices",
]

# NCF pools to create per document type ncf_type
# auth_number is arbitrary for test; sequence 1-50
POOLS_CONFIG = [
    {
        "ncf_type": "fiscal",
        "auth_number": "TEST-FISCAL-001",
        "sequence_start": 1,
        "sequence_end": 50,
    },
    {
        "ncf_type": "consumer",
        "auth_number": "TEST-CONSUMER-001",
        "sequence_start": 1,
        "sequence_end": 50,
    },
    {
        "ncf_type": "credit_note",
        "auth_number": "TEST-CREDIT-001",
        "sequence_start": 1,
        "sequence_end": 50,
    },
    {
        "ncf_type": "debit_note",
        "auth_number": "TEST-DEBIT-001",
        "sequence_start": 1,
        "sequence_end": 50,
    },
]


# ─── XMLRPC HELPERS ────────────────────────────────────────────────────────────
def get_db_proxy():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/db", allow_none=True)


def get_common_proxy():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)


def get_object_proxy():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)


def authenticate(db, login, password):
    uid = get_common_proxy().authenticate(db, login, password, {})
    if not uid:
        raise RuntimeError(f"Auth failed: {db}/{login}")
    return uid


def call(obj, uid, model, method, *args, **kwargs):
    return obj.execute_kw(DB_NAME, uid, ADMIN_PASSWD, model, method, list(args), kwargs)


def search_read(obj, uid, model, domain, fields, limit=None):
    kw = {"fields": fields}
    if limit:
        kw["limit"] = limit
    return call(obj, uid, model, "search_read", domain, **kw)


def find_or_create(obj, uid, model, domain, vals):
    result = search_read(obj, uid, model, domain, ["id"], limit=1)
    if result:
        return result[0]["id"]
    return call(obj, uid, model, "create", vals)


# ─── STEP 1: CREATE DATABASE ───────────────────────────────────────────────────
def create_database(reset=False):
    db_proxy = get_db_proxy()
    existing = db_proxy.list()

    if DB_NAME in existing:
        if reset:
            print(f"[reset] Dropping {DB_NAME}...")
            db_proxy.drop(MASTER_PASSWD, DB_NAME)
            time.sleep(2)
        else:
            print(f"[skip] DB '{DB_NAME}' exists. Use --reset to recreate.")
            return False

    print(f"[create] Creating database '{DB_NAME}'...")
    db_proxy.create_database(
        MASTER_PASSWD,
        DB_NAME,
        DEMO_DATA,
        LANG,
        ADMIN_PASSWD,
        ADMIN_LOGIN,
        "DO",  # Dominican Republic
    )
    for i in range(30):
        try:
            uid = authenticate(DB_NAME, ADMIN_LOGIN, ADMIN_PASSWD)
            if uid:
                break
        except Exception:
            pass
        print(f"  waiting for DB... ({i+1}/30)")
        time.sleep(3)
    print(f"[ok] Database '{DB_NAME}' created.")
    return True


# ─── STEP 2: INSTALL MODULES ───────────────────────────────────────────────────
CONTAINER_NAME = "lfernandez_v17"
ODOO_BIN = "odoo"
# DB connection args for odoo-bin (entrypoint normally injects these)
ODOO_DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]


def _module_installed(obj, uid, module_name):
    mods = search_read(
        obj, uid, "ir.module.module",
        [("name", "=", module_name)], ["state"], limit=1,
    )
    return mods and mods[0]["state"] == "installed"


def install_modules(obj, uid):
    """Install via odoo-bin inside container to avoid Python namespace issues."""
    to_install = [m for m in MODULES_TO_INSTALL if not _module_installed(obj, uid, m)]

    if not to_install:
        print("[skip] All modules already installed.")
        return

    modules_arg = ",".join(to_install)
    print(f"[install] Installing via odoo-bin: {modules_arg}")

    cmd = [
        "docker", "exec", CONTAINER_NAME,
        ODOO_BIN,
        "--database", DB_NAME,
        "--init", modules_arg,
        "--stop-after-init",
        "--no-http",
    ] + ODOO_DB_ARGS
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"[error] odoo-bin stderr:\n{result.stderr[-3000:]}")
        raise RuntimeError(f"Module installation failed (exit {result.returncode})")

    print(f"[ok] Modules installed: {modules_arg}")

    # Restart container so the running HTTP server picks up the new modules
    print(f"[restart] Restarting container '{CONTAINER_NAME}' to reload registry...")
    subprocess.run(["docker", "restart", CONTAINER_NAME], check=True, capture_output=True)

    print("[wait] Waiting for Odoo to be ready after restart...")
    for i in range(60):
        try:
            uid_check = authenticate(DB_NAME, ADMIN_LOGIN, ADMIN_PASSWD)
            if uid_check:
                print(f"  [ok] Odoo ready (uid={uid_check})")
                return uid_check
        except Exception:
            pass
        print(f"  waiting... ({i+1}/60)")
        time.sleep(5)
    raise RuntimeError("Odoo did not come back after container restart.")


# ─── STEP 3: CONFIGURE COMPANY ────────────────────────────────────────────────
def setup_company(obj, uid):
    print("[setup] Configuring company for Dominican Republic...")

    company = search_read(obj, uid, "res.company", [], ["id", "name", "vat"], limit=1)
    if not company:
        raise RuntimeError("No company found.")
    company_id = company[0]["id"]

    call(obj, uid, "res.company", "write", [company_id], {
        "vat": "131793898",  # test RNC
        "currency_id": _get_dop_currency(obj, uid),
    })
    # l10n_do_dgii_tax_payer_type lives on res.partner, not res.company
    partner_ids = search_read(
        obj, uid, "res.company", [("id", "=", company_id)], ["partner_id"], limit=1,
    )
    if partner_ids:
        partner_id = partner_ids[0]["partner_id"][0]
        call(obj, uid, "res.partner", "write", [partner_id], {
            "l10n_do_dgii_tax_payer_type": "taxpayer",
        })

    # Install DO chart of accounts if not already done
    coa = search_read(
        obj, uid, "account.account",
        [("company_id", "=", company_id)], ["id"], limit=1,
    )
    if not coa:
        print("  [install] Setting up DO chart of accounts...")
        try:
            call(obj, uid, "res.company", "action_reload_chart_of_accounts", [company_id])
        except Exception as e:
            print(f"  [warn] CoA setup: {e}")

    print(f"  [ok] Company id={company_id} configured (RNC=131793898, taxpayer)")
    return company_id


def _get_dop_currency(obj, uid):
    currencies = search_read(
        obj, uid, "res.currency", [("name", "=", "DOP")], ["id"], limit=1,
    )
    if currencies:
        return currencies[0]["id"]
    # Activate DOP if it exists but inactive
    currencies = search_read(
        obj, uid, "res.currency",
        [("name", "=", "DOP"), ("active", "=", False)], ["id"], limit=1,
    )
    if currencies:
        call(obj, uid, "res.currency", "write", [currencies[0]["id"]], {"active": True})
        return currencies[0]["id"]
    return False


# ─── STEP 4: CONFIGURE CUSTOMER INVOICE JOURNAL ───────────────────────────────
def setup_journal(obj, uid):
    print("[setup] Configuring customer invoice journal...")

    journals = search_read(
        obj, uid, "account.journal",
        [("type", "=", "sale"), ("l10n_latam_use_documents", "=", True)],
        ["id", "name"], limit=1,
    )

    if not journals:
        # Check if sale journal exists without l10n_latam flag
        journals = search_read(
            obj, uid, "account.journal",
            [("type", "=", "sale")],
            ["id", "name"], limit=1,
        )
        if journals:
            journal_id = journals[0]["id"]
            call(obj, uid, "account.journal", "write", [journal_id],
                 {"l10n_latam_use_documents": True})
            print(f"  [ok] Enabled l10n_latam_use_documents on journal id={journal_id}")
        else:
            raise RuntimeError("No sale journal found. Verify l10n_do_accounting is installed.")
    else:
        journal_id = journals[0]["id"]

    print(f"  [ok] Journal id={journal_id} '{journals[0]['name']}'")
    return journal_id


# ─── STEP 5: CONFIGURE NCF SEQUENCES ─────────────────────────────────────────
# Pattern from l10n_do_accounting/tests/common.py:
#   write auth_number, sequence_start, sequence_end, l10n_do_ncf_expiration_date
#   then write state='valid' directly on l10n_do.account.journal.document_type
def setup_sequences(obj, uid, journal_id):
    print("[setup] Configuring NCF sequences on journal...")

    doc_types = search_read(
        obj, uid, "l10n_do.account.journal.document_type",
        [("journal_id", "=", journal_id)],
        ["id", "l10n_do_ncf_type", "state"],
    )

    if not doc_types:
        # Re-trigger document type creation
        call(obj, uid, "account.journal", "write", [journal_id],
             {"l10n_latam_use_documents": True})
        doc_types = search_read(
            obj, uid, "l10n_do.account.journal.document_type",
            [("journal_id", "=", journal_id)],
            ["id", "l10n_do_ncf_type", "state"],
        )

    print(f"  found {len(doc_types)} document types")
    expiration_date = date(date.today().year + 2, 12, 31).isoformat()

    # Index by ncf_type
    ncf_map = {dt["l10n_do_ncf_type"]: dt for dt in doc_types if dt.get("l10n_do_ncf_type")}

    for pool_cfg in POOLS_CONFIG:
        ncf_type = pool_cfg["ncf_type"]
        dt = ncf_map.get(ncf_type)
        if not dt:
            print(f"  [skip] ncf_type='{ncf_type}' not in journal")
            continue
        if dt.get("state") == "valid":
            print(f"  [skip] ncf_type='{ncf_type}' already valid")
            continue

        call(obj, uid, "l10n_do.account.journal.document_type", "write", [dt["id"]], {
            "auth_number": pool_cfg["auth_number"],
            "sequence_start": pool_cfg["sequence_start"],
            "sequence_end": pool_cfg["sequence_end"],
            "l10n_do_ncf_expiration_date": expiration_date,
            "state": "valid",
        })
        print(f"  [ok] ncf_type='{ncf_type}' → state=valid seq {pool_cfg['sequence_start']}-{pool_cfg['sequence_end']}")

    return doc_types


# ─── STEP 7: CREATE TEST PARTNER ──────────────────────────────────────────────
def setup_partner(obj, uid):
    print("[setup] Creating test customer...")

    country_id = search_read(
        obj, uid, "res.country", [("code", "=", "DO")], ["id"], limit=1,
    )[0]["id"]

    partner_id = find_or_create(
        obj, uid, "res.partner",
        [("vat", "=", "101892256"), ("company_type", "=", "company")],
        {
            "name": "Empresa Test DO S.R.L.",
            "company_type": "company",
            "vat": "101892256",
            "l10n_do_dgii_tax_payer_type": "taxpayer",
            "country_id": country_id,
            "customer_rank": 1,
            "email": "test@empresa-do.com",
        }
    )
    print(f"  [ok] Partner id={partner_id} (RNC=101892256, taxpayer)")
    return partner_id


# ─── STEP 8: CREATE TEST INVOICE ──────────────────────────────────────────────
def create_test_invoice(obj, uid, partner_id, journal_id):
    print("[setup] Creating test invoice...")

    # Get a product (any)
    product = search_read(
        obj, uid, "product.product",
        [("sale_ok", "=", True), ("type", "!=", "service")],
        ["id", "name"], limit=1,
    )
    if not product:
        product = search_read(
            obj, uid, "product.product",
            [("sale_ok", "=", True)],
            ["id", "name"], limit=1,
        )

    product_id = product[0]["id"] if product else False

    # Get fiscal document type (B01 for taxpayer customer)
    doc_types = search_read(
        obj, uid, "l10n_do.account.journal.document_type",
        [("journal_id", "=", journal_id), ("l10n_do_ncf_type", "=", "fiscal")],
        ["l10n_latam_document_type_id"], limit=1,
    )
    doc_type_id = doc_types[0]["l10n_latam_document_type_id"][0] if doc_types else False

    invoice_vals = {
        "move_type": "out_invoice",
        "partner_id": partner_id,
        "journal_id": journal_id,
        "invoice_line_ids": [],
    }
    if doc_type_id:
        invoice_vals["l10n_latam_document_type_id"] = doc_type_id

    if product_id:
        invoice_vals["invoice_line_ids"] = [
            (0, 0, {
                "product_id": product_id,
                "quantity": 2.0,
                "price_unit": 5000.0,
                "name": "Producto de Prueba",
            })
        ]
    else:
        invoice_vals["invoice_line_ids"] = [
            (0, 0, {
                "name": "Servicio de Prueba",
                "quantity": 1.0,
                "price_unit": 10000.0,
            })
        ]

    invoice_id = call(obj, uid, "account.move", "create", invoice_vals)
    print(f"  [ok] Invoice id={invoice_id} created (draft).")

    # Confirm / post the invoice
    try:
        call(obj, uid, "account.move", "action_post", [invoice_id])
        invoice = search_read(
            obj, uid, "account.move", [("id", "=", invoice_id)],
            ["name", "l10n_do_fiscal_number", "state"], limit=1,
        )[0]
        print(f"  [ok] Invoice posted: name={invoice['name']}, "
              f"NCF={invoice.get('l10n_do_fiscal_number', 'n/a')}, "
              f"state={invoice['state']}")
    except Exception as e:
        print(f"  [warn] Could not post invoice: {e}")
        print(f"         Open invoice id={invoice_id} manually and confirm.")

    return invoice_id


# ─── SUMMARY ──────────────────────────────────────────────────────────────────
def print_summary(invoice_id, journal_id, partner_id):
    print("\n" + "=" * 60)
    print("TEST ENVIRONMENT READY")
    print("=" * 60)
    print(f"  DB:           {DB_NAME}")
    print(f"  URL:          {ODOO_URL}/web?db={DB_NAME}")
    print(f"  Login:        {ADMIN_LOGIN} / {ADMIN_PASSWD}")
    print(f"  Journal:      id={journal_id}")
    print(f"  Partner:      id={partner_id}")
    print(f"  Invoice:      id={invoice_id}")
    print(f"  Invoice URL:  {ODOO_URL}/odoo/accounting/customer-invoices/{invoice_id}")
    print()
    print("VALIDATION STEPS:")
    print("  1. Open invoice → verify NCF assigned (B01XXXXXXXX)")
    print("  2. Print PDF → verify Dominican layout (l10n_do_report_invoices)")
    print("  3. Check: RNC, NCF, customer info, ITBIS totals display correctly")
    print("  4. Test B02 (consumer): create invoice with non-taxpayer partner")
    print("=" * 60)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    global MASTER_PASSWD
    parser = argparse.ArgumentParser(
        description="Setup test DB for l10n_do_report_invoices"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate DB if it exists")
    parser.add_argument("--skip-db-create", action="store_true",
                        help="Skip DB creation, only seed data into existing DB")
    parser.add_argument("--master-password", default=MASTER_PASSWD,
                        help="Odoo master password")
    args = parser.parse_args()
    MASTER_PASSWD = args.master_password

    if not args.skip_db_create:
        created = create_database(reset=args.reset)
        if not created and not args.reset:
            print(f"\nTip: --reset to recreate  |  --skip-db-create to seed only")

    print(f"\n[auth] Connecting to {ODOO_URL}, db={DB_NAME}...")
    uid = authenticate(DB_NAME, ADMIN_LOGIN, ADMIN_PASSWD)
    obj = get_object_proxy()
    print(f"[ok] uid={uid}")

    new_uid = install_modules(obj, uid)
    if new_uid:
        uid = new_uid

    company_id = setup_company(obj, uid)
    journal_id = setup_journal(obj, uid)
    setup_sequences(obj, uid, journal_id)
    partner_id = setup_partner(obj, uid)
    invoice_id = create_test_invoice(obj, uid, partner_id, journal_id)

    print_summary(invoice_id, journal_id, partner_id)


if __name__ == "__main__":
    main()
