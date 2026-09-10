"""Seed para el manual de price_unit_display_precision.

Reproduce el caso que destapó el problema: una cotización con descuento por
línea y dos descuentos globales encadenados, que deja precios unitarios de 3 y 5
decimales (-2973.834 y -2929.22649). Deja una cotización en borrador, un pedido
confirmado y su factura de cliente en borrador, para ver el Precio unitario en
los tres documentos. Además activa es_DO para que las capturas salgan en
español.
"""

env = env(user=2)  # admin  # noqa: F821

# ─── idioma: capturas en español ────────────────────────────────────────────
lang = env["res.lang"]._activate_lang("es_DO")
wizard = env["base.language.install"].create(
    {"lang_ids": [(6, 0, lang.ids)], "overwrite": False}
)
wizard.lang_install()
env.user.write({"lang": "es_DO"})

# ─── plan de cuentas: sin datos demo la compañía no trae ninguno ────────────
company = env.user.company_id
if not company.chart_template:
    env["account.chart.template"].try_loading(
        "generic_coa", company=company, install_demo=False
    )

# ─── cliente y producto ─────────────────────────────────────────────────────
partner = env["res.partner"].create(
    {
        "name": "Ferretería El Progreso S.R.L.",
        "street": "Av. Duarte 210",
        "city": "Santo Domingo",
        "email": "compras@elprogreso-demo.com",
        "phone": "+1 809 555 0110",
    }
)
product = env["product.product"].create(
    {
        "name": "Cable THHN #12 (rollo)",
        "type": "consu",
        "list_price": 2110.0,
    }
)

# ─── el precio unitario con decimales de más ────────────────────────────────
# 13% por línea y dos descuentos globales de 1.5%: cada descuento global toma
# las líneas del anterior como parte de su base, así que los decimales se
# acumulan sin redondeo.
DISCOUNTS = (("sol_discount", 0.13), ("so_discount", 0.015), ("so_discount", 0.015))


def build_order():
    order = env["sale.order"].create(
        {
            "partner_id": partner.id,
            "order_line": [
                (0, 0, {"product_id": product.id, "product_uom_qty": 108.0})
            ],
        }
    )
    order.order_line.price_unit = 2110.0
    for discount_type, percentage in DISCOUNTS:
        env["sale.order.discount"].create(
            {
                "sale_order_id": order.id,
                "discount_type": discount_type,
                "discount_percentage": percentage,
            }
        ).action_apply_discount()
    return order


# El pedido confirmado se crea primero y la cotización después, para que la
# cotización en borrador quede como primera fila de la lista de Cotizaciones y
# los flujos del manual la abran sin buscarla por nombre.
order = build_order()
order.action_confirm()
invoice = order._create_invoices()

quotation = build_order()

stored = order.order_line.filtered(lambda line: line.price_unit < 0).mapped(
    "price_unit"
)
assert any(round(price, 2) != price for price in stored), (
    "el seed debe dejar precios unitarios con más de 2 decimales: %s" % stored
)

env.cr.commit()
print(
    "SEED OK — cotización %s, pedido %s, factura id=%s, precios unitarios %s"
    % (quotation.name, order.name, invoice.id, stored)
)
