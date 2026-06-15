# Seed data for the product_label_for_zebra_printer user manual.
# Runs inside `odoo shell` (global `env` provided). Idempotent.

# Printer assigned to the shipped product-label report.
printer = env["report.zpl.printer"].search([("name", "=", "Zebra ZD420")], limit=1)
if not printer:
    printer = env["report.zpl.printer"].create(
        {"name": "Zebra ZD420", "printer_type": "zpl"}
    )

report = env.ref(
    "product_label_for_zebra_printer.report_product_zpl_label",
    raise_if_not_found=False,
)
if report and not report.printer_id:
    report.printer_id = printer.id

# Demo products to label.
demo_products = [
    ("Camiseta Azul M", "7460000000017"),
    ("Gorra Negra", "7460000000024"),
    ("Taza Cerámica 350ml", "7460000000031"),
]
for name, barcode in demo_products:
    if not env["product.product"].search([("barcode", "=", barcode)], limit=1):
        env["product.product"].create({"name": name, "barcode": barcode})

env.cr.commit()
print(
    "SEED OK: printer=%s report=%s products=%s"
    % (printer.id, report.id if report else None, len(demo_products))
)
