# Datos de ejemplo para el manual de l10n_do_hr_payroll_news_attendance (línea 20.0).
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date, datetime, timedelta

MODULE = "l10n_do_hr_payroll_news_attendance"
TZ = "America/Santo_Domingo"
UTC_OFFSET = 4

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)
period_start = period_end.replace(day=1)

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": TZ, "tour_enabled": False})

do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
company = env.ref("base.main_company")
company.write({
    "name": "Empresa Dominicana SRL",
    "country_id": do.id,
    "tz": TZ,
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
    "attendance_validation": "no_validation",
    "attendance_work_entry_type_id": env.ref("hr_work_entry.generic_work_entry_type_attendance").id,
})
company.partner_id.lang = "es_DO"
try:
    with env.cr.savepoint():
        company.currency_id = dop.id
except Exception:
    pass
if not admin.employee_id:
    env["hr.employee"].create({"name": "Administrador", "user_id": admin.id})
env = env(user=admin.id, context=dict(env.context, lang="es_DO"))

attendances = []
for dow in range(5):
    attendances.append((0, 0, {"dayofweek": str(dow), "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
    attendances.append((0, 0, {"dayofweek": str(dow), "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}))
attendances.append((0, 0, {"dayofweek": "5", "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
calendar_rd = env["resource.calendar"].create({
    "name": "Jornada RD 44 horas", "company_id": company.id, "attendance_ids": attendances,
})
company.resource_calendar_id = calendar_rd

stype = env.ref("l10n_do_hr_payroll.structure_type_employee")
stype.write({"default_resource_calendar_id": calendar_rd.id, "default_schedule_pay": "monthly"})
struct_base = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
journal = env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
if not journal:
    journal = env["account.journal"].create({"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id})
for struct in env["hr.payroll.structure"].search([("journal_id", "=", False)]):
    struct.journal_id = journal

time_rule = env.ref("hr_work_entry.hr_time_rule_employee_schedule")

contract_start = date(today.year - 1, 1, 1)
emp = env["hr.employee"].create({
    "name": "Carlos Méndez", "company_id": company.id, "country_id": do.id,
    "identification_id": "00112345678", "l10n_do_social_security_number": "90001",
    "l10n_do_has_papers": True, "sex": "male", "birthday": "1988-03-15",
    "tz": TZ, "resource_calendar_id": calendar_rd.id,
    "date_version": contract_start, "contract_date_start": contract_start,
    "wage": 30000.0, "structure_type_id": stype.id,
})
emp.version_id.write({"attendance_based": True, "resource_calendar_id": calendar_rd.id})


def at_utc(d, local_hour):
    return datetime(d.year, d.month, d.day, local_hour + UTC_OFFSET, 0, 0)


ot_days, day = [], period_start
while day <= period_end and len(ot_days) < 3:
    if day.weekday() < 5:
        ot_days.append(day)
    day += timedelta(days=1)
sources = env["hr.attendance"]
for d in ot_days:
    sources |= env["hr.attendance"].create({"employee_id": emp.id, "check_in": at_utc(d, 8), "check_out": at_utc(d, 18)})

slip = env["hr.payslip"].create({
    "name": "Nómina %s" % emp.name, "employee_id": emp.id, "version_id": emp.version_id.id,
    "struct_id": struct_base.id, "date_from": period_start, "date_to": period_end,
})
slip.compute_sheet()
attachment = env["hr.salary.attachment"].search(
    [("employee_id", "=", emp.id), ("description", "=like", "[HE-ASISTENCIA]%")], limit=1
)


def demo_action(xmlid, vals):
    act = env["ir.actions.act_window"].sudo().create(vals)
    env["ir.model.data"].sudo().create({
        "module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })


def demo_list(name, model, arch):
    return env["ir.ui.view"].sudo().create({"name": name, "model": model, "type": "list", "arch": arch}).id


demo_action("demo_version_action", {
    "name": "Configuración de nómina (contrato)", "res_model": "hr.version",
    "view_mode": "form", "res_id": emp.version_id.id, "domain": "[('id', '=', %d)]" % emp.version_id.id,
})
demo_action("demo_time_rule_action", {
    "name": "Regla de tiempo", "res_model": "hr.time.rule",
    "view_mode": "form", "res_id": time_rule.id, "domain": "[('id', '=', %d)]" % time_rule.id,
})
demo_action("demo_ot_lines_action", {
    "name": "Horas extra (Asistencia)", "res_model": "hr.attendance", "view_mode": "list",
    "view_id": demo_list("demo.ot.attendance.list", "hr.attendance", """<list create="0" edit="0" default_order="check_in asc">
        <field name="employee_id" string="Empleado"/><field name="check_in" string="Desde"/>
        <field name="check_out" string="Hasta"/><field name="work_entry_type_id" string="Tipo de tiempo"/>
        <field name="time_rule_id" string="Regla"/><field name="worked_hours" string="Horas" sum="Total"/>
        <field name="state" string="Estado"/></list>"""),
    "domain": "[('employee_id', '=', %d)]" % emp.id,
})
demo_action("demo_payslip_action", {
    "name": "Recibo de nómina", "res_model": "hr.payslip",
    "view_mode": "form", "res_id": slip.id, "domain": "[('id', '=', %d)]" % slip.id,
})
demo_action("demo_worked_days_action", {
    "name": "Días trabajados del recibo", "res_model": "hr.payslip.worked_days", "view_mode": "list",
    "view_id": demo_list("demo.worked.days.list", "hr.payslip.worked_days", """<list create="0" edit="0">
        <field name="work_entry_type_id" string="Tipo"/><field name="code" string="Código"/>
        <field name="number_of_days" string="Días"/><field name="number_of_hours" string="Horas"/></list>"""),
    "domain": "[('payslip_id', '=', %d)]" % slip.id,
})
demo_action("demo_attachment_action", {
    "name": "Ajuste de nómina [HE-ASISTENCIA]", "res_model": "hr.salary.attachment",
    "view_mode": "form", "res_id": attachment.id, "domain": "[('id', '=', %d)]" % attachment.id,
})
demo_action("demo_hel_input_action", {
    "name": "Entrada de horas extra (HEL)", "res_model": "hr.payslip.input", "view_mode": "list",
    "view_id": demo_list("demo.hel.input.list", "hr.payslip.input", """<list create="0" edit="0">
        <field name="payslip_id" string="Recibo"/><field name="code" string="Código"/>
        <field name="name" string="Concepto"/><field name="amount" string="Horas"/></list>"""),
    "domain": "[('payslip_id', '=', %d)]" % slip.id,
})
demo_action("demo_hel_lines_action", {
    "name": "Líneas del recibo", "res_model": "hr.payslip.line", "view_mode": "list",
    "view_id": demo_list("demo.payslip.line.list", "hr.payslip.line", """<list create="0" edit="0" default_order="sequence">
        <field name="code" string="Código"/><field name="name" string="Concepto"/>
        <field name="quantity" string="Cantidad"/><field name="total" string="Monto"/></list>"""),
    "domain": "[('slip_id', '=', %d), ('code', 'in', ['BASE', 'HEL', 'BRUTO', 'SFSE', 'SVDSE', 'NET'])]" % slip.id,
})

env.cr.commit()
ot_hours = sum(slip.worked_days_line_ids.filtered(lambda w: w.code == "040.00").mapped("number_of_hours"))
hel_in = sum(slip.input_line_ids.filtered(lambda i: i.code == "HEL").mapped("amount"))
hel_amt = sum(slip.line_ids.filtered(lambda r: r.code == "HEL").mapped("total"))
print("SEED OK: empleado=%s horas_extra=%.1f HEL_input=%.1f HEL_pago=%.2f adjunto=%s periodo=%s" % (
    emp.name, ot_hours, hel_in, hel_amt, attachment.display_name, period_start.strftime("%m/%Y")))
