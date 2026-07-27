"""Seed para el manual de sale_mr_inherit_modify.

Crea el flujo dimensional completo: clientes, productos con BoM, un pedido
confirmado (con su entrega y "Ver Cantidades" ya aplicado), una cotización en
borrador y órdenes de fabricación vinculadas a líneas de venta. Además activa
es_DO para que las capturas salgan en español.
"""

env = env(user=2)  # admin  # noqa: F821

# ─── idioma: capturas en español ────────────────────────────────────────────
lang = env["res.lang"]._activate_lang("es_DO")
wizard = env["base.language.install"].create(
    {"lang_ids": [(6, 0, lang.ids)], "overwrite": False}
)
wizard.lang_install()
env.user.write({"lang": "es_DO"})

# ─── clientes ───────────────────────────────────────────────────────────────
Partner = env["res.partner"]
constructora = Partner.create(
    {
        "name": "Constructora Demo S.R.L.",
        "street": "Av. Independencia 45",
        "city": "Santo Domingo",
        "email": "compras@constructora-demo.com",
        "phone": "+1 809 555 0101",
    }
)
textilera = Partner.create(
    {
        "name": "Textilera Moderna C. por A.",
        "street": "Calle El Conde 120",
        "city": "Santiago",
        "email": "pedidos@textilera-demo.com",
        "phone": "+1 809 555 0202",
    }
)

# ─── productos de venta y componentes ───────────────────────────────────────
Product = env["product.product"]
ceramica = Product.create(
    {"name": "Cerámica 60×60 Blanca", "type": "consu", "list_price": 320.0}
)
vidrio = Product.create(
    {"name": "Vidrio Templado 6mm", "type": "consu", "list_price": 1200.0}
)
madera = Product.create(
    {"name": "Piso de Madera Roble Natural", "type": "consu", "list_price": 850.0}
)
tela = Product.create(
    {"name": "Tela Lino Natural (metro)", "type": "consu", "list_price": 450.0}
)
arcilla = Product.create(
    {"name": "Arcilla Refractaria (kg)", "type": "consu", "list_price": 15.0}
)
esmalte = Product.create(
    {"name": "Esmalte Cerámico (lt)", "type": "consu", "list_price": 80.0}
)
madera_bruta = Product.create(
    {"name": "Madera Roble en Bruto (m²)", "type": "consu", "list_price": 420.0}
)
barniz = Product.create(
    {"name": "Barniz Poliuretano (lt)", "type": "consu", "list_price": 95.0}
)

# ─── listas de materiales ───────────────────────────────────────────────────
Bom = env["mrp.bom"]
bom_ceramica = Bom.create(
    {
        "product_tmpl_id": ceramica.product_tmpl_id.id,
        "product_qty": 1.0,
        "type": "normal",
        "bom_line_ids": [
            (0, 0, {"product_id": arcilla.id, "product_qty": 2.5}),
            (0, 0, {"product_id": esmalte.id, "product_qty": 0.3}),
        ],
    }
)
bom_madera = Bom.create(
    {
        "product_tmpl_id": madera.product_tmpl_id.id,
        "product_qty": 1.0,
        "type": "normal",
        "bom_line_ids": [
            (0, 0, {"product_id": madera_bruta.id, "product_qty": 1.2}),
            (0, 0, {"product_id": barniz.id, "product_qty": 0.15}),
        ],
    }
)

# ─── pedido 1: confirmado, con entrega y cantidades sincronizadas ───────────
SaleOrder = env["sale.order"]
Line = env["sale.order.line"]
order1 = SaleOrder.create(
    {
        "partner_id": constructora.id,
        "note": "Pedido demo — cálculo dimensional Pieza × Altura = Cantidad",
    }
)
line_ceramica_sala = Line.create(
    {
        "order_id": order1.id,
        "product_id": ceramica.id,
        "new_qty": 5.0,
        "new_height": 8.0,
        "product_uom_qty": 40.0,
        "price_unit": 320.0,
    }
)
Line.create(
    {
        "order_id": order1.id,
        "product_id": vidrio.id,
        "new_qty": 1.2,
        "new_height": 2.4,
        "product_uom_qty": 2.88,
        "price_unit": 1200.0,
    }
)
Line.create(
    {
        "order_id": order1.id,
        "product_id": tela.id,
        "new_qty": 1.5,
        "new_height": 10.0,
        "product_uom_qty": 15.0,
        "price_unit": 450.0,
    }
)
order1.action_confirm()

picking = order1.picking_ids[:1]
assert picking, "el pedido confirmado debió generar una entrega"
picking.find_qty()  # sincroniza Pieza/Altura hacia movimientos y líneas

# ─── pedido 2: cotización en borrador ───────────────────────────────────────
order2 = SaleOrder.create(
    {
        "partner_id": textilera.id,
        "note": "Cotización demo — telas e instalación por dimensiones",
    }
)
line_madera_salon = Line.create(
    {
        "order_id": order2.id,
        "product_id": madera.id,
        "new_qty": 4.0,
        "new_height": 6.0,
        "product_uom_qty": 24.0,
        "price_unit": 850.0,
    }
)
Line.create(
    {
        "order_id": order2.id,
        "product_id": tela.id,
        "new_qty": 1.5,
        "new_height": 10.0,
        "product_uom_qty": 15.0,
        "price_unit": 450.0,
    }
)

# ─── órdenes de fabricación vinculadas ──────────────────────────────────────
Production = env["mrp.production"]
mo1 = Production.create(
    {
        "product_id": ceramica.id,
        "product_qty": 40.0,
        "product_uom_id": ceramica.uom_id.id,
        "bom_id": bom_ceramica.id,
        "sale_line_id": line_ceramica_sala.id,
    }
)
mo1.action_confirm()

# MO sin vínculo manual: find_qty lo resuelve por el documento origen
mo2 = Production.create(
    {
        "product_id": madera.id,
        "product_qty": 24.0,
        "product_uom_id": madera.uom_id.id,
        "bom_id": bom_madera.id,
        "origin": order2.name,
    }
)
mo2.find_qty()
assert mo2.sale_line_id == line_madera_salon, "find_qty debió vincular la línea"

env.cr.commit()
print(
    "SEED OK — pedido %s (entrega %s), cotización %s, MOs %s/%s"
    % (order1.name, picking.name, order2.name, mo1.name, mo2.name)
)
