#!/usr/bin/env python3
"""
Setup script: test_sale_order_with_other_locations
Creates DB, installs module, seeds all required test data.

Usage:
    python3 setup_test_sale_order_with_other_locations.py
    python3 setup_test_sale_order_with_other_locations.py --reset  # drop & recreate DB

Requirements:
    - Odoo container running (lfernandez_v17)
    - Odoo accessible at http://localhost:8090
"""

import argparse
import sys
import time
import xmlrpc.client

# ─── CONFIG ────────────────────────────────────────────────────────────────────
ODOO_URL = "http://localhost:8090"
DB_NAME = "test_sale_order_with_other_locations"
MASTER_PASSWD = "admin"          # Odoo master/admin password (set in odoo.conf)
ADMIN_LOGIN = "admin"
ADMIN_PASSWD = "admin"           # admin user password for the new DB
DEMO_DATA = False
LANG = "en_US"


# ─── XMLRPC HELPERS ────────────────────────────────────────────────────────────
def get_db_proxy():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/db", allow_none=True)


def get_common_proxy():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/common", allow_none=True)


def get_object_proxy():
    return xmlrpc.client.ServerProxy(f"{ODOO_URL}/xmlrpc/2/object", allow_none=True)


def authenticate(db, login, password):
    common = get_common_proxy()
    uid = common.authenticate(db, login, password, {})
    if not uid:
        raise RuntimeError(f"Auth failed: {db}/{login}")
    return uid


def call(obj, uid, db, passwd, model, method, *args, **kwargs):
    return obj.execute_kw(db, uid, passwd, model, method, list(args), kwargs)


def search_read(obj, uid, db, passwd, model, domain, fields, limit=None):
    kw = {"fields": fields}
    if limit:
        kw["limit"] = limit
    return call(obj, uid, db, passwd, model, "search_read", domain, **kw)


def find_or_create(obj, uid, db, passwd, model, domain, vals):
    """Return existing id or create new record."""
    result = search_read(obj, uid, db, passwd, model, domain, ["id"], limit=1)
    if result:
        return result[0]["id"]
    return call(obj, uid, db, passwd, model, "create", vals)


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
            print(f"[skip] DB '{DB_NAME}' already exists. Use --reset to recreate.")
            return False

    print(f"[create] Creating database '{DB_NAME}'...")
    db_proxy.create_database(
        MASTER_PASSWD,
        DB_NAME,
        DEMO_DATA,
        LANG,
        ADMIN_PASSWD,
        ADMIN_LOGIN,
        "DO",   # country_code: Dominican Republic
    )
    # Wait for DB to be ready
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
def install_modules(obj, uid):
    print("[install] Installing sale_order_with_other_locations (+ deps)...")
    module_ids = search_read(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "ir.module.module",
        [("name", "=", "sale_order_with_other_locations")],
        ["id", "state"],
        limit=1,
    )
    if not module_ids:
        raise RuntimeError("Module 'sale_order_with_other_locations' not found in addons path")

    mod = module_ids[0]
    if mod["state"] == "installed":
        print("[skip] Module already installed.")
        return

    call(obj, uid, DB_NAME, ADMIN_PASSWD,
         "ir.module.module", "button_immediate_install", [mod["id"]])

    # Wait for installation
    for i in range(60):
        state = search_read(
            obj, uid, DB_NAME, ADMIN_PASSWD,
            "ir.module.module",
            [("name", "=", "sale_order_with_other_locations")],
            ["state"], limit=1,
        )
        if state and state[0]["state"] == "installed":
            break
        print(f"  installing... ({i+1}/60)")
        time.sleep(5)

    print("[ok] Module installed.")


# ─── STEP 3: CONFIGURE WAREHOUSES ─────────────────────────────────────────────
def setup_warehouses(obj, uid):
    print("[setup] Configuring warehouses...")

    # Main warehouse (usually exists: "My Company")
    wh_main_id = search_read(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "stock.warehouse", [("code", "=", "WH")], ["id", "name"], limit=1,
    )
    if wh_main_id:
        wh_main_id = wh_main_id[0]["id"]
        print(f"  [ok] Main warehouse WH (id={wh_main_id})")
    else:
        wh_main_id = call(obj, uid, DB_NAME, ADMIN_PASSWD,
                          "stock.warehouse", "create", {
                              "name": "Main Warehouse",
                              "code": "WH",
                          })
        print(f"  [create] Main warehouse (id={wh_main_id})")

    # Secondary warehouse
    wh_sec = search_read(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "stock.warehouse", [("code", "=", "WH2")], ["id", "name"], limit=1,
    )
    if wh_sec:
        wh_sec_id = wh_sec[0]["id"]
        print(f"  [ok] Secondary warehouse WH2 (id={wh_sec_id})")
    else:
        wh_sec_id = call(obj, uid, DB_NAME, ADMIN_PASSWD,
                         "stock.warehouse", "create", {
                             "name": "Secondary Warehouse",
                             "code": "WH2",
                         })
        print(f"  [create] Secondary warehouse WH2 (id={wh_sec_id})")

    return wh_main_id, wh_sec_id


# ─── STEP 4: CONFIGURE STATE → WAREHOUSES ─────────────────────────────────────
def setup_state_warehouses(obj, uid, wh_main_id, wh_sec_id):
    print("[setup] Assigning warehouses to state (Distrito Nacional)...")

    state = search_read(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "res.country.state",
        [("code", "=", "DO-01")],
        ["id", "name"], limit=1,
    )
    if not state:
        # fallback: first DO state
        state = search_read(
            obj, uid, DB_NAME, ADMIN_PASSWD,
            "res.country.state",
            [("country_id.code", "=", "DO")],
            ["id", "name"], limit=1,
        )
    if not state:
        raise RuntimeError("No Dominican Republic state found. Check country data.")

    state_id = state[0]["id"]
    state_name = state[0]["name"]
    call(obj, uid, DB_NAME, ADMIN_PASSWD,
         "res.country.state", "write",
         [state_id], {"warehouse_ids": [(6, 0, [wh_main_id, wh_sec_id])]})
    print(f"  [ok] State '{state_name}' (id={state_id}) → warehouses [{wh_main_id}, {wh_sec_id}]")
    return state_id


# ─── STEP 5: CREATE STORABLE PRODUCTS ─────────────────────────────────────────
def setup_products(obj, uid):
    print("[setup] Creating test products...")

    def create_product(name, default_code):
        pid = find_or_create(
            obj, uid, DB_NAME, ADMIN_PASSWD,
            "product.template",
            [("default_code", "=", default_code)],
            {
                "name": name,
                "default_code": default_code,
                "type": "product",         # storable
                "detailed_type": "product",
                "sale_ok": True,
                "purchase_ok": True,
            }
        )
        # Get product.product id
        pp = search_read(
            obj, uid, DB_NAME, ADMIN_PASSWD,
            "product.product",
            [("product_tmpl_id", "=", pid)],
            ["id"], limit=1,
        )
        return pid, pp[0]["id"]

    pt_a, pp_a = create_product("TEST Product A (no stock main)", "TEST-A")
    pt_b, pp_b = create_product("TEST Product B (partial stock main)", "TEST-B")
    print(f"  [ok] Product A: tmpl={pt_a}, variant={pp_a}")
    print(f"  [ok] Product B: tmpl={pt_b}, variant={pp_b}")
    return (pt_a, pp_a), (pt_b, pp_b)


# ─── STEP 6: ADD INVENTORY (QUANTS) ────────────────────────────────────────────
def setup_inventory(obj, uid, products, wh_main_id, wh_sec_id):
    """
    Product A: 0 in WH, 50 in WH2   → forces secondary warehouse lookup
    Product B: 5 in WH, 50 in WH2   → partial in main
    """
    print("[setup] Setting inventory levels...")
    (pt_a, pp_a), (pt_b, pp_b) = products

    def get_stock_location(warehouse_id):
        wh = search_read(
            obj, uid, DB_NAME, ADMIN_PASSWD,
            "stock.warehouse", [("id", "=", warehouse_id)],
            ["lot_stock_id"], limit=1,
        )
        return wh[0]["lot_stock_id"][0]

    loc_main = get_stock_location(wh_main_id)
    loc_sec = get_stock_location(wh_sec_id)

    def apply_quant_inventory(quant_id):
        """action_apply_inventory returns None — server can't marshal None via XML-RPC.
        Catch that specific serialization error; it means the method succeeded."""
        try:
            call(obj, uid, DB_NAME, ADMIN_PASSWD,
                 "stock.quant", "action_apply_inventory", [quant_id])
        except xmlrpc.client.Fault as e:
            if "cannot marshal None" not in str(e):
                raise

    def update_quant(product_id, location_id, qty):
        existing = search_read(
            obj, uid, DB_NAME, ADMIN_PASSWD,
            "stock.quant",
            [("product_id", "=", product_id), ("location_id", "=", location_id)],
            ["id", "quantity"], limit=1,
        )
        if existing:
            call(obj, uid, DB_NAME, ADMIN_PASSWD,
                 "stock.quant", "write", [existing[0]["id"]], {"inventory_quantity": qty})
            apply_quant_inventory(existing[0]["id"])
        else:
            quant_id = call(obj, uid, DB_NAME, ADMIN_PASSWD,
                            "stock.quant", "create", {
                                "product_id": product_id,
                                "location_id": location_id,
                                "inventory_quantity": qty,
                            })
            apply_quant_inventory(quant_id)

    # Product A: 0 in main, 50 in secondary
    update_quant(pp_a, loc_sec, 50.0)
    print(f"  [ok] Product A: 0 in WH (loc={loc_main}), 50 in WH2 (loc={loc_sec})")

    # Product B: 5 in main, 50 in secondary
    update_quant(pp_b, loc_main, 5.0)
    update_quant(pp_b, loc_sec, 50.0)
    print(f"  [ok] Product B: 5 in WH (loc={loc_main}), 50 in WH2 (loc={loc_sec})")


# ─── STEP 7: CREATE WEBSITE ────────────────────────────────────────────────────
def setup_website(obj, uid, wh_main_id):
    print("[setup] Configuring website...")
    websites = search_read(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "website", [], ["id", "name"], limit=1,
    )
    if websites:
        ws_id = websites[0]["id"]
        call(obj, uid, DB_NAME, ADMIN_PASSWD,
             "website", "write", [ws_id], {"warehouse_id": wh_main_id})
        print(f"  [ok] Website id={ws_id} → warehouse {wh_main_id}")
        return ws_id
    raise RuntimeError("No website found. Ensure website_sale is installed.")


# ─── STEP 8: CREATE TEST PARTNER ───────────────────────────────────────────────
def setup_partner(obj, uid, state_id):
    print("[setup] Creating test partner...")
    partner_id = find_or_create(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "res.partner",
        [("name", "=", "TEST Customer Multi-WH")],
        {
            "name": "TEST Customer Multi-WH",
            "email": "test.multiwh@example.com",
            "state_id": state_id,
            "country_id": search_read(
                obj, uid, DB_NAME, ADMIN_PASSWD,
                "res.country", [("code", "=", "DO")], ["id"], limit=1
            )[0]["id"],
            "customer_rank": 1,
        }
    )
    print(f"  [ok] Partner id={partner_id}, state_id={state_id}")
    return partner_id


# ─── STEP 9: CREATE TEST SALE ORDER ───────────────────────────────────────────
def create_test_sale_order(obj, uid, partner_id, products, wh_main_id, ws_id):
    print("[setup] Creating test sale order...")
    (pt_a, pp_a), (pt_b, pp_b) = products

    # Get pricelist
    pricelist = search_read(
        obj, uid, DB_NAME, ADMIN_PASSWD,
        "product.pricelist", [("currency_id.name", "=", "DOP")], ["id"], limit=1,
    )
    pricelist_id = pricelist[0]["id"] if pricelist else False

    so_id = call(obj, uid, DB_NAME, ADMIN_PASSWD,
                 "sale.order", "create", {
                     "partner_id": partner_id,
                     "warehouse_id": wh_main_id,
                     "website_id": ws_id,
                     **({"pricelist_id": pricelist_id} if pricelist_id else {}),
                     "order_line": [
                         (0, 0, {
                             "product_id": pp_a,
                             "product_uom_qty": 10.0,
                             "price_unit": 100.0,
                         }),
                         (0, 0, {
                             "product_id": pp_b,
                             "product_uom_qty": 20.0,  # > 5 in main → triggers secondary
                             "price_unit": 200.0,
                         }),
                     ],
                 })
    print(f"  [ok] Sale Order id={so_id}")
    print(f"       → Confirm in UI to test internal transfer creation")
    print(f"       → URL: {ODOO_URL}/odoo/sales/{so_id}")
    return so_id


# ─── SUMMARY ──────────────────────────────────────────────────────────────────
def print_summary(so_id, wh_main_id, wh_sec_id, state_id, partner_id):
    print("\n" + "=" * 60)
    print("TEST ENVIRONMENT READY")
    print("=" * 60)
    print(f"  DB:             {DB_NAME}")
    print(f"  URL:            {ODOO_URL}/web?db={DB_NAME}")
    print(f"  Login:          {ADMIN_LOGIN} / {ADMIN_PASSWD}")
    print(f"  WH Main:        id={wh_main_id}")
    print(f"  WH Secondary:   id={wh_sec_id}")
    print(f"  State:          id={state_id} (with both warehouses)")
    print(f"  Test Partner:   id={partner_id}")
    print(f"  Test SO:        id={so_id}")
    print()
    print("VALIDATION STEPS:")
    print("  1. Open SO → verify warehouse = WH (main)")
    print("  2. Check order lines → warehouse_ids populated on lines with stock shortage")
    print("  3. Confirm SO → check Inventory > Transfers for internal pickings")
    print("  4. Internal transfer: origin=WH2, dest=WH")
    print("=" * 60)


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    global MASTER_PASSWD
    parser = argparse.ArgumentParser(description="Setup test DB for sale_order_with_other_locations")
    parser.add_argument("--reset", action="store_true", help="Drop and recreate DB if exists")
    parser.add_argument("--skip-db-create", action="store_true", help="Skip DB creation, only seed data")
    parser.add_argument("--master-password", default=MASTER_PASSWD, help="Odoo master password")
    args = parser.parse_args()
    MASTER_PASSWD = args.master_password

    if not args.skip_db_create:
        created = create_database(reset=args.reset)
        if not created and not args.reset:
            print(f"\nTip: to force recreate, run with --reset")
            print(f"Tip: to only seed data into existing DB, run with --skip-db-create")

    print(f"\n[auth] Authenticating to {DB_NAME}...")
    uid = authenticate(DB_NAME, ADMIN_LOGIN, ADMIN_PASSWD)
    obj = get_object_proxy()
    print(f"[ok] uid={uid}")

    install_modules(obj, uid)

    wh_main_id, wh_sec_id = setup_warehouses(obj, uid)
    state_id = setup_state_warehouses(obj, uid, wh_main_id, wh_sec_id)
    products = setup_products(obj, uid)
    setup_inventory(obj, uid, products, wh_main_id, wh_sec_id)
    ws_id = setup_website(obj, uid, wh_main_id)
    partner_id = setup_partner(obj, uid, state_id)
    so_id = create_test_sale_order(obj, uid, partner_id, products, wh_main_id, ws_id)

    print_summary(so_id, wh_main_id, wh_sec_id, state_id, partner_id)


if __name__ == "__main__":
    main()
