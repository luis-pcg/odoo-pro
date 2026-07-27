"""Seed para el manual de project_unified_board.

Crea 3 proyectos con etapas propias, tareas con estados/prioridades/
dependencias/subtareas, dos usuarios asignables y la configuración del
tablero del admin (proyectos con color + columna personalizada "Test" que
agrupa las etapas Prueba 1, Prueba 2 y los Test de los otros proyectos).
Además instala el español (es_DO) para que las capturas salgan en español.
"""
from datetime import datetime, timedelta

env = env(user=2)  # admin  # noqa: F821

# ─── idioma: capturas en español ────────────────────────────────────────────
lang = env["res.lang"]._activate_lang("es_DO")
wizard = env["base.language.install"].create(
    {"lang_ids": [(6, 0, lang.ids)], "overwrite": False}
)
wizard.lang_install()
env.user.write({"lang": "es_DO"})

# ─── usuarios asignables ────────────────────────────────────────────────────
Users = env["res.users"]
users = {}
for login_name, name in [("maria", "María Pérez"), ("pedro", "Pedro Gómez")]:
    user = Users.search([("login", "=", login_name)], limit=1)
    if not user:
        user = Users.create(
            {
                "name": name,
                "login": login_name,
                "lang": "es_DO",
                "group_ids": [
                    (4, env.ref("base.group_user").id),
                    (4, env.ref("project.group_project_user").id),
                ],
            }
        )
    users[login_name] = user
maria = users["maria"]
pedro = users["pedro"]
admin = env.user

# ─── proyectos y etapas ─────────────────────────────────────────────────────
Project = env["project.project"]
Stage = env["project.task.type"]
Task = env["project.task"]

def get_project(name, color):
    project = Project.search([("name", "=", name)], limit=1)
    return project or Project.create({"name": name, "color": color})

web = get_project("Sitio Web", 4)
erp = get_project("Implementación ERP", 10)
movil = get_project("App Móvil", 9)

def get_stage(project, name, seq):
    stage = Stage.search(
        [("name", "=", name), ("project_ids", "in", project.id)], limit=1
    )
    return stage or Stage.create(
        {"name": name, "sequence": seq, "project_ids": [(4, project.id)]}
    )

stages = {}
for project, names in [
    (web, ["Nuevo", "En Progreso", "Prueba 1", "Prueba 2", "Entregado"]),
    (erp, ["Nuevo", "En Progreso", "Test", "Entregado"]),
    (movil, ["Nuevo", "En Progreso", "Test", "Entregado"]),
]:
    for seq, stage_name in enumerate(names, start=1):
        stages[(project.id, stage_name)] = get_stage(project, stage_name, seq)

# ─── tareas ─────────────────────────────────────────────────────────────────
now = datetime.now()

def get_task(name, project, stage_name, **vals):
    task = Task.search([("name", "=", name), ("project_id", "=", project.id)], limit=1)
    if task:
        return task
    vals.update(
        {
            "name": name,
            "project_id": project.id,
            "stage_id": stages[(project.id, stage_name)].id,
        }
    )
    return Task.create(vals)

imagenes = get_task(
    "Optimizar imágenes", web, "En Progreso", user_ids=[(6, 0, maria.ids)]
)
landing = get_task(
    "Rediseñar landing page", web, "Prueba 1",
    priority="1",
    date_deadline=now - timedelta(days=2),
    user_ids=[(6, 0, [maria.id, pedro.id])],
    depend_on_ids=[(6, 0, imagenes.ids)],
)
landing.write({"state": "02_changes_requested"})
hero = get_task(
    "Ajustar sección hero", web, "Prueba 1",
    parent_id=landing.id, user_ids=[(6, 0, pedro.ids)],
)
hero.display_in_project = True
get_task(
    "Migrar blog", web, "Nuevo",
    date_deadline=now + timedelta(days=5), user_ids=[(6, 0, pedro.ids)],
)
release = get_task(
    "Publicar release notes", web, "Prueba 2", user_ids=[(6, 0, admin.ids)]
)
release.write({"state": "03_approved"})
lanzamiento = get_task("Lanzamiento v1", web, "Entregado")
lanzamiento.write({"state": "1_done"})

saldos = get_task(
    "Cargar saldos iniciales", erp, "En Progreso",
    date_deadline=now + timedelta(days=2), user_ids=[(6, 0, pedro.ids)],
)
cuentas = get_task(
    "Configurar plan de cuentas", erp, "Test",
    user_ids=[(6, 0, maria.ids)], depend_on_ids=[(6, 0, saldos.ids)],
)
get_task(
    "Capacitación contabilidad", erp, "Nuevo",
    date_deadline=now + timedelta(days=10), user_ids=[(6, 0, admin.ids)],
)
piloto = get_task("Piloto primera compañía", erp, "Entregado")
piloto.write({"state": "1_done"})
abandonado = get_task("Integración legacy descartada", erp, "Nuevo")
abandonado.write({"state": "1_canceled"})

get_task(
    "Pantalla de login", movil, "Test",
    priority="1", user_ids=[(6, 0, [admin.id, maria.id])],
)
get_task(
    "Notificaciones push", movil, "En Progreso", user_ids=[(6, 0, pedro.ids)]
)
get_task(
    "Publicar en App Store", movil, "Nuevo",
    date_deadline=now + timedelta(days=15),
)

# ─── configuración del tablero del admin ────────────────────────────────────
settings = env["project.board.settings"]._get_settings()
settings.line_ids.unlink()
settings.column_ids.unlink()
settings.write(
    {
        "my_tasks_only": False,
        "line_ids": [
            (0, 0, {"project_id": web.id, "color": 4, "sequence": 1}),
            (0, 0, {"project_id": erp.id, "color": 10, "sequence": 2}),
            (0, 0, {"project_id": movil.id, "color": 9, "sequence": 3}),
        ],
        "column_ids": [
            (
                0,
                0,
                {
                    "name": "Test",
                    "sequence": 1,
                    "stage_ids": [
                        (
                            6,
                            0,
                            [
                                stages[(web.id, "Prueba 1")].id,
                                stages[(web.id, "Prueba 2")].id,
                                stages[(erp.id, "Test")].id,
                                stages[(movil.id, "Test")].id,
                            ],
                        )
                    ],
                },
            )
        ],
    }
)

env.cr.commit()
print("SEED OK")
