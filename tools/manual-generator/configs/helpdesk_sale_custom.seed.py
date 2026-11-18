MODULE = "helpdesk_sale_custom"

company = env.ref("base.main_company")
admin = env.ref("base.user_admin")

es = env["res.lang"]._activate_lang("es_DO")
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(
    filter_lang="es_DO", overwrite=True
)

company.write(
    {
        "name": "INDEXA SRL",
        "country_id": env.ref("base.do").id,
        "create_ticket_from_sale_order": True,
        "allow_to_create_ticket_on_unconfirmed_orders": False,
    }
)
admin.write({"group_ids": [(4, env.ref("helpdesk_sale_custom.group_can_create_ticket_from_sale").id)]})

team = env["helpdesk.team"].search([], limit=1) or env["helpdesk.team"].create({"name": "Soporte"})
team.name = "Soporte posventa"

cliente = env["res.partner"].create(
    {"name": "Ferretería El Progreso, SRL", "email": "compras@elprogreso.do", "phone": "809-555-0101"}
)
cliente2 = env["res.partner"].create({"name": "Distribuidora Caribe, SRL", "email": "info@dcaribe.do"})
servicio = env["product.product"].create(
    {"name": "Instalación de aire acondicionado", "type": "service", "list_price": 15000.0}
)
equipo = env["product.product"].create(
    {"name": "Aire acondicionado inverter 12,000 BTU", "type": "consu", "list_price": 32000.0}
)


def pedido(partner, lines, confirm=True):
    so = env["sale.order"].create(
        {
            "partner_id": partner.id,
            "order_line": [(0, 0, {"product_id": p.id, "product_uom_qty": q}) for p, q in lines],
        }
    )
    if confirm:
        so.action_confirm()
    return so


so_nuevo = pedido(cliente, [(equipo, 1), (servicio, 1)])
so_tickets = pedido(cliente2, [(equipo, 3), (servicio, 3)])
cotizacion = pedido(cliente, [(equipo, 2)], confirm=False)

Ticket = env["helpdesk.ticket"]
t1 = Ticket.create(
    {
        "name": "Equipo no enfría - unidad 1",
        "team_id": team.id,
        "partner_id": cliente2.id,
        "sale_order_id": so_tickets.id,
    }
)
t2 = Ticket.create(
    {
        "name": "Ruido en compresor - unidad 3",
        "team_id": team.id,
        "partner_id": cliente2.id,
        "sale_order_id": so_tickets.id,
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


demo_action("demo_pedido_nuevo", {"name": "Pedido confirmado", "res_model": "sale.order", "view_mode": "form", "res_id": so_nuevo.id})
demo_action("demo_pedido_tickets", {"name": "Pedido con tickets", "res_model": "sale.order", "view_mode": "form", "res_id": so_tickets.id})
demo_action("demo_cotizacion", {"name": "Cotización", "res_model": "sale.order", "view_mode": "form", "res_id": cotizacion.id})
grupo = env.ref("helpdesk_sale_custom.group_can_create_ticket_from_sale")
demo_action("demo_grupo", {"name": "Grupo", "res_model": "res.groups", "view_mode": "form", "res_id": grupo.id})

env.cr.commit()
print("SEED OK |", so_nuevo.name, so_tickets.name, so_tickets.helpdesk_ticket_count, cotizacion.name, cotizacion.state)
