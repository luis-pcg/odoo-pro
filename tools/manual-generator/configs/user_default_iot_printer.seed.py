env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin = env.ref("base.user_admin")
admin.lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

Box = env["iot.box"].sudo()
Device = env["iot.device"].sudo()


def box(name, identifier, ip):
    record = Box.search([("identifier", "=", identifier)], limit=1)
    return record or Box.create({"name": name, "identifier": identifier, "ip": ip})


def printer(iot_box, name, identifier, subtype, connection="network"):
    record = Device.search([("identifier", "=", identifier)], limit=1)
    return record or Device.create({
        "iot_id": iot_box.id,
        "name": name,
        "identifier": identifier,
        "type": "printer",
        "subtype": subtype,
        "connection": connection,
        "connected_status": "connected",
    })


principal = box("IoT Sucursal Principal", "IOT-PRINCIPAL-01", "192.168.10.20")
santiago = box("IoT Sucursal Santiago", "IOT-SANTIAGO-01", "192.168.20.20")

caja1 = printer(principal, "Epson TM-T88 Caja 1", "printer_caja1", "receipt_printer")
caja2 = printer(principal, "Epson TM-T88 Caja 2", "printer_caja2", "receipt_printer")
oficina = printer(principal, "HP LaserJet Oficina", "printer_oficina", "office_printer")
caja_stgo = printer(santiago, "Epson TM-T20 Caja Santiago", "printer_caja_stgo", "receipt_printer", "direct")

invoice_report = env.ref("account.account_invoices")
invoice_report.device_ids = [(6, 0, (caja1 | caja2 | oficina | caja_stgo).ids)]

admin.write({
    "default_iot_box_id": principal.id,
    "default_iot_printer_ids": [(6, 0, caja1.ids)],
    "force_iot_printer_wizard": True,
})

Users = env["res.users"].sudo().with_context(no_reset_password=True)
invoice_group = env.ref("account.group_account_invoice")


def user(name, login, iot_box, printers, force=False):
    record = Users.search([("login", "=", login)], limit=1)
    vals = {
        "name": name,
        "login": login,
        "lang": "es_DO",
        "default_iot_box_id": iot_box.id,
        "default_iot_printer_ids": [(6, 0, printers.ids)],
        "force_iot_printer_wizard": force,
    }
    if record:
        record.write(vals)
        return record
    vals["group_ids"] = [(4, invoice_group.id)]
    return Users.create(vals)


user("María Caja Principal", "maria.caja", principal, caja2)
user("Pedro Caja Santiago", "pedro.santiago", santiago, caja_stgo)

partner = env["res.partner"].search([("name", "=", "Ferretería El Progreso")], limit=1)
if not partner:
    partner = env["res.partner"].create({"name": "Ferretería El Progreso"})

product = env["product.product"].search([("name", "=", "Cable eléctrico THHN #12")], limit=1)
if not product:
    product = env["product.product"].create({"name": "Cable eléctrico THHN #12", "list_price": 1250.0})

invoice = env["account.move"].search([("partner_id", "=", partner.id), ("move_type", "=", "out_invoice")], limit=1)
if not invoice:
    invoice = env["account.move"].create({
        "move_type": "out_invoice",
        "partner_id": partner.id,
        "invoice_line_ids": [(0, 0, {"product_id": product.id, "quantity": 4, "price_unit": 1250.0})],
    })
    invoice.action_post()

ModelData = env["ir.model.data"].sudo()


def xmlid(name, record):
    if not ModelData.search([("module", "=", "manual_seed"), ("name", "=", name)]):
        ModelData.create({"module": "manual_seed", "name": name, "model": record._name, "res_id": record.id})


xmlid("invoice", invoice)
xmlid("user_maria", Users.search([("login", "=", "maria.caja")]))
xmlid("user_pedro", Users.search([("login", "=", "pedro.santiago")]))
xmlid("box_principal", principal)
env.cr.commit()
