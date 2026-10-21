# Seed data for the report_zpl_direct_print user manual.
# Executed inside `odoo shell` (the `env` global is provided). Idempotent.

env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

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

report.write({"multi_copy_print": True, "default_copies": 2, "binding_model_id": partner_model.id})

partner = env["res.partner"].search([("name", "=", "Ferretería El Progreso")], limit=1)
if not partner:
    partner = env["res.partner"].create({"name": "Ferretería El Progreso", "city": "Santo Domingo", "ref": "CLI-00125"})

ModelData = env["ir.model.data"].sudo()
for name, record in (("printer", printer), ("template", template), ("report", report), ("partner", partner)):
    if not ModelData.search([("module", "=", "manual_seed"), ("name", "=", name)]):
        ModelData.create({"module": "manual_seed", "name": name, "model": record._name, "res_id": record.id})

env.cr.commit()
print("SEED OK: printer=%s template=%s report=%s" % (printer.id, template.id, report.id))
