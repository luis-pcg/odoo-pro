SO = env["sale.order"]
p = env["res.partner"].create({"name": "Pat"})
prod = env["product.product"].create({"name": "Svc", "type": "service", "invoice_policy": "order"})
def mk():
    return SO.create({"partner_id": p.id, "order_line": [(0, 0, {"product_id": prod.id, "price_unit": 50})]})
o = mk()
try:
    res = o.action_lock()
    copies = SO.search([("hms_origin_order_id", "=", o.id)])
    print("LOCK draft ok locked=%s copies=%s" % (o.locked, len(copies)))
    o.action_lock()
    print("LOCK twice copies=%s" % SO.search_count([("hms_origin_order_id", "=", o.id)]))
except Exception as e:
    print("LOCK ERR", type(e).__name__, e)
try:
    mk().action_done()
    print("ACTION_DONE ok")
except Exception as e:
    print("ACTION_DONE ERR", type(e).__name__, e)
o2 = mk(); o2.action_confirm()
try:
    inv = o2._create_invoices()
    print("INVOICE ok", inv.name, getattr(inv, "treating_partner_id", "no-field"))
except Exception as e:
    print("INVOICE ERR", type(e).__name__, e)
for v in env["ir.ui.view"].search([("arch_db", "ilike", "action_lock"), ("model", "=", "sale.order"), ("key", "ilike", "hms")]):
    print("VIEW", v.key)
env.cr.rollback()
