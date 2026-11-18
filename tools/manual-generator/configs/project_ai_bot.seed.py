from markupsafe import Markup

from odoo.addons.project_ai_bot.hooks import post_init_hook

env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "name": "Luis Fernández"})
env = env(context=dict(env.context, lang="es_DO", tracking_disable=False))

Tag = env["project.tags"]
TAG_NAMES = [
    "1. Type - BUG 🐞",
    "1. Type - MIG 🏃‍♂️💨",
    "1. Type - NEW 🌟",
    "1. Type - IMP ✅",
    "1. Type - REF ⚠️",
    "1. Type - QA 👮🏻‍♂️",
    "3. Versión - 17",
    "3. Versión - 19",
    "3. Versión - 20",
    "4. Base - Payroll",
    "4. Base - Account",
    "4. Base - L10N",
    "5. Complejidad - 👶🏼",
    "5. Complejidad - 🥶",
    "5. Complejidad - 🔥",
    "Documentación",
]
tags = {name: Tag.search([("name", "=", name)], limit=1) or Tag.create({"name": name}) for name in TAG_NAMES}

Stage = env["project.task.type"]
stages = {}
for sequence, name in enumerate(["To Do", "1 In Progress", "Review", "Done"]):
    stages[name] = Stage.search([("name", "=", name)], limit=1) or Stage.create(
        {"name": name, "sequence": sequence, "fold": name == "Done"}
    )

Project = env["project.project"]
project = Project.search([("name", "=", "[TI] Ingeniería")], limit=1) or Project.create(
    {"name": "[TI] Ingeniería", "type_ids": [(6, 0, [stage.id for stage in stages.values()])]}
)
Project.search([("name", "=", "[ADM] Administrativo")], limit=1) or Project.create(
    {"name": "[ADM] Administrativo", "type_ids": [(6, 0, [stages["To Do"].id, stages["Done"].id])]}
)

post_init_hook(env)

Users = env["res.users"].sudo().with_context(no_reset_password=True)
bot = Users.search([("login", "=", "botclaude")], limit=1) or Users.create(
    {
        "name": "Bot Claude",
        "login": "botclaude",
        "lang": "es_DO",
        "group_ids": [(4, env.ref("project.group_project_user").id)],
    }
)
ana = Users.search([("login", "=", "ana.qa")], limit=1) or Users.create(
    {
        "name": "Ana Rodríguez",
        "login": "ana.qa",
        "lang": "es_DO",
        "group_ids": [(4, env.ref("project.group_project_user").id)],
    }
)

version_17 = env.ref("project_ai_bot.version_17")
version_19 = env.ref("project_ai_bot.version_19")
version_20 = env.ref("project_ai_bot.version_20")
version_17.write({"cloud_environment": "odoo-17", "routine_trigger_id": "trig_01Odoo17Bot"})
version_19.write({"cloud_environment": "odoo-19", "routine_trigger_id": "trig_01Odoo19Bot"})
version_20.write({"cloud_environment": "odoo-20", "docker_image": "ghcr.io/indexa-git/odoo-docker-master"})
env["project.ai.bot.area"].search([("name", "=", "Payroll")]).write(
    {"skills": "odoo-payroll", "instructions": "Valide los cálculos contra la escala ISR vigente."}
)


def task(name, tag_names, stage, description="", users=None):
    record = env["project.task"].search([("name", "=", name)], limit=1)
    if record:
        return record
    return env["project.task"].create(
        {
            "name": name,
            "project_id": project.id,
            "stage_id": stages[stage].id,
            "tag_ids": [(6, 0, [tags[tag].id for tag in tag_names])],
            "user_ids": [(6, 0, (users or admin).ids)],
            "description": description,
        }
    )


ACTIVATION = "0. Team - Claude 🤖"
tags[ACTIVATION] = Tag.search([("name", "=", ACTIVATION)], limit=1)

bug = task(
    "Reporte IR-3: casilla 3 no cuadra con el total de sueldos",
    [ACTIVATION, "1. Type - BUG 🐞", "3. Versión - 19", "4. Base - Payroll", "5. Complejidad - 🥶"],
    "To Do",
    "<p>Al generar el IR-3 de septiembre la casilla 3 muestra RD$ 1,250,000 y el resumen de nómina RD$ 1,180,000.</p>",
)
migration = task(
    "Migrar l10n_do_hr_payroll_liquidation a 19.0",
    [ACTIVATION, "1. Type - MIG 🏃‍♂️💨", "3. Versión - 17", "4. Base - Payroll"],
    "To Do",
)
working = task(
    "e-CF: error al validar factura con NCF vencido",
    [ACTIVATION, "1. Type - BUG 🐞", "3. Versión - 19", "4. Base - L10N"],
    "1 In Progress",
    "<p>La DGII rechaza la factura E310000000123 con el código 2005 aunque la secuencia está vigente.</p>",
    ana,
)
development = task(
    "Reporte de comisiones por vendedor en Excel",
    [ACTIVATION, "1. Type - NEW 🌟", "3. Versión - 19", "4. Base - Account", "Documentación"],
    "1 In Progress",
)
review = task(
    "Asiento de cierre duplica la cuenta de resultados",
    [ACTIVATION, "1. Type - BUG 🐞", "3. Versión - 19", "4. Base - Account", "5. Complejidad - 👶🏼"],
    "Review",
)
master = task(
    "Probar compatibilidad del POS con master",
    [ACTIVATION, "1. Type - QA 👮🏻\u200d♂️", "3. Versión - 20"],
    "To Do",
)
task("Actualizar logo en el portal de clientes", ["1. Type - IMP ✅", "3. Versión - 19"], "To Do")


def note(record, body, author):
    record.message_post(
        body=Markup(body), message_type="comment", subtype_xmlid="mail.mt_note", author_id=author.partner_id.id
    )


def session(record, session_id, state, cost):
    record.ai_bot_register_session(session_id, f"https://claude.ai/code/{session_id}")
    record.ai_bot_set_state(state, cost)


session(working, "cse_01ECFncfVencido", "needs_input", 1.84)
note(
    working,
    '🤖 Claude started working on this task (19.0, Corrección de error): <a href="https://claude.ai/code/cse_01ECFncfVencido">'
    "cse_01ECFncfVencido</a>",
    bot,
)
note(
    working,
    "🤖 Reproduje el rechazo 2005 en 19.0: la fecha de vencimiento se toma de la secuencia B01 y no de la E31.<br/>"
    "Pregunta: ¿la corrección debe aplicar también a las notas de crédito (E34)?<br/>status: needs_input",
    bot,
)
note(working, "/claude Sí, aplica también a E34. Usa la misma regla.", ana)

session(development, "cse_01ComisionesXlsx", "needs_approval", 0.62)
note(
    development,
    "🤖 Análisis propuesto: nuevo asistente en Ventas ▸ Informes con filtro por fechas y vendedor, exportando a XLSX "
    "con report_xlsx. Responda <b>/claude aprobar</b> o <b>/claude rechazar &lt;motivo&gt;</b>.<br/>"
    "status: needs_approval",
    bot,
)

session(review, "cse_01CierreResultados", "done", 2.37)
note(
    review,
    '🤖 PR abierto: <a href="https://github.com/indexa-git/odoo-pro/pull/1402">indexa-git/odoo-pro#1402</a>. '
    "Tests de account_closing pasan. Moví la tarea a Review.<br/>status: done",
    bot,
)

config = env.ref("project_ai_bot.config_main")
config.write(
    {
        "gateway_url": "https://claudebot.progressa.group",
        "webhook_secret": "manual-" + "0" * 40,
        "bot_user_id": bot.id,
        "max_sessions": 3,
        "project_ids": [(6, 0, project.ids)],
    }
)

ModelData = env["ir.model.data"].sudo()


def xmlid(name, record):
    if not ModelData.search([("module", "=", "manual_seed"), ("name", "=", name)]):
        ModelData.create({"module": "manual_seed", "name": name, "model": record._name, "res_id": record.id})


xmlid("task_bug", bug)
xmlid("task_migration", migration)
xmlid("task_working", working)
xmlid("task_development", development)
xmlid("task_review", review)
xmlid("task_master", master)
xmlid("project_ti", project)
env.cr.commit()
print("SEED OK")
