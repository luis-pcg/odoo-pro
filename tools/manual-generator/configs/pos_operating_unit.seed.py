from odoo import fields

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
if not company.chart_template:
    env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)
dop = env.ref("base.DOP")
dop.active = True
if company.currency_id != dop:
    company.currency_id = dop

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

categ = env["pos.category"].create({"name": "Ferretería"})
products = env["product.product"].create(
    [
        {
            "name": name,
            "list_price": price,
            "type": "consu",
            "available_in_pos": True,
            "pos_categ_ids": [(6, 0, categ.ids)],
            "taxes_id": [(5, 0, 0)],
        }
        for name, price in (
            ("Martillo de uña 16 oz", 650.0),
            ("Cinta métrica 5 m", 380.0),
            ("Caja de tornillos 1\"", 225.0),
        )
    ]
)

for config in env["pos.config"].search([]):
    if config.current_session_id:
        config.current_session_id.unlink()
    config.active = False

cash_journal = env["account.journal"].search(
    [("type", "=", "cash"), ("company_id", "=", company.id)], limit=1
)


def make_pos(name, ou):
    journal = cash_journal.copy({"name": "Caja %s" % name, "code": ou.code[:3] + "C"})
    method = env["pos.payment.method"].create(
        {"name": "Efectivo %s" % name, "journal_id": journal.id, "is_cash_count": True}
    )
    return env["pos.config"].create(
        {
            "name": name,
            "operating_unit_ids": [(6, 0, ou.ids)],
            "payment_method_ids": [(6, 0, method.ids)],
        }
    )


pos_sdq = make_pos("Tienda Santo Domingo", ou_sdq)
pos_sti = make_pos("Tienda Santiago", ou_sti)


def sell(config, number, lines):
    session = config.current_session_id
    total = sum(product.list_price * qty for product, qty in lines)
    env["pos.order"].sync_from_ui(
        [
            {
                "session_id": session.id,
                "date_order": fields.Datetime.to_string(fields.Datetime.now()),
                "pricelist_id": config.pricelist_id.id,
                "user_id": admin.id,
                "name": "%s/%04d" % (config.name, number),
                "partner_id": False,
                "amount_paid": total,
                "amount_total": total,
                "amount_tax": 0.0,
                "amount_return": 0.0,
                "fiscal_position_id": False,
                "sequence_number": number,
                "uuid": "%s-%04d" % (config.id, number),
                "lines": [
                    [
                        0,
                        0,
                        {
                            "product_id": product.id,
                            "qty": qty,
                            "price_unit": product.list_price,
                            "price_subtotal": product.list_price * qty,
                            "price_subtotal_incl": product.list_price * qty,
                            "discount": 0.0,
                        },
                    ]
                    for product, qty in lines
                ],
                "payment_ids": [
                    [
                        0,
                        0,
                        {"payment_method_id": config.payment_method_ids[0].id, "amount": total},
                    ]
                ],
            }
        ]
    )


for config in (pos_sdq, pos_sti):
    config.with_user(admin).open_ui()
    config.current_session_id.set_opening_control(0, "")
sell(pos_sdq, 1, [(products[0], 2), (products[2], 4)])
sell(pos_sdq, 2, [(products[1], 1)])
sell(pos_sti, 1, [(products[0], 1), (products[1], 2)])
sell(pos_sti, 2, [(products[2], 10)])

cajero = env["res.users"].create(
    {
        "name": "Cajero Santiago",
        "login": "santiago",
        "password": "santiago",
        "lang": "es_DO",
        "company_id": company.id,
        "company_ids": [(6, 0, company.ids)],
        "group_ids": [(6, 0, [env.ref("base.group_user").id, env.ref("point_of_sale.group_pos_user").id])],
        "assigned_operating_unit_ids": [(6, 0, ou_sti.ids)],
        "default_operating_unit_id": ou_sti.id,
    }
)

print("SEED OK: PdV %s (%s) / %s (%s), %s órdenes, cajero %s" % (
    pos_sdq.name, pos_sdq.id, pos_sti.name, pos_sti.id,
    env["pos.order"].search_count([]), cajero.id,
))
env.cr.commit()
