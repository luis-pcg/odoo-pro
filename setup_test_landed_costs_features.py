#!/usr/bin/env python3
"""
Setup script: stock_landed_costs_features
Creates a test DB, installs the module, and seeds data to validate:

  1. "Costo en Liquidación"  — renamed final_cost header in Valuation Summary
  2. currency_id column      — always visible in Vendor Bills tab
  3. column_invisible         — company_id / currency_id / target_model hidden
                               in Landed Costs tab
  4. "Default Split Method"  — renamed general_split_method on bills + pre-clearance

Usage:
    python3 setup_test_landed_costs_features.py
    python3 setup_test_landed_costs_features.py --reset          # drop & recreate DB
    python3 setup_test_landed_costs_features.py --skip-db-create # seed only (DB exists)

Requirements:
    - Container lfernandez_v17 running
    - Odoo at http://localhost:8090
"""

import argparse
import subprocess
import sys
import time
import xmlrpc.client
from datetime import date, timedelta

# ─── CONFIG ───────────────────────────────────────────────────────────────────
ODOO_URL     = "http://localhost:8090"
DB_NAME      = "test_landed_costs_features"
MASTER_PASSWD = "strong.password"
ADMIN_LOGIN  = "admin"
ADMIN_PASSWD = "admin"
DEMO_DATA    = False
LANG         = "es_DO"

CONTAINER = "lfernandez_v17"
ODOO_BIN  = "odoo"
DB_ARGS   = ["--db_host", "odoo-db", "--db_port", "5432",
             "--db_user", "odoo", "--db_password", "odoo_password"]

MODULES = ["stock_landed_costs_features", "stock_landed_costs_file"]


# ─── XML-RPC HELPERS ──────────────────────────────────────────────────────────
def _db():     return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/db",     allow_none=True)
def _common(): return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)
def _obj():    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object",  allow_none=True)


def authenticate(db=DB_NAME, login=ADMIN_LOGIN, passwd=ADMIN_PASSWD):
    uid = _common().authenticate(db, login, passwd, {})
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


def get_ref(obj, uid, xmlid):
    """Resolve an xml external id to a record id."""
    parts = xmlid.split(".")
    module, name = parts[0], parts[1]
    res = search_read(obj, uid, "ir.model.data",
                      [("module", "=", module), ("name", "=", name)], ["res_id"], limit=1)
    return res[0]["res_id"] if res else None


# ─── STEP 1: CREATE DATABASE ──────────────────────────────────────────────────
def create_database(reset=False):
    db_proxy = _db()
    existing = db_proxy.list()

    if DB_NAME in existing:
        if reset:
            print(f"[reset] Dropping {DB_NAME}...")
            db_proxy.drop(MASTER_PASSWD, DB_NAME)
            time.sleep(2)
        else:
            print(f"[skip]  DB '{DB_NAME}' exists. Use --reset to recreate.")
            return False

    print(f"[create] Creating database '{DB_NAME}'...")
    db_proxy.create_database(MASTER_PASSWD, DB_NAME, DEMO_DATA, LANG,
                             ADMIN_PASSWD, ADMIN_LOGIN, "DO")
    for i in range(30):
        try:
            if authenticate():
                break
        except Exception:
            pass
        print(f"  waiting for DB... ({i+1}/30)")
        time.sleep(3)
    print(f"[ok] Database '{DB_NAME}' created.")
    return True


# ─── STEP 2: INSTALL MODULES ──────────────────────────────────────────────────
def _module_state(obj, uid, name):
    rows = search_read(obj, uid, "ir.module.module",
                       [("name", "=", name)], ["state"], limit=1)
    return rows[0]["state"] if rows else None


def install_modules(obj, uid):
    to_install = [m for m in MODULES if _module_state(obj, uid, m) != "installed"]
    if not to_install:
        print("[skip]  All modules already installed.")
        return uid

    modules_arg = ",".join(to_install)
    print(f"[install] Installing via odoo-bin: {modules_arg}")

    cmd = ["docker", "exec", CONTAINER, ODOO_BIN,
           "--database", DB_NAME, "--init", modules_arg,
           "--stop-after-init", "--no-http"] + DB_ARGS
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"[error] stderr:\n{result.stderr[-4000:]}")
        raise RuntimeError(f"Install failed (exit {result.returncode})")
    print(f"[ok] Installed: {modules_arg}")

    print(f"[restart] Restarting container '{CONTAINER}'...")
    subprocess.run(["docker", "restart", CONTAINER], check=True, capture_output=True)
    print("[wait] Waiting for Odoo to come back...")
    for i in range(60):
        try:
            new_uid = authenticate()
            if new_uid:
                print(f"  [ok] Odoo ready (uid={new_uid})")
                return new_uid
        except Exception:
            pass
        print(f"  waiting... ({i+1}/60)")
        time.sleep(5)
    raise RuntimeError("Odoo did not restart in time.")


# ─── STEP 3: CONFIGURE COMPANY ────────────────────────────────────────────────
def setup_company(obj, uid):
    print("[setup] Configuring company...")
    company = search_read(obj, uid, "res.company", [], ["id", "partner_id"], limit=1)[0]
    company_id = company["id"]
    partner_id = company["partner_id"][0]

    # Activate DOP
    dop = search_read(obj, uid, "res.currency", [("name", "=", "DOP")], ["id", "active"])
    if dop:
        dop_id = dop[0]["id"]
        if not dop[0]["active"]:
            call(obj, uid, "res.currency", "write", [dop_id], {"active": True})
    else:
        raise RuntimeError("DOP currency not found. Install l10n_do or manually activate DOP.")

    # Activate USD
    usd = search_read(obj, uid, "res.currency", [("name", "=", "USD")], ["id", "active"])
    if usd and not usd[0]["active"]:
        call(obj, uid, "res.currency", "write", [usd[0]["id"]], {"active": True})

    usd_id = usd[0]["id"] if usd else None

    country_do = search_read(obj, uid, "res.country", [("code", "=", "DO")], ["id"], limit=1)
    country_id = country_do[0]["id"] if country_do else None

    call(obj, uid, "res.company", "write", [company_id], {
        "currency_id": dop_id,
        **({"country_id": country_id} if country_id else {}),
    })
    call(obj, uid, "res.partner", "write", [partner_id], {
        **({"country_id": country_id} if country_id else {}),
    })

    print(f"  [ok] Company id={company_id} currency=DOP country=DO")
    return company_id, usd_id


# ─── STEP 4: PRODUCT CATEGORY WITH AVCO + REAL_TIME ─────────────────────────
def setup_product_category(obj, uid):
    print("[setup] Product category (AVCO, real_time)...")

    # Find stock input/output accounts for the category
    input_accs = search_read(obj, uid, "account.account",
                             [("code", "ilike", "1"), ("account_type", "=", "asset_current")],
                             ["id"], limit=1)
    output_accs = search_read(obj, uid, "account.account",
                              [("code", "ilike", "6"), ("account_type", "=", "expense")],
                              ["id"], limit=1)

    categ_id = find_or_create(
        obj, uid, "product.category",
        [("name", "=", "Imported Goods")],
        {
            "name": "Imported Goods",
            "property_cost_method": "average",
            "property_valuation": "real_time",
        }
    )

    write_vals = {
        "property_cost_method": "average",
        "property_valuation": "real_time",
    }
    # Try to set stock accounts if they exist
    if input_accs:
        write_vals["property_stock_account_input_categ_id"] = input_accs[0]["id"]
    if output_accs:
        write_vals["property_stock_account_output_categ_id"] = output_accs[0]["id"]

    call(obj, uid, "product.category", "write", [categ_id], write_vals)
    print(f"  [ok] Category id={categ_id} 'Imported Goods'")
    return categ_id


# ─── STEP 5: STORABLE PRODUCTS ───────────────────────────────────────────────
def create_importable_products(obj, uid, categ_id):
    print("[setup] Creating importable products...")

    uom_unit = search_read(obj, uid, "uom.uom",
                           [("category_id.name", "=", "Unit"), ("uom_type", "=", "reference")],
                           ["id"], limit=1)
    uom_id = uom_unit[0]["id"] if uom_unit else None

    products = [
        {
            "name": "Samsung 55\" Smart TV",
            "type": "product",
            "categ_id": categ_id,
            "standard_price": 35000.0,
            "list_price": 50000.0,
            "weight": 15.0,
            "volume": 0.2,
            **({"uom_id": uom_id, "uom_po_id": uom_id} if uom_id else {}),
        },
        {
            "name": "iPhone 15 128GB",
            "type": "product",
            "categ_id": categ_id,
            "standard_price": 20000.0,
            "list_price": 32000.0,
            "weight": 0.3,
            "volume": 0.001,
            **({"uom_id": uom_id, "uom_po_id": uom_id} if uom_id else {}),
        },
    ]

    product_ids = []
    for p in products:
        pid = find_or_create(
            obj, uid, "product.product",
            [("name", "=", p["name"]), ("type", "=", "product")],
            p,
        )
        product_ids.append(pid)
        print(f"  [ok] Product id={pid} '{p['name']}'")

    return product_ids


# ─── STEP 6: LANDED COST SERVICE PRODUCT ────────────────────────────────────
def create_lc_service_product(obj, uid):
    print("[setup] Creating landed cost service product...")

    # Get landed cost product category (created by module data)
    lc_categ = search_read(obj, uid, "product.category",
                           [("name", "ilike", "landed cost")], ["id"], limit=1)
    lc_categ_id = lc_categ[0]["id"] if lc_categ else None

    # Get stock input account
    stock_input_acc = search_read(
        obj, uid, "account.account",
        [("account_type", "in", ["asset_current", "liability_current"]),
         ("deprecated", "=", False)],
        ["id"], limit=1,
    )
    acc_id = stock_input_acc[0]["id"] if stock_input_acc else None

    prod_id = find_or_create(
        obj, uid, "product.product",
        [("name", "=", "International Freight"), ("landed_cost_ok", "=", True)],
        {
            "name": "International Freight",
            "type": "service",
            "landed_cost_ok": True,
            "standard_price": 1.0,
            "list_price": 1.0,
            **({"categ_id": lc_categ_id} if lc_categ_id else {}),
        }
    )
    print(f"  [ok] LC Service product id={prod_id} 'International Freight'")

    # Find stock_input account: look for accounts used as stock valuation input
    stock_input_acc = search_read(
        obj, uid, "account.account",
        [("code", "ilike", "1"), ("account_type", "=", "asset_current"),
         ("deprecated", "=", False)],
        ["id", "code", "name"], limit=1,
    )
    lc_acc_id = stock_input_acc[0]["id"] if stock_input_acc else acc_id

    return prod_id, lc_acc_id


# ─── STEP 7: VENDOR (FOREIGN SUPPLIER IN USD) ────────────────────────────────
def create_vendors(obj, uid, usd_id):
    print("[setup] Creating vendors...")

    country_us = search_read(obj, uid, "res.country", [("code", "=", "US")], ["id"], limit=1)
    country_us_id = country_us[0]["id"] if country_us else None

    country_do = search_read(obj, uid, "res.country", [("code", "=", "DO")], ["id"], limit=1)
    country_do_id = country_do[0]["id"] if country_do else None

    # Foreign supplier (USD)
    supplier_id = find_or_create(
        obj, uid, "res.partner",
        [("name", "=", "Samsung Electronics Ltd"), ("supplier_rank", ">", 0)],
        {
            "name": "Samsung Electronics Ltd",
            "company_type": "company",
            "supplier_rank": 1,
            "customer_rank": 0,
            **({"country_id": country_us_id} if country_us_id else {}),
            **({"property_purchase_currency_id": usd_id} if usd_id else {}),
        }
    )
    print(f"  [ok] Foreign supplier id={supplier_id} (USD)")

    # Customs agent (DOP)
    customs_id = find_or_create(
        obj, uid, "res.partner",
        [("name", "=", "Agentes Aduanales S.A.")],
        {
            "name": "Agentes Aduanales S.A.",
            "company_type": "company",
            "supplier_rank": 1,
            "customer_rank": 0,
            **({"country_id": country_do_id} if country_do_id else {}),
        }
    )
    print(f"  [ok] Customs agent id={customs_id} (DOP)")

    return supplier_id, customs_id


# ─── STEP 8: STOCK RECEIPT ────────────────────────────────────────────────────
def create_stock_receipt(obj, uid, product_ids, supplier_id):
    print("[setup] Creating and validating stock receipt...")

    uom_unit = search_read(obj, uid, "uom.uom",
                           [("category_id.name", "=", "Unit"), ("uom_type", "=", "reference")],
                           ["id"], limit=1)
    uom_id = uom_unit[0]["id"] if uom_unit else None

    # Find incoming picking type
    in_types = search_read(obj, uid, "stock.picking.type",
                           [("code", "=", "incoming")],
                           ["id", "default_location_src_id", "default_location_dest_id"],
                           limit=1)
    if not in_types:
        raise RuntimeError("No incoming picking type found.")
    ptype = in_types[0]

    # Supplier location
    sup_loc = search_read(obj, uid, "stock.location",
                          [("usage", "=", "supplier")], ["id"], limit=1)
    src_loc_id = sup_loc[0]["id"] if sup_loc else ptype["default_location_src_id"][0]
    dest_loc_id = ptype["default_location_dest_id"][0]

    today = date.today().isoformat()

    moves = []
    qtys = [10, 20]  # 10 TVs, 20 iPhones
    for pid, qty in zip(product_ids, qtys):
        moves.append((0, 0, {
            "product_id": pid,
            "product_uom_qty": qty,
            **({"product_uom": uom_id} if uom_id else {}),
            "location_id": src_loc_id,
            "location_dest_id": dest_loc_id,
            "name": "Test import receipt",
        }))

    picking_id = call(obj, uid, "stock.picking", "create", {
        "picking_type_id": ptype["id"],
        "partner_id": supplier_id,
        "location_id": src_loc_id,
        "location_dest_id": dest_loc_id,
        "move_ids_without_package": moves,
        "scheduled_date": today,
    })
    print(f"  created picking id={picking_id}")

    # Confirm
    call(obj, uid, "stock.picking", "action_confirm", [picking_id])

    # Odoo 17: get demand from stock.move, then set quantity on move.lines
    stock_moves = search_read(obj, uid, "stock.move",
                              [("picking_id", "=", picking_id)],
                              ["id", "product_uom_qty", "move_line_ids"])

    for mv in stock_moves:
        demand = mv["product_uom_qty"]
        ml_ids = mv.get("move_line_ids", [])
        if ml_ids:
            for ml_id in ml_ids:
                call(obj, uid, "stock.move.line", "write", [ml_id], {"quantity": demand})
        else:
            # No move lines yet — create one
            pick_data = search_read(obj, uid, "stock.picking",
                                    [("id", "=", picking_id)],
                                    ["location_id", "location_dest_id"], limit=1)[0]
            mv_data = search_read(obj, uid, "stock.move", [("id", "=", mv["id"])],
                                  ["product_id", "product_uom"], limit=1)[0]
            call(obj, uid, "stock.move.line", "create", {
                "move_id": mv["id"],
                "picking_id": picking_id,
                "product_id": mv_data["product_id"][0],
                "product_uom_id": mv_data["product_uom"][0],
                "quantity": demand,
                "location_id": pick_data["location_id"][0],
                "location_dest_id": pick_data["location_dest_id"][0],
            })

    # Validate picking — may return wizard for backorder
    result = call(obj, uid, "stock.picking", "button_validate", [picking_id])
    if isinstance(result, dict) and result.get("res_model"):
        wizard_model = result["res_model"]
        wizard_id = result.get("res_id")
        if wizard_id:
            # No backorder
            try:
                call(obj, uid, wizard_model, "process_cancel_backorder", [wizard_id])
            except Exception:
                try:
                    call(obj, uid, wizard_model, "process", [wizard_id])
                except Exception as e:
                    print(f"  [warn] Could not close wizard: {e}")

    # Verify picking is done
    pick_state = search_read(obj, uid, "stock.picking",
                             [("id", "=", picking_id)], ["state"], limit=1)
    state = pick_state[0]["state"] if pick_state else "unknown"
    if state == "done":
        print(f"  [ok] Picking id={picking_id} state=done")
    else:
        print(f"  [warn] Picking id={picking_id} state={state} (expected 'done')")

    return picking_id


# ─── STEP 9: VENDOR BILLS ────────────────────────────────────────────────────
def create_vendor_bills(obj, uid, supplier_id, customs_id, lc_prod_id, usd_id):
    print("[setup] Creating vendor bills...")

    # Find purchase journal
    journals = search_read(obj, uid, "account.journal",
                           [("type", "=", "purchase")], ["id"], limit=1)
    if not journals:
        raise RuntimeError("No purchase journal found.")
    journal_id = journals[0]["id"]

    # Find expense account (for bill lines)
    expense_acc = search_read(
        obj, uid, "account.account",
        [("account_type", "=", "expense"), ("deprecated", "=", False)],
        ["id"], limit=1,
    )
    acc_id = expense_acc[0]["id"] if expense_acc else None

    # Use acc_id (expense account) as the line account for landed cost lines
    lc_acc_id = acc_id

    today = date.today().isoformat()

    # Bill 1: USD vendor bill (freight - is_landed_costs_line)
    bill1_vals = {
        "move_type": "in_invoice",
        "partner_id": supplier_id,
        "journal_id": journal_id,
        "invoice_date": today,
        **({"currency_id": usd_id} if usd_id else {}),
        "invoice_line_ids": [(0, 0, {
            "product_id": lc_prod_id,
            "name": "International Freight & Insurance",
            "quantity": 1.0,
            "price_unit": 850.0,
            "is_landed_costs_line": True,
            **({"account_id": lc_acc_id} if lc_acc_id else {}),
        })],
        "general_split_method": "by_current_cost_price",
    }
    bill1_id = call(obj, uid, "account.move", "create", bill1_vals)
    try:
        call(obj, uid, "account.move", "action_post", [bill1_id])
        print(f"  [ok] Bill 1 (USD freight) id={bill1_id} posted")
    except Exception as e:
        print(f"  [warn] Bill 1 could not be posted: {e}")

    # Bill 2: DOP vendor bill (customs - is_landed_costs_line)
    bill2_vals = {
        "move_type": "in_invoice",
        "partner_id": customs_id,
        "journal_id": journal_id,
        "invoice_date": today,
        "invoice_line_ids": [(0, 0, {
            "product_id": lc_prod_id,
            "name": "Customs & Clearance Fees",
            "quantity": 1.0,
            "price_unit": 12500.0,
            "is_landed_costs_line": True,
            **({"account_id": lc_acc_id} if lc_acc_id else {}),
        })],
        "general_split_method": "by_quantity",
    }
    bill2_id = call(obj, uid, "account.move", "create", bill2_vals)
    try:
        call(obj, uid, "account.move", "action_post", [bill2_id])
        print(f"  [ok] Bill 2 (DOP customs) id={bill2_id} posted")
    except Exception as e:
        print(f"  [warn] Bill 2 could not be posted: {e}")

    return bill1_id, bill2_id


# ─── STEP 10: LANDED COST RUN ────────────────────────────────────────────────
def create_landed_cost_run(obj, uid, bill1_id, bill2_id,
                            lc_prod_id, lc_acc_id, picking_id, product_ids):
    print("[setup] Creating Landed Cost Run...")

    today = date.today().isoformat()

    # Create run
    run_id = call(obj, uid, "stock.landed.cost.run", "create", {
        "number": "BL-TEST-001",
        "date_bl": (date.today() - timedelta(days=5)).isoformat(),
        "manifest_ref": "MNF-TEST-001",
        "date": today,
        "vendor_bill_ids": [(4, bill1_id), (4, bill2_id)],
    })
    print(f"  [ok] Run id={run_id} created (draft)")

    # Add pre-clearance product line
    if lc_acc_id:
        preclear_id = call(obj, uid, "stock.landed.cost.product", "create", {
            "run_id": run_id,
            "product_id": lc_prod_id,
            "name": "International Freight FOB",
            "account_id": lc_acc_id,
            "quantity": 1.0,
            "price_unit": 42500.0,
            "general_split_method": "by_current_cost_price",
        })
        print(f"  [ok] Pre-clearance product id={preclear_id} added")
    else:
        print("  [skip] No stock_input account found — skipping pre-clearance line")
        preclear_id = None

    # Generate landed costs from pre-clearance products
    # Note: button_generate_landed_costs returns None — Odoo XML-RPC serialization
    # raises "cannot marshal None" even though the method executed successfully.
    # We check for landed costs existence after the call to confirm it worked.
    if preclear_id:
        try:
            call(obj, uid, "stock.landed.cost.run", "button_generate_landed_costs", [run_id])
            print("  [ok] Landed costs generated")
        except Exception as e:
            if "cannot marshal None" in str(e) or "marshal" in str(e).lower():
                print("  [ok] Landed costs generated (None return — expected)")
            else:
                print(f"  [warn] Generate failed: {e}")
                return run_id, None

    # Get generated landed costs
    lc_ids = search_read(obj, uid, "stock.landed.cost",
                         [("run_id", "=", run_id)], ["id", "state"])
    if not lc_ids:
        print("  [warn] No landed costs generated.")
        return run_id, None

    print(f"  [ok] {len(lc_ids)} landed cost(s) generated")

    # Associate picking to each draft landed cost
    for lc in lc_ids:
        if lc["state"] == "draft":
            try:
                call(obj, uid, "stock.landed.cost", "write", [lc["id"]],
                     {"picking_ids": [(4, picking_id)]})
                print(f"  [ok] Picking linked to LC id={lc['id']}")
            except Exception as e:
                print(f"  [warn] Could not link picking to LC id={lc['id']}: {e}")

    def _none_safe_call(label, *args, **kwargs):
        """Call an Odoo method that may return None (XML-RPC can't serialize None)."""
        try:
            call(*args, **kwargs)
            print(f"  [ok] {label}")
            return True
        except Exception as e:
            if "cannot marshal None" in str(e) or "marshal" in str(e).lower():
                print(f"  [ok] {label} (None return — expected)")
                return True
            print(f"  [warn] {label} failed: {e}")
            return False

    # Compute all
    if not _none_safe_call("Landed costs computed",
                           obj, uid, "stock.landed.cost.run",
                           "compute_landed_cost_all", [run_id]):
        return run_id, lc_ids

    # Validate run
    if _none_safe_call("Run validated",
                       obj, uid, "stock.landed.cost.run",
                       "button_validate", [run_id]):
        run_state = search_read(obj, uid, "stock.landed.cost.run",
                                [("id", "=", run_id)], ["state", "name"], limit=1)[0]
        print(f"  [ok] Run '{run_state['name']}' state={run_state['state']}")

    return run_id, lc_ids


# ─── SUMMARY ──────────────────────────────────────────────────────────────────
def print_summary(run_id, bill1_id, bill2_id, picking_id, product_ids):
    run_url = f"{ODOO_URL}/odoo/inventory/landed-costs-run/{run_id}"
    print()
    print("=" * 65)
    print("  TEST ENVIRONMENT READY")
    print("=" * 65)
    print(f"  DB      : {DB_NAME}")
    print(f"  URL     : {ODOO_URL}/web?db={DB_NAME}")
    print(f"  Login   : {ADMIN_LOGIN} / {ADMIN_PASSWD}")
    print()
    print(f"  Run     : id={run_id}  →  {run_url}")
    print(f"  Bill 1  : id={bill1_id}  (USD — freight)")
    print(f"  Bill 2  : id={bill2_id}  (DOP — customs)")
    print(f"  Picking : id={picking_id}")
    print(f"  Products: {product_ids}")
    print()
    print("WHAT TO VALIDATE:")
    print()
    print("  1. VENDOR BILLS TAB")
    print("     → currency_id column VISIBLE (USD / DOP shown per bill)")
    print("     → 'Default Split Method' column shown ('By Current Cost' / 'By Qty')")
    print()
    print("  2. LANDED COSTS TAB")
    print("     → columns company_id / currency / target_model NOT rendered")
    print("       (column_invisible=True — not in DOM, not toggleable)")
    print()
    print("  3. VALUATION SUMMARY TAB")
    print("     → 'Costo en Liquidación' column header (renamed from 'New Value')")
    print("     → Hover column headers to see help tooltips")
    print("     → Check: former_cost, additional_landed_cost, cost_factor_currency")
    print()
    print("  4. PRE-CLEARANCE TAB")
    print("     → 'Default Split Method' label on column")
    print()
    print("  5. FIELD HELP TEXTS (hover on field labels in form view)")
    print("     → former_cost: 'Total inventory value...'")
    print("     → final_cost:  'Does not represent the product's new permanent unit cost'")
    print("     → account.move.general_split_method: 'Default distribution method...'")
    print()
    print("  TIP: Run not yet validated? Navigate to the Run form and click Validate")
    print("       to go through the full workflow manually.")
    print("=" * 65)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    global MASTER_PASSWD
    parser = argparse.ArgumentParser(
        description="Setup test DB for stock_landed_costs_features"
    )
    parser.add_argument("--reset", action="store_true",
                        help="Drop and recreate DB if it exists")
    parser.add_argument("--skip-db-create", action="store_true",
                        help="Skip DB creation, seed into existing DB")
    parser.add_argument("--master-password", default=MASTER_PASSWD)
    args = parser.parse_args()
    MASTER_PASSWD = args.master_password

    if not args.skip_db_create:
        created = create_database(reset=args.reset)
        if not created and not args.reset:
            print(f"\n  Tip: --reset to recreate  |  --skip-db-create to seed only")

    print(f"\n[auth] Connecting to {ODOO_URL}, db={DB_NAME}...")
    uid = authenticate()
    obj = _obj()
    print(f"[ok] uid={uid}")

    new_uid = install_modules(obj, uid)
    if new_uid and new_uid != uid:
        uid = new_uid
        obj = _obj()

    company_id, usd_id = setup_company(obj, uid)
    categ_id = setup_product_category(obj, uid)
    product_ids = create_importable_products(obj, uid, categ_id)
    lc_prod_id, lc_acc_id = create_lc_service_product(obj, uid)
    supplier_id, customs_id = create_vendors(obj, uid, usd_id)
    picking_id = create_stock_receipt(obj, uid, product_ids, supplier_id)
    bill1_id, bill2_id = create_vendor_bills(
        obj, uid, supplier_id, customs_id, lc_prod_id, usd_id
    )
    run_id, lc_ids = create_landed_cost_run(
        obj, uid, bill1_id, bill2_id, lc_prod_id, lc_acc_id, picking_id, product_ids
    )

    print_summary(run_id, bill1_id, bill2_id, picking_id, product_ids)


if __name__ == "__main__":
    main()
