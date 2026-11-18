SO = env["sale.order"]
p = env["res.partner"].create({"name": "Pat"})
prod = env["product.product"].create({"name": "Svc", "type": "service", "invoice_policy": "order"})
def mk():
    return SO.create({"partner_id": p.id, "order_line": [(0, 0, {"product_id": prod.id, "price_unit": 50})]})
o = mk()
o.action_lock(); o.action_lock()
print("LOCK twice copies=%s" % SO.search_count([("hms_origin_order_id", "=", o.id)]))
o2 = mk(); o2.action_confirm()
try:
    inv = o2._create_invoices()
    print("INVOICE ok", "treating" if "treating_partner_id" in inv._fields else "no-field")
except Exception as e:
    print("INVOICE ERR", type(e).__name__, e)
env.cr.rollback()
