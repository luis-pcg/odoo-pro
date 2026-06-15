# Seed data for the report_zpl_direct_print user manual.
# Executed inside `odoo shell` (the `env` global is provided). Idempotent.

partner_model = env["ir.model"]._get("res.partner")

printer = env["report.zpl.printer"].search([("name", "=", "Zebra ZD420")], limit=1)
if not printer:
    printer = env["report.zpl.printer"].create(
        {"name": "Zebra ZD420", "printer_type": "zpl"}
    )

template = env["report.zpl.template"].search(
    [("name", "=", "Etiqueta de contacto (ZPL)")], limit=1
)
if not template:
    template = env["report.zpl.template"].create(
        {
            "name": "Etiqueta de contacto (ZPL)",
            "model_id": partner_model.id,
            "template_text": (
                "^XA\n"
                "^CFA,30\n"
                "^FO50,60^FD{object.name}^FS\n"
                "^FO50,110^FD{object.city}^FS\n"
                "^BY3,2,120\n"
                "^FO50,160^BC^FD{object.ref}^FS\n"
                "^XZ"
            ),
        }
    )

report = env["ir.actions.report"].search(
    [("report_name", "=", "report_zpl_direct_print.demo_partner_label")], limit=1
)
if not report:
    report = env["ir.actions.report"].create(
        {
            "name": "Etiqueta de contacto (ZPL Direct)",
            "model": "res.partner",
            "report_name": "report_zpl_direct_print.demo_partner_label",
            "report_type": "qweb-text",
            "report_user_action": "send_to_printer",
            "printer_id": printer.id,
            "use_template": True,
            "report_template_id": template.id,
        }
    )

env.cr.commit()
print("SEED OK: printer=%s template=%s report=%s" % (printer.id, template.id, report.id))
