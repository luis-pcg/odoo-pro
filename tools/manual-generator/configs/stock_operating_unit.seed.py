company = env.ref("base.main_company")
do = env.ref("base.do")
admin = env.ref("base.user_admin")

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

company = company.with_env(env)
company.write({"name": "Tiendas del Caribe SRL", "country_id": do.id})
company.partner_id.lang = "es_DO"

ou_sdq = env.ref("operating_unit.main_operating_unit")
ou_sdq.write({"name": "Sucursal Santo Domingo", "code": "SDQ"})
partner_sti = env["res.partner"].create(
    {"name": "Tiendas del Caribe - Santiago", "city": "Santiago", "country_id": do.id}
)
ou_sti = env["operating.unit"].create(
    {
        "name": "Sucursal Santiago",
        "code": "STI",
        "partner_id": partner_sti.id,
        "company_id": company.id,
    }
)
admin.write(
    {
        "assigned_operating_unit_ids": [(6, 0, (ou_sdq | ou_sti).ids)],
        "default_operating_unit_id": ou_sdq.id,
    }
)

wh_sdq = env.ref("stock.warehouse0")
wh_sdq.write({"name": "Almacén Santo Domingo", "code": "SDQ", "operating_unit_id": ou_sdq.id})
wh_sdq.lot_stock_id.write({"name": "Existencias", "operating_unit_id": ou_sdq.id})
wh_sti = env["stock.warehouse"].create(
    {
        "name": "Almacén Santiago",
        "code": "STI",
        "company_id": company.id,
        "partner_id": partner_sti.id,
        "operating_unit_id": ou_sti.id,
    }
)
wh_sti.lot_stock_id.operating_unit_id = ou_sti

products = env["product.product"].create(
    [
        {"name": "Cemento gris 42.5 kg", "is_storable": True, "list_price": 495.0},
        {"name": "Varilla corrugada 3/8\"", "is_storable": True, "list_price": 310.0},
        {"name": "Block de 6\"", "is_storable": True, "list_price": 42.0},
    ]
)
Quant = env["stock.quant"].sudo()
for product, qty_sdq, qty_sti in zip(products, (120, 300, 2000), (45, 80, 650)):
    Quant._update_available_quantity(product, wh_sdq.lot_stock_id, qty_sdq)
    Quant._update_available_quantity(product, wh_sti.lot_stock_id, qty_sti)

vendor = env["res.partner"].create({"name": "Cementos del Cibao SRL", "is_company": True})
supplier_loc = env.ref("stock.stock_location_suppliers")


def receipt(warehouse, lines, validate):
    picking = env["stock.picking"].create(
        {
            "picking_type_id": warehouse.in_type_id.id,
            "partner_id": vendor.id,
            "location_id": supplier_loc.id,
            "location_dest_id": warehouse.lot_stock_id.id,
            "move_ids": [
                (
                    0,
                    0,
                    {
                        "product_id": product.id,
                        "product_uom_qty": qty,
                        "location_id": supplier_loc.id,
                        "location_dest_id": warehouse.lot_stock_id.id,
                    },
                )
                for product, qty in lines
            ],
        }
    )
    picking.action_confirm()
    if validate:
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
        picking.move_ids.picked = True
        picking.button_validate()
    return picking


receipt(wh_sdq, [(products[0], 60), (products[1], 100)], validate=True)
receipt(wh_sdq, [(products[2], 500)], validate=False)
receipt(wh_sti, [(products[0], 30), (products[2], 400)], validate=True)
receipt(wh_sti, [(products[1], 50)], validate=False)

santiago = env["res.users"].create(
    {
        "name": "Encargado Santiago",
        "login": "santiago",
        "password": "santiago",
        "lang": "es_DO",
        "company_id": company.id,
        "company_ids": [(6, 0, company.ids)],
        "group_ids": [(6, 0, [env.ref("base.group_user").id, env.ref("stock.group_stock_user").id])],
        "assigned_operating_unit_ids": [(6, 0, ou_sti.ids)],
        "default_operating_unit_id": ou_sti.id,
    }
)

print("SEED OK: OU %s/%s, almacenes %s/%s, usuario %s (id %s)" % (
    ou_sdq.code, ou_sti.code, wh_sdq.code, wh_sti.code, santiago.login, santiago.id
))
print("SEED IDS: wh_sti=%s loc_sti=%s santiago=%s" % (wh_sti.id, wh_sti.lot_stock_id.id, santiago.id))
env.cr.commit()
