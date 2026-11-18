# Datos de ejemplo para el manual de sales_bavel (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from odoo.tools.binary import BinaryBytes

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Order>
    <GeneralData Ref="{ref}" Currency="DOP" Date="{date}"/>
    <Client CIF="131000001" Company="Supermercados del Caribe SRL" Address="Av. 27 de Febrero 300"
            City="Santo Domingo" PC="10101" Email="compras@supercaribe.do" Country="DO"/>
    <Customers>
        <Customer CustomerID="{store_id}" Customer="{store}" Address="{address}"
                  City="Santo Domingo" PC="10148" Phone="809-555-0101" Email="tiendas@supercaribe.do"/>
    </Customers>
    <ProductList>
        <Product SupplierSKU="BV-DET-5L" Item="Detergente líquido 5 L" Qty="24" UP="450.00">
            <Discounts>
                <Discount Type="DESC PROVEEDOR" Rate="5"/>
                <Discount Type="DescNoDevGpoArticulo" Rate="2" Amount="216.00"/>
            </Discounts>
        </Product>
        <Product SupplierSKU="BV-SUA-1L" Item="Suavizante de ropa 1 L" Qty="48" UP="125.00"/>
        <Product SupplierSKU="BV-CLO-1G" Item="Cloro concentrado 1 galón" Qty="36" UP="95.00"/>
    </ProductList>
</Order>
"""

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})
admin.group_ids |= env.ref("sales_team.group_sale_manager") | env.ref("sales_bavel.group_bavel_user")

company = env.ref("base.main_company")
company.write({"name": "Distribuidora Química Dominicana SRL", "country_id": env.ref("base.do").id})
env.ref("base.DOP").active = True
company.currency_id = env.ref("base.DOP")
env["product.pricelist"].search([]).write({"currency_id": env.ref("base.DOP").id})
admin.group_ids |= env.ref("sale.group_discount_per_so_line")

category = env["product.category"].create({"name": "Productos BaVel"})
discount_product = env["product.product"].create(
    {"name": "Descuento BaVel", "default_code": "DESC-BAVEL", "type": "service", "sale_ok": True}
)
env["product.product"].create(
    {"name": "Suavizante de ropa 1 L", "default_code": "SUAV-1L", "bavel_sku": "BV-SUA-1L", "list_price": 125}
)
env["res.config.settings"].create(
    {
        "bavel_url": "https://fileconnector.bavel.example/api",
        "bavel_user": "distquimica",
        "bavel_password": "********",
        "bavel_error_email": "sistemas@distquimica.do",
        "bavel_default_order_state": "draft",
        "bavel_default_product_type": "consu",
        "bavel_default_product_category_id": category.id,
        "bavel_discount_product_id": discount_product.id,
        "bavel_log_retention_days": 30,
    }
).execute()

Log = env["bavel.import.log"]


def add(name, ref, store_id, store, address, date):
    return Log.create(
        {
            "name": name,
            "file_content": BinaryBytes(
                XML.format(ref=ref, store_id=store_id, store=store, address=address, date=date).encode()
            ),
        }
    )


add("ORD_20261102_0001.xml", "PC-45001", "TD-010", "Supercaribe Piantini", "C/ Gustavo Mejía Ricart 5", "2026-11-02T08:15:00")
add("ORD_20261102_0002.xml", "PC-45002", "TD-022", "Supercaribe Los Prados", "Av. Núñez de Cáceres 88", "2026-11-02T09:40:00")
add("ORD_20261103_0001.xml", "PC-45003", "TD-010", "Supercaribe Piantini", "C/ Gustavo Mejía Ricart 5", "2026-11-03T10:05:00")
add("ORD_20261103_0002_REENVIO.xml", "PC-45001", "TD-010", "Supercaribe Piantini", "C/ Gustavo Mejía Ricart 5", "2026-11-03T11:30:00")
Log.process_pending_files()
add("ORD_20261104_0001.xml", "PC-45004", "TD-022", "Supercaribe Los Prados", "Av. Núñez de Cáceres 88", "2026-11-04T07:50:00")

first = Log.search([("name", "=", "ORD_20261102_0001.xml")])
failed = Log.search([("status", "=", "failed")])
print(
    "SEED OK | logs:", Log.search_count([]),
    "| completados:", Log.search_count([("status", "=", "completed")]),
    "| fallidos:", failed.mapped("name"),
    "| pedido:", first.sale_order_id.name, first.sale_order_id.amount_total,
    "| contactos:", env["res.partner"].search_count([("bavel_customer_id", "!=", False)]),
)
env.cr.commit()
