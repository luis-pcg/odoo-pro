# Seed for the manual of l10n_do_gamification_hr_news (badges that pay).
# Builds, from a CLEAN DB, the full flow: RD payroll company -> sellers with
# users/employees -> badge configured to pay an employee news -> 100% native
# sales challenge with that badge as reward -> goals reached -> challenge
# closed -> badges granted (one grant without news: user without employee) ->
# employee news confirmed -> HR validation -> salary attachment -> payslip
# input INC -> payslip validated (attachment closed).
# Executed inside `odoo shell` (`env` is provided).
from datetime import date, timedelta

today = date.today()
period_start = today.replace(day=1)
period_end = (period_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
TZ = "America/Santo_Domingo"

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True

errors = []
report = []

# ── 0. Español ────────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"

# ── 1. Compañía RD ────────────────────────────────────────────────────────────
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
    company.write({"country_id": do.id})

# ── 2. Calendario RD 44h + estructura ─────────────────────────────────────────
attendances = []
for dow in range(5):
    attendances.append((0, 0, {"name": "Mañana", "dayofweek": str(dow),
                               "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
    attendances.append((0, 0, {"name": "Tarde", "dayofweek": str(dow),
                               "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}))
attendances.append((0, 0, {"name": "Sábado", "dayofweek": "5",
                           "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
calendar_rd = env["resource.calendar"].search([("name", "=", "Jornada RD 44 horas")], limit=1)
if not calendar_rd:
    calendar_rd = env["resource.calendar"].create({
        "name": "Jornada RD 44 horas", "company_id": company.id, "tz": TZ,
        "hours_per_day": 8, "attendance_ids": attendances,
    })
company.resource_calendar_id = calendar_rd

structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
structure_type.write({"default_resource_calendar_id": calendar_rd.id, "default_schedule_pay": "monthly"})
struct_base = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
salary_journal = env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
if not salary_journal:
    salary_journal = env["account.journal"].create(
        {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id})
for struct in env["hr.payroll.structure"].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal

# ── 3. Vendedores: usuarios + empleados (uno sin empleado a propósito) ───────
contract_start = date(today.year - 1, 1, 1)
group_user = env.ref("base.group_user")


def make_user(name, login):
    user = env["res.users"].search([("login", "=", login)], limit=1)
    if not user:
        user = env["res.users"].create({
            "name": name, "login": login, "email": login,
            "group_ids": [(4, group_user.id)],
        })
    return user


SELLERS = [
    # name, login, cedula, nss, wage, sales (goal current, target is 10)
    ("Ana Féliz", "ana.feliz@example.com", "00120000001", "91001", 45000.0, 12),
    ("Carlos Mota", "carlos.mota@example.com", "00120000002", "91002", 60000.0, 15),
    ("Julia Peña", "julia.pena@example.com", "00120000003", "91003", 30000.0, 6),
]
users = env["res.users"]
employees = env["hr.employee"]
sales_by_user = {}
for name, login, cedula, nss, wage, sales in SELLERS:
    user = make_user(name, login)
    emp = env["hr.employee"].search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = env["hr.employee"].create({
            "name": name, "company_id": company.id, "country_id": do.id,
            "identification_id": cedula, "l10n_do_social_security_number": nss,
            "l10n_do_has_papers": True, "tz": TZ,
            "resource_calendar_id": calendar_rd.id,
            "date_version": contract_start, "contract_date_start": contract_start,
            "wage": wage, "structure_type_id": structure_type.id,
            "user_id": user.id,
        })
    emp.version_id.write({"l10n_do_schedule_retentions": "distributed",
                          "resource_calendar_id": calendar_rd.id})
    users |= user
    employees |= emp
    sales_by_user[user.id] = sales

# Roberto has a user but NO employee: demonstrates the error handling.
user_roberto = make_user("Roberto Vargas", "roberto.vargas@example.com")
users |= user_roberto
sales_by_user[user_roberto.id] = 11

# ── 4. Insignia precargada: solo se configura el monto ───────────────────────
# The module ships the badge with amount 0; the admin sets the amount (the
# only configuration step) before using it as a challenge reward.
news_type = env.ref("l10n_do_gamification_hr_news.news_type_gamification_reward")
badge = env.ref("l10n_do_gamification_hr_news.badge_goal_reward")
if badge.reward_amount != 5000.0:
    badge.reward_amount = 5000.0

definition = env["gamification.goal.definition"].search(
    [("name", "=", "Ventas cerradas del mes (registro manual)")], limit=1)
if not definition:
    definition = env["gamification.goal.definition"].create({
        "name": "Ventas cerradas del mes (registro manual)",
        "description": "Cantidad de ventas cerradas por el vendedor en el mes.",
        "computation_mode": "manually",
        "condition": "higher",
        "display_mode": "progress",
        "suffix": "ventas",
    })

challenge = env["gamification.challenge"].search([("name", "=", "Reto de Ventas del Mes")], limit=1)
if not challenge:
    challenge = env["gamification.challenge"].create({
        "name": "Reto de Ventas del Mes",
        "description": "Cerrar al menos 10 ventas en el mes. Quien lo logre recibe la "
                       "insignia y una recompensa de RD$5,000 pagada por nómina.",
        "period": "once",
        "user_domain": False,
        "user_ids": [(6, 0, users.ids)],
        "line_ids": [(0, 0, {"definition_id": definition.id, "target_goal": 10})],
        "reward_id": badge.id,  # única configuración de premio: la insignia nativa
        "reward_realtime": False,
        "challenge_category": "hr",
    })
challenge.action_start()

# ── 5. Registrar el avance de las metas y cerrar el desafío ──────────────────
goals = env["gamification.goal"].search([("challenge_id", "=", challenge.id)])
if len(goals) != 4:
    errors.append("Se esperaban 4 metas (una por participante), hay %d" % len(goals))
for goal in goals:
    current = sales_by_user.get(goal.user_id.id, 0)
    goal.write({"current": current})
    if current >= goal.target_goal:
        goal.action_reach()

challenge.write({"state": "done"})  # manual close -> badges (and their news)

# ── 6. Validación: otorgamientos de insignia y novedades ─────────────────────
# The badge grant is native and does NOT require an employee: Roberto gets his
# badge even though his news could not be created (native behavior untouched).
grants = env["gamification.badge.user"].search([("challenge_id", "=", challenge.id)])
paid_grants = grants.filtered("hr_news_id")
failed_grants = grants - paid_grants
if {g.user_id.name for g in grants} != {"Ana Féliz", "Carlos Mota", "Roberto Vargas"}:
    errors.append("Insignias otorgadas incorrectas: %s" % grants.mapped("user_id.name"))
if {g.user_id.name for g in paid_grants} != {"Ana Féliz", "Carlos Mota"}:
    errors.append("Otorgamientos con novedad incorrectos: %s" % paid_grants.mapped("user_id.name"))
if failed_grants.mapped("user_id.name") != ["Roberto Vargas"]:
    errors.append("Otorgamiento sin novedad incorrecto: %s" % failed_grants.mapped("user_id.name"))

news = paid_grants.mapped("hr_news_id")
if len(news) != 2 or set(news.mapped("state")) != {"confirm"}:
    errors.append("Se esperaban 2 novedades en estado 'confirm': %s" % news.mapped("state"))
if set(news.mapped("payslip_input_amount")) != {5000.0}:
    errors.append("Montos de novedad incorrectos: %s" % news.mapped("payslip_input_amount"))
if set(news.mapped("gamification_badge_id").ids) != {badge.id}:
    errors.append("Novedades no enlazadas a la insignia correcta")

report.append("Insignias: %d otorgadas; novedades: %d (%s); sin novedad: %s" % (
    len(grants), len(news), ", ".join(paid_grants.mapped("user_id.name")),
    ", ".join(failed_grants.mapped("user_id.name"))))

# ── 7. RRHH aprueba la novedad de Ana -> ajuste salarial ─────────────────────
# Carlos' news is left in 'confirm' on purpose: the manual captures the approval
# workflow on it. Ana's news goes through the full path down to the payslip.
ana_news = news.filtered(lambda n: n.employee_id.name == "Ana Féliz")
carlos_news = news - ana_news
ana_news.action_approve()  # validation_type 'manager' -> validate + attachment
ana_attachment = ana_news.salary_attachment_id
if not ana_attachment or ana_attachment.state != "open":
    errors.append("Se esperaba un ajuste salarial abierto para Ana: %s" % ana_attachment.mapped("state"))
if ana_attachment.monthly_amount != 5000.0:
    errors.append("Monto del ajuste incorrecto: %s" % ana_attachment.monthly_amount)
if ana_attachment.other_input_type_id.code != "INC":
    errors.append("Input type del ajuste incorrecto: %s" % ana_attachment.other_input_type_id.code)
if carlos_news.state != "confirm":
    errors.append("La novedad de Carlos debía quedar en 'confirm': %s" % carlos_news.state)

# ── 8. Nómina del mes de Ana: el incentivo entra como input INC ──────────────
ana_emp = employees.filtered(lambda e: e.name == "Ana Féliz")
ana_slip = env["hr.payslip"].search(
    [("employee_id", "=", ana_emp.id), ("date_from", "=", period_start)], limit=1)
if not ana_slip:
    ana_slip = env["hr.payslip"].create({
        "name": "Nómina %s" % ana_emp.name, "employee_id": ana_emp.id,
        "struct_id": struct_base.id,
        "date_from": period_start, "date_to": period_end,
    })
ana_slip.compute_sheet()

inc_inputs = ana_slip.input_line_ids.filtered(lambda i: i.input_type_id.code == "INC")
inc_lines = ana_slip.line_ids.filtered(lambda l: l.code == "INC")
if not inc_inputs or abs(sum(inc_inputs.mapped("amount")) - 5000.0) > 0.01:
    errors.append("Ana: input INC esperado 5000, hay %s" % inc_inputs.mapped("amount"))
if not inc_lines or abs(sum(inc_lines.mapped("total")) - 5000.0) > 0.01:
    errors.append("Ana: línea salarial INC esperada 5000, hay %s" % inc_lines.mapped("total"))
report.append("Ana Féliz: input INC=%.2f, línea INC=%.2f, NETO=%.2f" % (
    sum(inc_inputs.mapped("amount")), sum(inc_lines.mapped("total")),
    sum(ana_slip.line_ids.filtered(lambda l: l.code == "NET").mapped("total"))))

# ── 9. Validar la nómina de Ana: el ajuste one-time se cierra ────────────────
ana_slip.action_payslip_done()
if ana_attachment.state != "close":
    errors.append("El ajuste de Ana debía cerrarse al validar la nómina: %s" % ana_attachment.state)
if abs(ana_attachment.paid_amount - 5000.0) > 0.01:
    errors.append("Monto pagado del ajuste de Ana: %s" % ana_attachment.paid_amount)
report.append("Nómina de Ana validada: ajuste %s, pagado %.2f" % (
    ana_attachment.state, ana_attachment.paid_amount))
report.append("Novedad de Carlos en '%s' (pendiente de aprobación para el manual)" % carlos_news.state)

# ── 10. Acciones de demo para las capturas ────────────────────────────────────
def demo_action(xmlid, vals):
    existing = env.ref("l10n_do_gamification_hr_news.%s" % xmlid, raise_if_not_found=False)
    if existing:
        return
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": "l10n_do_gamification_hr_news", "name": xmlid,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })


demo_action("demo_news_type_action", {
    "name": "Tipo de novedad", "res_model": "l10n.do.hr.news.type",
    "view_mode": "form", "res_id": news_type.id,
})
demo_action("demo_challenge_action", {
    "name": "Desafío", "res_model": "gamification.challenge",
    "view_mode": "form", "res_id": challenge.id,
})
goal_view = env["ir.ui.view"].create({
    "name": "demo.goal.list", "model": "gamification.goal", "type": "list",
    "arch": """<list create="0" edit="0" default_order="current desc">
        <field name="user_id" string="Participante"/>
        <field name="definition_id" string="Meta"/>
        <field name="current" string="Actual"/>
        <field name="target_goal" string="Objetivo"/>
        <field name="completeness" string="Avance %" widget="progressbar"/>
        <field name="state" string="Estado"/></list>""",
})
demo_action("demo_goals_action", {
    "name": "Metas del desafío", "res_model": "gamification.goal",
    "view_mode": "list", "view_id": goal_view.id,
    "domain": "[('challenge_id', '=', %d)]" % challenge.id,
})
demo_action("demo_badge_action", {
    "name": "Insignia", "res_model": "gamification.badge",
    "view_mode": "form", "res_id": badge.id,
})
demo_action("demo_grants_action", {
    "name": "Otorgamientos de la insignia", "res_model": "gamification.badge.user",
    "view_mode": "list",
    "view_id": env.ref("l10n_do_gamification_hr_news.badge_user_list_view_hr_news").id,
    "domain": "[('challenge_id', '=', %d)]" % challenge.id,
})
demo_action("demo_news_list_action", {
    "name": "Novedades del desafío", "res_model": "l10n.do.hr.news",
    "view_mode": "list,form",
    "domain": "[('gamification_challenge_id', '=', %d)]" % challenge.id,
})
demo_action("demo_news_carlos_action", {
    "name": "Novedad de Carlos", "res_model": "l10n.do.hr.news",
    "view_mode": "form", "res_id": carlos_news.id,
})
demo_action("demo_news_form_action", {
    "name": "Novedad de Ana", "res_model": "l10n.do.hr.news",
    "view_mode": "form", "res_id": ana_news.id,
})
demo_action("demo_attachment_action", {
    "name": "Ajuste salarial", "res_model": "hr.salary.attachment",
    "view_mode": "form", "res_id": ana_attachment.id,
})
demo_action("demo_payslip_action", {
    "name": "Recibo de nómina", "res_model": "hr.payslip",
    "view_mode": "form", "res_id": ana_slip.id,
})
line_view = env["ir.ui.view"].create({
    "name": "demo.payslip.line.list", "model": "hr.payslip.line", "type": "list",
    "arch": """<list create="0" edit="0" default_order="employee_id,sequence">
        <field name="employee_id" string="Empleado"/>
        <field name="code" string="Código"/>
        <field name="name" string="Concepto"/>
        <field name="total" string="Monto"/></list>""",
})
demo_action("demo_payslip_lines_action", {
    "name": "Líneas de nómina", "res_model": "hr.payslip.line",
    "view_mode": "list", "view_id": line_view.id,
    "domain": "[('slip_id', '=', %d), ('code', 'in', ['BASIC', 'INC', 'NET'])]" % ana_slip.id,
})

env.cr.commit()
if errors:
    print("SEED FAIL:")
    for e in errors:
        print("  -", e)
else:
    print("SEED OK: reto cerrado, novedad de Ana pagada por nómina, Carlos pendiente de aprobar, 1 fallo controlado")
    for r in report:
        print("  ", r)
