# Seed for the manual of helpdesk_team_restrict_visibility (Odoo 17).
# Creates two helpdesk teams (one restricted to its members, one open),
# example members, tickets and demo actions so the manual can navigate to a
# concrete team form and ticket list. Executed inside `odoo shell`; the global
# `env` is available. UI in Spanish (es_DO). Ends with env.cr.commit().

TZ = "America/Santo_Domingo"

# ── 0. Español (es_DO) ────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    try:
        env["base.language.install"].create(
            {"lang": "es_DO", "overwrite": True}
        ).lang_install()
    except Exception:
        env.cr.rollback()
env.ref("base.user_admin").write({"lang": "es_DO", "tz": TZ})

# ── 1. Usuarios de ejemplo (agentes de Mesa de Ayuda) ────────────────────────
group_user = env.ref("helpdesk.group_helpdesk_user")


def ensure_user(name, login):
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        user = env["res.users"].create(
            {
                "name": name,
                "login": login,
                "email": "%s@example.com" % login,
                "lang": "es_DO",
                "tz": TZ,
                "groups_id": [(6, 0, group_user.ids)],
            }
        )
    return user


ana = ensure_user("Ana Pérez (Servicio al Personal)", "ana.servicio")
luis = ensure_user("Luis Gómez (Suministro)", "luis.suministro")
admin = env.ref("base.user_admin")

# ── 2. Equipos ────────────────────────────────────────────────────────────────
Team = env["helpdesk.team"]


def ensure_team(name, members, restrict):
    team = Team.search([("name", "=", name)], limit=1)
    vals = {
        "name": name,
        "privacy_visibility": "portal",  # público: deja operativo el formulario web
        "restrict_internal_visibility": restrict,
        "member_ids": [(6, 0, members.ids)],
    }
    if team:
        team.write(vals)
    else:
        team = Team.create(vals)
    return team


team_personal = ensure_team("Servicio al Personal", admin | ana, True)
team_suministro = ensure_team("Suministro", admin | luis, True)

# ── 3. Tickets de ejemplo en el equipo restringido ───────────────────────────
Ticket = env["helpdesk.ticket"]
EJEMPLOS = [
    "Solicitud de carta de trabajo",
    "Actualización de datos personales",
    "Reembolso de gastos médicos",
]
for subject in EJEMPLOS:
    if not Ticket.search(
        [("name", "=", subject), ("team_id", "=", team_personal.id)], limit=1
    ):
        Ticket.create({"name": subject, "team_id": team_personal.id})

# ── 4. Acciones de demo para el manual (navegación determinista) ─────────────
def demo_action(xmlid_name, name, model, view_mode, domain, res_id=False):
    full = "helpdesk_team_restrict_visibility.%s" % xmlid_name
    if env.ref(full, raise_if_not_found=False):
        return
    vals = {
        "name": name,
        "res_model": model,
        "view_mode": view_mode,
        "domain": domain,
    }
    if res_id:
        vals["res_id"] = res_id
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {
            "module": "helpdesk_team_restrict_visibility",
            "name": xmlid_name,
            "model": "ir.actions.act_window",
            "res_id": act.id,
            "noupdate": True,
        }
    )


demo_action(
    "manual_team_form_action",
    "Equipo (configuración)",
    "helpdesk.team",
    "list,form",
    "[('id', '=', %d)]" % team_personal.id,
)
demo_action(
    "manual_teams_action",
    "Equipos de Mesa de Ayuda",
    "helpdesk.team",
    "kanban,list,form",
    "[('id', 'in', %s)]" % [team_personal.id, team_suministro.id],
)
demo_action(
    "manual_tickets_action",
    "Tickets — Servicio al Personal",
    "helpdesk.ticket",
    "list,form",
    "[('team_id', '=', %d)]" % team_personal.id,
)

env.cr.commit()
print(
    "SEED OK: equipos=%s tickets=%d miembros_personal=%s"
    % (
        Team.search([("id", "in", [team_personal.id, team_suministro.id])]).mapped(
            "name"
        ),
        Ticket.search_count([("team_id", "=", team_personal.id)]),
        team_personal.member_ids.mapped("name"),
    )
)
