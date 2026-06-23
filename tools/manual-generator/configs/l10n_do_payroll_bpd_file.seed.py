# Seed para el manual de l10n_do_payroll_bpd_file (archivo de pago Banco Popular).
# Reproduce el caso LEDTRIC SRL: un colaborador EXTRANJERO con pasaporte
# (passport_id) y SIN cedula dominicana (identification_id vacio), mas un
# colaborador dominicano de control. Deja un lote de nomina calculado y
# validado (estado "Hecho"/02_close) para que aparezca el boton "Archivo banco".
#
# Se ejecuta dentro de `odoo shell` (el global `env` esta disponible). La UI se
# pone en espanol (es_DO) para que las capturas usen la terminologia local.
# Termina con env.cr.commit().
from datetime import date, timedelta

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)
period_start = period_end.replace(day=1)

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
bank_popular = env.ref("l10n_do_banks.bank_popular")  # bic BPDODOSX

# ── 0. UI en espanol (es_DO) ─────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    wiz = env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True})
    wiz.lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"

# ── 1. Compania RD + RNC + numero de afiliacion BPD (5 digitos) ──────────────
company.write({
    "name": "LEDTRIC SRL",
    "country_id": do.id,
    "city": "Santo Domingo",
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
    "l10n_do_bpd_bank_number": "12345",
})
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback(); company.write({"country_id": do.id})
try:
    company.partner_id.with_context(no_vat_validation=True).vat = "131-79391-6"
except Exception:
    pass

# ── 2. Cuenta de banco de la empresa + diario BPD (is_bpd_bank) ──────────────
company_acc = env["res.partner.bank"].search(
    [("acc_number", "=", "78839748939")], limit=1) or env["res.partner.bank"].create({
        "acc_number": "78839748939",
        "partner_id": company.partner_id.id,
        "bank_id": bank_popular.id,
        "currency_id": dop.id,
    })
bpd_journal = env["account.journal"].search([("code", "=", "BPDPS")], limit=1)
if not bpd_journal:
    bpd_journal = env["account.journal"].create({
        "name": "BPD Nómina",
        "code": "BPDPS",
        "type": "bank",
        "bank_account_id": company_acc.id,
    })

# ── 3. Calendario + estructura + diario de salario ───────────────────────────
calendar_rd = env["resource.calendar"].search([("name", "=", "Jornada RD")], limit=1)
if not calendar_rd:
    attendances = []
    for dow in range(5):
        attendances.append((0, 0, {"name": "Mañana", "dayofweek": str(dow),
                                   "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
        attendances.append((0, 0, {"name": "Tarde", "dayofweek": str(dow),
                                   "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}))
    calendar_rd = env["resource.calendar"].create({
        "name": "Jornada RD", "company_id": company.id,
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

afp = env["res.partner"].search([("name", "=", "AFP Popular")], limit=1) or env["res.partner"].create(
    {"name": "AFP Popular", "is_company": True, "country_id": do.id})
ars = env["res.partner"].search([("name", "=", "ARS Universal")], limit=1) or env["res.partner"].create(
    {"name": "ARS Universal", "is_company": True, "country_id": do.id})
dept = env["hr.department"].search([("name", "=", "Operaciones")], limit=1) or env["hr.department"].create(
    {"name": "Operaciones"})
contract_start = date(today.year - 1, 1, 1)


def make_employee(name, fn, l1, l2, cedula, passport, country_birth):
    emp = env["hr.employee"].search([("name", "=", name)], limit=1)
    if emp:
        return emp
    emp = env["hr.employee"].create({
        "name": name,
        "company_id": company.id,
        "country_id": do.id,
        "country_of_birth": country_birth.id,
        "identification_id": cedula,    # vacio para el extranjero
        "passport_id": passport,
        "l10n_do_afp_partner_id": afp.id,
        "l10n_do_ars_partner_id": ars.id,
        "sex": "male",
        "birthday": "1990-05-10",
        "department_id": dept.id,
        "resource_calendar_id": calendar_rd.id,
        "date_version": contract_start,
        "contract_date_start": contract_start,
        "wage": 45000.0,
        "structure_type_id": structure_type.id,
    })
    emp.version_id.write({"l10n_do_schedule_retentions": "end_of_month"})
    acc = env["res.partner.bank"].create({
        "acc_number": "9610%s" % (cedula[-7:] if cedula else "0055443"),
        "partner_id": emp.work_contact_id.id,
        "bank_id": bank_popular.id,
        "account_type": "savings",
        "currency_id": dop.id,
    })
    emp.bank_account_ids = [(4, acc.id)]
    return emp


ven = env["res.country"].search([("code", "=", "VE")], limit=1) or do
# Colaborador EXTRANJERO: pasaporte, SIN cedula dominicana
foreign = make_employee("Carlos Pérez Marval", "Carlos", "Pérez", "Marval", "", "VEN1234567", ven)
# Colaborador DOMINICANO de control: cedula, sin pasaporte
local = make_employee("Juan Domínguez Reyes", "Juan", "Domínguez", "Reyes", "00112345678", "", do)

# ── 4. Lote de nomina calculado + validado (-> estado 02_close = "Hecho") ────
run = env["hr.payslip.run"].search([("name", "like", "Nómina LEDTRIC")], limit=1)
if not run:
    run = env["hr.payslip.run"].create({
        "name": "Nómina LEDTRIC %s" % period_start.strftime("%m/%Y"),
        "date_start": period_start, "date_end": period_end,
    })
slips = env["hr.payslip"]
for emp in (foreign, local):
    slip = env["hr.payslip"].search(
        [("employee_id", "=", emp.id), ("payslip_run_id", "=", run.id)], limit=1)
    if not slip:
        slip = env["hr.payslip"].create({
            "name": "Nómina %s" % emp.name,
            "employee_id": emp.id,
            "struct_id": struct_base.id,
            "date_from": period_start, "date_to": period_end,
            "payslip_run_id": run.id,
        })
    slips |= slip
slips.compute_sheet()
slips.filtered(lambda s: s.state not in ("validated", "paid")).write({"state": "validated"})

env.cr.commit()
print("SEED OK: company=%s rnc=%s journal=%s(is_bpd=%s) foreign_passport=%s local_cedula=%s run_state=%s" % (
    company.name, company.partner_id.vat, bpd_journal.name, bpd_journal.is_bpd_bank(),
    foreign.passport_id, local.identification_id, run.state))
