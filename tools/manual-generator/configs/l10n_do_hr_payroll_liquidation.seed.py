# Seed for the manual of l10n_do_hr_payroll_liquidation (Liquidación por
# desvinculación). Builds, from a CLEAN DB, a Dominican payroll company with two
# terminated employees and their labour-severance liquidations:
#
#   * Juan Pérez  — RD$60,000/mes, 3 años 8 meses, salida por despido. Su
#     liquidación se calcula Y se confirma -> genera la nómina extraordinaria de
#     liquidación. Preaviso, cesantía y regalía van exentos; las vacaciones van
#     por la regla VAC (Salario Ordinario) y por tanto cotizan TSS e ISR.
#   * Ana Ruiz    — RD$30,000/mes, 3 meses de antigüedad. Su liquidación queda en
#     estado "Calculado" para mostrar la pantalla previa a confirmar (sin
#     vacaciones: la escala del Art. 180 exige MÁS de cinco meses).
#
# Se siembra además el historial de 12 nóminas mensuales validadas de Juan para
# que funcione el botón "Cargar Historial de Nómina". Ejecutado dentro de
# `odoo shell` (`env` disponible). Termina con env.cr.commit().
from datetime import date, datetime

from dateutil.relativedelta import relativedelta

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
TZ = "America/Santo_Domingo"

# ── 0. Español ────────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
# Run the rest of the seed in es_DO context so snapshot fields stored at compute
# time (e.g. hr.payslip.line.name, copied from the salary rule name) are captured
# in Spanish — mirroring a real es_DO user confirming a liquidation. The odoo
# shell env defaults to en_US, which would otherwise freeze English line names.
env = env(context=dict(env.context, lang="es_DO"))

# ── 1. Compañía RD ──────────────────────────────────────────────────────────
company.write(
    {
        "name": "Empresa Dominicana SRL",
        "country_id": do.id,
        "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
    }
)
company.partner_id.lang = "es_DO"
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback()
    company.write({"country_id": do.id})

# ── 1b. Contabilidad dominicana (plan de cuentas DO) ──────────────────────────
# Requiere l10n_do_accounting instalado (lo instala el generador vía
# `extra_modules` del config, o el setup script vía CLI). Si no está, se omite.
if env["ir.module.module"].search(
    [("name", "=", "l10n_do_accounting"), ("state", "=", "installed")]
):
    company.partner_id.write({"l10n_do_dgii_tax_payer_type": "taxpayer"})
    try:
        company.partner_id.with_context(no_vat_validation=True).vat = "131793916"
    except Exception:
        pass
    if company.chart_template != "do":
        env["account.chart.template"].try_loading(
            "do", company, install_demo=False, force_create=True
        )
    if company.account_fiscal_country_id != do:
        company.account_fiscal_country_id = do.id
    print("Contabilidad DO: plan=%s pais_fiscal=%s RNC=%s" % (
        company.chart_template, company.account_fiscal_country_id.code, company.vat))

# ── 2. Calendario RD 44h + estructura + diario ────────────────────────────────
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
salary_journal = env["account.journal"].search(
    [("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
if not salary_journal:
    salary_journal = env["account.journal"].create(
        {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id})
for struct in env["hr.payroll.structure"].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal

# ── 3. Causa de salida (despido) ──────────────────────────────────────────────
reason = env.ref("hr.departure_fired", raise_if_not_found=False) \
    or env["hr.departure.reason"].search([], limit=1)


# ── 4. Empleados desvinculados ────────────────────────────────────────────────
def make_employee(name, cedula, nss, wage, start, end):
    emp = env["hr.employee"].search([("identification_id", "=", cedula)], limit=1)
    if not emp:
        emp = env["hr.employee"].create({
            "name": name, "company_id": company.id, "country_id": do.id,
            "identification_id": cedula, "l10n_do_social_security_number": nss,
            "l10n_do_has_papers": True, "tz": TZ,
            "resource_calendar_id": calendar_rd.id,
            "date_version": start, "contract_date_start": start,
            "wage": wage, "structure_type_id": structure_type.id,
        })
    emp.version_id.write({"l10n_do_schedule_retentions": "distributed",
                          "resource_calendar_id": calendar_rd.id})
    emp.write({"departure_date": end,
               "departure_reason_id": reason.id if reason else False,
               "departure_description": "Cierre de operaciones del departamento."})
    return emp


juan = make_employee("Juan Pérez", "00112345678", "80001", 60000.0,
                     date(2023, 1, 15), date(2026, 9, 30))
ana = make_employee("Ana Ruiz", "00998877665", "80002", 30000.0,
                    date(2026, 3, 1), date(2026, 6, 30))

# ── 5. Historial de 12 nóminas validadas de Juan (para "Cargar Historial") ────
def seed_history(employee, date_end, months, salary):
    apagar = env.ref("l10n_do_hr_payroll.hr_rule_base")
    for i in range(months, 0, -1):
        date_from = (date_end.replace(day=1) - relativedelta(months=i))
        date_to = date_from + relativedelta(months=1, days=-1)
        exists = env["hr.payslip"].search(
            [("employee_id", "=", employee.id), ("date_from", "=", date_from)], limit=1)
        if exists:
            continue
        slip = env["hr.payslip"].create({
            "name": "Nómina %s" % date_from, "employee_id": employee.id,
            "version_id": employee.version_id.id, "struct_id": struct_base.id,
            "date_from": date_from, "date_to": date_to, "state": "validated",
            # done_date is set by Odoo on validation; we bypass that flow, so set
            # it explicitly. Core _compute_is_wrong_version compares
            # version.last_modified_date > done_date on validated/paid slips and
            # crashes (datetime > False) if done_date is empty.
            "done_date": datetime.combine(date_to, datetime.min.time()),
        })
        env["hr.payslip.line"].create({
            "slip_id": slip.id, "name": "Salario a Pagar",
            "salary_rule_id": apagar.id, "amount": salary, "total": salary,
        })


seed_history(juan, date(2026, 9, 30), 12, 60000.0)


# ── 6. Liquidaciones ──────────────────────────────────────────────────────────
def make_liquidation(employee, start, end, salary, fill_from_end=None):
    liq = env["l10n.do.hr.liquidation"].create({
        "employee_id": employee.id, "date_start": start, "date_end": end,
    })
    lines = liq.salary_line_ids.sorted("sequence")
    target = lines[-fill_from_end:] if fill_from_end else lines
    for line in target:
        line.write({"salary": salary, "commission": 0.0})
    liq.action_compute()
    return liq


def confirm_via_wizard(liquidations):
    """Emula el asistente de configuración de lote que abre action_confirm:
    crea el lote con los defaults de la acción y dispara la generación de las
    nóminas de liquidación (mismo camino que 'Generar lote de nómina' en la UI)."""
    action = liquidations.action_confirm()
    ctx = action["context"]
    run = env["hr.payslip.run"].with_context(**ctx).create({
        "name": ctx["default_name"],
        "date_start": ctx["default_date_start"],
        "date_end": ctx["default_date_end"],
        "structure_id": ctx["default_structure_id"],
        "company_id": ctx["default_company_id"],
        "l10n_do_extraordinary": ctx["default_l10n_do_extraordinary"],
        "l10n_do_is_liquidation": ctx["default_l10n_do_is_liquidation"],
    })
    run.with_context(**ctx).action_generate_liquidation_payslips()
    return run


# 6a. Juan: liquidación calculada Y confirmada -> nómina de liquidación
liq_juan = make_liquidation(juan, date(2023, 1, 15), date(2026, 9, 30), 60000.0)
confirm_via_wizard(liq_juan)

# 6b. Ana: liquidación solo calculada (pantalla previa a confirmar)
liq_ana = make_liquidation(ana, date(2026, 3, 1), date(2026, 6, 30), 30000.0, fill_from_end=4)

# 6c. Carlos: salida PARCIAL (9 de julio) que estrena los ajustes del segundo batch:
#   * Vacaciones ya tomadas -> se paga la PROPORCIÓN desde el último aniversario
#     (10 meses -> 11 días), en lugar de eliminar el concepto.
#   * Regalía prorrateada: 6 meses validados del año + período abierto 1-9 jul.
#   * Días laborados pendientes -> entrada DLAB con los días equivalentes en el
#     MISMO recibo de liquidación; la regla APAGAR los convierte en monto y
#     cotizan TSS/ISR junto con las vacaciones.
carlos = make_employee("Carlos Méndez", "00445566778", "80003", 60000.0,
                       date(2020, 9, 1), date(2026, 7, 9))
seed_history(carlos, date(2026, 7, 9), 12, 60000.0)
liq_carlos = env["l10n.do.hr.liquidation"].create({
    "employee_id": carlos.id, "date_start": date(2020, 9, 1), "date_end": date(2026, 7, 9),
    "vacations_taken": True, "include_worked_days": True, "current_salary": 60000.0,
})
liq_carlos.action_load_payroll_history()
liq_carlos.action_compute()
confirm_via_wizard(liq_carlos)


# ── 7. Acciones demo para las capturas ────────────────────────────────────────
def demo_action(xmlid, vals):
    existing = env.ref("l10n_do_hr_payroll_liquidation.%s" % xmlid, raise_if_not_found=False)
    if existing:
        return existing
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create({
        "module": "l10n_do_hr_payroll_liquidation", "name": xmlid,
        "model": "ir.actions.act_window", "res_id": act.id, "noupdate": True,
    })
    return act


demo_action("demo_employee_juan", {
    "name": "Empleado - Juan Pérez", "res_model": "hr.employee",
    "view_mode": "form", "res_id": juan.id, "domain": "[('id', '=', %d)]" % juan.id,
})
demo_action("demo_liq_juan", {
    "name": "Liquidación - Juan Pérez", "res_model": "l10n.do.hr.liquidation",
    "view_mode": "form", "res_id": liq_juan.id,
})
demo_action("demo_liq_ana", {
    "name": "Liquidación - Ana Ruiz", "res_model": "l10n.do.hr.liquidation",
    "view_mode": "form", "res_id": liq_ana.id,
})
demo_action("demo_payslip_juan", {
    "name": "Nómina de Liquidación - Juan Pérez", "res_model": "hr.payslip",
    "view_mode": "form", "res_id": liq_juan.payslip_id.id,
})
demo_action("demo_run_juan", {
    "name": "Lote de Liquidación - Juan Pérez", "res_model": "hr.payslip.run",
    "view_mode": "form", "res_id": liq_juan.payslip_run_id.id,
})
demo_action("demo_liq_carlos", {
    "name": "Liquidación - Carlos Méndez", "res_model": "l10n.do.hr.liquidation",
    "view_mode": "form", "res_id": liq_carlos.id,
})
demo_action("demo_payslip_carlos", {
    "name": "Nómina de Liquidación - Carlos Méndez", "res_model": "hr.payslip",
    "view_mode": "form", "res_id": liq_carlos.payslip_id.id,
})

env.cr.commit()

# ── 8. Reporte ────────────────────────────────────────────────────────────────
errors = []
amounts = {line.concept: line.amount for line in liq_juan.line_ids}
expected = {"preaviso": 70499.37, "cesantia": 191355.43,
            "vacaciones": 35249.69, "regalia": 45000.00}
for concept, val in expected.items():
    if abs(amounts.get(concept, 0.0) - val) > 0.01:
        errors.append("Juan %s: esperado %.2f, dio %.2f" % (concept, val, amounts.get(concept, 0.0)))
if abs(liq_juan.amount_total - 342104.49) > 0.01:
    errors.append("Juan total: esperado 342104.49, dio %.2f" % liq_juan.amount_total)
if abs(liq_juan.avg_daily_salary - 2517.83) > 0.01:
    errors.append("Juan salario diario: esperado 2517.83, dio %.2f" % liq_juan.avg_daily_salary)

# Ana: las cifras del caso de antigüedad corta que cita el manual.
a_amounts = {line.concept: line.amount for line in liq_ana.line_ids}
a_expected = {"preaviso": 8812.42, "cesantia": 7553.50,
              "vacaciones": 0.00, "regalia": 10000.00}
for concept, val in a_expected.items():
    if abs(a_amounts.get(concept, 0.0) - val) > 0.01:
        errors.append("Ana %s: esperado %.2f, dio %.2f" % (concept, val, a_amounts.get(concept, 0.0)))


def line_total(payslip, code):
    return sum(payslip.line_ids.filtered(lambda l: l.code == code).mapped("total"))


# Preaviso, cesantía y regalía conservan su exención: cada uno llega íntegro a su
# regla y ninguno entra en el salario cotizable. Las vacaciones sí cotizan.
juan_slip = liq_juan.payslip_id
for code, concept in (("PREA", "preaviso"), ("CESA", "cesantia"), ("REPA", "regalia")):
    if abs(line_total(juan_slip, code) - amounts.get(concept, 0.0)) > 0.01:
        errors.append("Juan %s: la regla no reproduce el concepto %s" % (code, concept))
if abs(line_total(juan_slip, "VAC") - amounts.get("vacaciones", 0.0)) > 0.01:
    errors.append("Juan VAC: la regla no reproduce las vacaciones calculadas")
if line_total(juan_slip, "VACL") != 0.0:
    errors.append("Juan: la liquidación no debe usar la regla exenta VACL")

saltss = line_total(juan_slip, "SALTSS")
if abs(saltss - amounts.get("vacaciones", 0.0)) > 0.01:
    errors.append("Juan SALTSS (%.2f) debe ser solo las vacaciones (%.2f)"
                  % (saltss, amounts.get("vacaciones", 0.0)))

param = env["hr.rule.parameter"]
sfs = line_total(juan_slip, "SFSE")
afp = line_total(juan_slip, "SVDSE")
expected_sfs = -(saltss * param._get_parameter_from_code("SFS_RET", liq_juan.date_end) / 100)
expected_afp = -(saltss * param._get_parameter_from_code("AFP_RET", liq_juan.date_end) / 100)
if abs(sfs - expected_sfs) > 0.01:
    errors.append("Juan SFSE: esperado %.2f, dio %.2f" % (expected_sfs, sfs))
if abs(afp - expected_afp) > 0.01:
    errors.append("Juan SVDSE: esperado %.2f, dio %.2f" % (expected_afp, afp))

retentions = sfs + afp + line_total(juan_slip, "ISR")
net = line_total(juan_slip, "NET")
if abs(net - (liq_juan.amount_total + retentions)) > 0.01:
    errors.append("Juan NET (%.2f) != total (%.2f) + retenciones (%.2f)"
                  % (net, liq_juan.amount_total, retentions))

# Carlos: salida parcial, vacaciones proporcionales y días laborados en el MISMO
# recibo, con la regla APAGAR convirtiendo los días equivalentes en monto.
c_amounts = {line.concept: line.amount for line in liq_carlos.line_ids}
c_expected = {"vacaciones": 60000 / 23.83 * 11, "regalia": (360000 + 60000 / 23.83 * 7.5) / 12,
              "worked_days": 60000 / 23.83 * 7.5}
for concept, val in c_expected.items():
    if abs(c_amounts.get(concept, 0.0) - val) > 0.01:
        errors.append("Carlos %s: esperado %.2f, dio %.2f" % (concept, val, c_amounts.get(concept, 0.0)))

carlos_slip = liq_carlos.payslip_id
if env["hr.payslip"].search_count([("employee_id", "=", carlos.id),
                                   ("payslip_run_id", "=", False)]) != 12:
    errors.append("Carlos: los días laborados no deben generar un recibo ordinario aparte")
dlab_input = carlos_slip.input_line_ids.filtered(lambda i: i.code == "DLAB")
if len(dlab_input) != 1 or abs(dlab_input.amount - 7.5) > 0.01:
    errors.append("Carlos: la entrada DLAB debe llevar 7.5 días equivalentes")
if abs(line_total(carlos_slip, "APAGAR") - c_expected["worked_days"]) > 0.01:
    errors.append("Carlos APAGAR (%.2f) != días laborados (%.2f)"
                  % (line_total(carlos_slip, "APAGAR"), c_expected["worked_days"]))
if line_total(carlos_slip, "DLAB") != 0.0:
    errors.append("Carlos: la regla DLAB duplica el cálculo de APAGAR")
c_saltss = line_total(carlos_slip, "SALTSS")
c_base = c_expected["vacaciones"] + c_expected["worked_days"]
if abs(c_saltss - c_base) > 0.01:
    errors.append("Carlos SALTSS (%.2f) != vacaciones + días laborados (%.2f)" % (c_saltss, c_base))
if line_total(carlos_slip, "SFSE") >= 0.0 or line_total(carlos_slip, "SVDSE") >= 0.0:
    errors.append("Carlos: vacaciones y días laborados deben retener TSS")

if errors:
    print("SEED FAIL:")
    for e in errors:
        print("  -", e)
else:
    print("SEED OK: Juan confirmado (total %.2f, NET %.2f, retenciones %.2f); "
          "Ana calculada (%s meses)" % (
              liq_juan.amount_total, net, retentions, liq_ana.total_months))
    print("  Juan conceptos:", {k: round(v, 2) for k, v in amounts.items()})
    print("  Juan recibo   :", {c: round(line_total(juan_slip, c), 2)
                                for c in ("PREA", "CESA", "VAC", "REPA", "SALTSS",
                                          "SFSE", "SVDSE", "ISR", "NET")})
    print("  Carlos recibo :", {c: round(line_total(carlos_slip, c), 2)
                                for c in ("APAGAR", "VAC", "REPA", "SALTSS",
                                          "SFSE", "SVDSE", "ISR", "NET")})
