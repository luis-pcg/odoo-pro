MODULE = "sale_stock_product_price_widget"

company = env.ref("base.main_company")
admin = env.ref("base.user_admin")

env["res.lang"]._activate_lang("es_DO")
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(
    filter_lang="es_DO", overwrite=True
)

company.write({"name": "INDEXA SRL", "country_id": env.ref("base.do").id})
usd = company.currency_id
dop = env.ref("base.DOP")
dop.active = True
env["res.currency.rate"].create({"currency_id": dop.id, "rate": 60.0, "company_id": company.id})

precision = env.ref("product.decimal_price")
env["res.config.settings"].create(
    {"group_product_pricelist": True, "sale_order_line_decimal_price_option": precision.id}
).execute()

producto = env["product.product"].create(
    {"name": "Taladro percutor 800W", "type": "consu", "list_price": 85.0, "taxes_id": [(5, 0, 0)]}
)
Pricelist = env["product.pricelist"]
Pricelist.search([]).action_archive()
detalle = Pricelist.create({"name": "Precio al detalle", "currency_id": usd.id, "company_id": False, "sequence": 1})
Pricelist.create(
    {
        "name": "Mayorista",
        "currency_id": usd.id,
        "company_id": company.id,
        "sequence": 2,
        "item_ids": [(0, 0, {"applied_on": "3_global", "compute_price": "discount", "price_discount": 10.0})],
    }
)
Pricelist.create(
    {
        "name": "Distribuidor",
        "currency_id": usd.id,
        "company_id": company.id,
        "sequence": 3,
        "item_ids": [
            (0, 0, {"applied_on": "3_global", "compute_price": "discount", "price_discount": 15.0, "min_quantity": 5})
        ],
    }
)
Pricelist.create({"name": "Detalle en pesos", "currency_id": dop.id, "company_id": False, "sequence": 4})

cliente = env["res.partner"].create({"name": "Ferretería El Progreso, SRL", "email": "compras@elprogreso.do"})
pedido = env["sale.order"].create(
    {
        "partner_id": cliente.id,
        "pricelist_id": detalle.id,
        "order_line": [(0, 0, {"product_id": producto.id, "product_uom_qty": 6})],
    }
)
pedido_uno = env["sale.order"].create(
    {
        "partner_id": cliente.id,
        "pricelist_id": detalle.id,
        "order_line": [(0, 0, {"product_id": producto.id, "product_uom_qty": 1})],
    }
)


def demo_action(xmlid, vals):
    existing = env.ref("%s.%s" % (MODULE, xmlid), raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True}
    )
    return act


demo_action("demo_pedido", {"name": "Pedido", "res_model": "sale.order", "view_mode": "form", "res_id": pedido.id})
demo_action("demo_pedido_uno", {"name": "Pedido", "res_model": "sale.order", "view_mode": "form", "res_id": pedido_uno.id})

env.cr.commit()
print("SEED OK |", pedido.name, [(r["pricelist_with_currency"], r["price_with_currency"]) for r in pedido.order_line.get_product_cost()])
