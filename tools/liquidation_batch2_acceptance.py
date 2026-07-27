"""Ejercita cada criterio de aceptación (AC-B2-01..10) y cada prueba del plan de
regresión (REG-01..09) del Informe de Pruebas Funcionales Batch 2, y reporta el
resultado por criterio. Se ejecuta dentro de `odoo shell` (`env` disponible).
"""

from datetime import date, datetime

from dateutil.relativedelta import relativedelta

RESULTS = []


def check(criterion, ok, detail=""):
    RESULTS.append((criterion, bool(ok), detail))
    return bool(ok)


company = env.company
do = env.ref("base.do")
company.write({"country_id": do.id})
struct = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
apagar_rule = env.ref("l10n_do_hr_payroll.hr_rule_base")
Liq = env["l10n.do.hr.liquidation"]

SEQ = [90000]


def cedula():
    SEQ[0] += 1
    return "009%08d" % SEQ[0]


def make_employee(name, wage, hire, departure=None, contract=True):
    vals = {
        "name": name,
        "company_id": company.id,
        "country_id": do.id,
        "identification_id": cedula(),
        "l10n_do_has_papers": True,
        "wage": wage,
        "date_version": hire,
        "structure_type_id": structure_type.id,
    }
    if contract:
        vals["contract_date_start"] = hire
    if departure:
        vals["departure_date"] = departure
    return env["hr.employee"].create(vals)


def seed_history(employee, date_end, months, salary):
    """Nóminas validadas mensuales terminando el mes anterior a date_end."""
    for i in range(months, 0, -1):
        ref = date_end.replace(day=1) - relativedelta(months=i)
        date_from = ref.replace(day=1)
        date_to = date_from + relativedelta(months=1, days=-1)
        slip = env["hr.payslip"].create({
            "name": "Nómina %s" % date_from,
            "employee_id": employee.id,
            "version_id": employee.version_id.id,
            "struct_id": struct.id,
            "date_from": date_from,
            "date_to": date_to,
            "state": "validated",
            "done_date": datetime.combine(date_to, datetime.min.time()),
        })
        env["hr.payslip.line"].create({
            "slip_id": slip.id,
            "name": "Salario a Pagar",
            "salary_rule_id": apagar_rule.id,
            "amount": salary,
            "total": salary,
        })


def fill_grid(liq, salary, months=12):
    lines = liq.salary_line_ids.sorted("sequence")
    for line in lines[-months:]:
        line.write({"salary": salary, "commission": 0.0})


def confirm(liquidations):
    """Emula el asistente de lote: crea el run con los defaults y genera."""
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


def total(payslip, code):
    return sum(payslip.line_ids.filtered(lambda l: l.code == code).mapped("total"))


def concept(liq, name):
    return liq.line_ids.filtered(lambda l: l.concept == name)


def vac_days(hire, exit_date, taken, wage=30000, months=12):
    liq = Liq.create({
        "employee_id": make_employee("Vac %s" % taken, wage, hire).id,
        "date_start": hire, "date_end": exit_date, "vacations_taken": taken,
    })
    fill_grid(liq, wage, months)
    liq.action_compute()
    return concept(liq, "vacaciones")


# ═══════════════════════════════════════════════════════════════════════════
# REG-01 / AC-B2-01 — vacaciones < 1 año no dependen del switch
# ═══════════════════════════════════════════════════════════════════════════
si = vac_days(date(2026, 1, 25), date(2026, 6, 30), True, months=6)
no = vac_days(date(2026, 1, 25), date(2026, 6, 30), False, months=6)
check("REG-01 / AC-B2-01  5m5d paga 6 días con el switch en Sí y en No",
      abs(si.days - 6.0) < 0.01 and abs(no.days - 6.0) < 0.01
      and abs(si.amount - no.amount) < 0.01,
      "Sí=%.2f días / No=%.2f días; montos %.2f vs %.2f" % (si.days, no.days, si.amount, no.amount))

exacto = vac_days(date(2026, 1, 30), date(2026, 6, 30), False, months=6)
check("REG-01b  5 meses exactos no genera derecho (Art. 180: 'más de cinco meses')",
      exacto.days == 0.0, "%.2f días" % exacto.days)

# ═══════════════════════════════════════════════════════════════════════════
# REG-02 — desde el primer aniversario el switch sí manda
# ═══════════════════════════════════════════════════════════════════════════
no2 = vac_days(date(2024, 1, 1), date(2026, 7, 1), False, wage=60000)
si2 = vac_days(date(2024, 1, 1), date(2026, 7, 1), True, wage=60000)
check("REG-02  2a6m: No = 14 días completos; Sí = proporción desde el aniversario",
      abs(no2.days - 14.0) < 0.01 and abs(si2.days - 6.0) < 0.01,
      "No=%.2f días / Sí=%.2f días" % (no2.days, si2.days))

# ═══════════════════════════════════════════════════════════════════════════
# REG-03 / REG-04 / AC-B2-02..06 — recibo único con los cinco conceptos
# ═══════════════════════════════════════════════════════════════════════════
emp = make_employee("Cinco Conceptos", 60000, date(2020, 9, 1), date(2026, 7, 9))
seed_history(emp, date(2026, 7, 9), 12, 60000)
liq = Liq.create({
    "employee_id": emp.id, "date_start": date(2020, 9, 1), "date_end": date(2026, 7, 9),
    "current_salary": 60000, "include_worked_days": True,
})
liq.action_load_payroll_history()
liq.action_compute()

conceptos = set(liq.line_ids.mapped("concept"))
check("REG-03a  se calculan los cinco conceptos (preaviso, cesantía, vacaciones, regalía, días laborados)",
      conceptos == {"preaviso", "cesantia", "vacaciones", "regalia", "worked_days"},
      str(sorted(conceptos)))

codigos = set(liq.line_ids.mapped("input_type_id.code"))
check("AC-B2-02a  los conceptos se envían a PREA/CESA/VAC/REPA/DLAB (sin VACL)",
      codigos == {"PREA", "CESA", "VAC", "REPA", "DLAB"}, str(sorted(codigos)))

antes = env["hr.payslip"].search([("employee_id", "=", emp.id)])
run = confirm(liq)
despues = env["hr.payslip"].search([("employee_id", "=", emp.id)])
nuevos = despues - antes
slip = liq.payslip_id

check("REG-03b / AC-B2-04  un único recibo extraordinario dentro del lote de liquidación",
      nuevos == slip and slip.payslip_run_id == run
      and slip.l10n_do_payslip_extraordinary and slip.l10n_do_is_liquidation,
      "recibos nuevos=%d, extraordinario=%s, liquidación=%s"
      % (len(nuevos), slip.l10n_do_payslip_extraordinary, slip.l10n_do_is_liquidation))

check("AC-B2-06  no se crea ningún recibo ordinario separado por días laborados",
      len(nuevos) == 1, "%d recibo(s) generado(s)" % len(nuevos))

entradas = {i.code: i.amount for i in slip.input_line_ids}
check("REG-03c  el recibo lleva las cinco entradas", len(entradas) == 5, str(sorted(entradas)))

worked = concept(liq, "worked_days")
check("AC-B2-05a  DLAB transfiere DÍAS, no monto",
      abs(entradas.get("DLAB", 0) - 7.5) < 0.01, "DLAB=%.2f (días esperados 7.5)" % entradas.get("DLAB", 0))
check("AC-B2-05b  APAGAR convierte los días en monto una sola vez (regla DLAB sin línea)",
      abs(total(slip, "APAGAR") - worked.amount) < 0.01 and total(slip, "DLAB") == 0.0,
      "APAGAR=%.2f, concepto=%.2f, línea DLAB=%.2f"
      % (total(slip, "APAGAR"), worked.amount, total(slip, "DLAB")))

check("AC-B2-02b  la liquidación usa VAC y no genera línea VACL exenta",
      abs(total(slip, "VAC") - concept(liq, "vacaciones").amount) < 0.01
      and total(slip, "VACL") == 0.0,
      "VAC=%.2f, VACL=%.2f" % (total(slip, "VAC"), total(slip, "VACL")))

base_esperada = concept(liq, "vacaciones").amount + worked.amount
check("REG-04a / AC-B2-03  VAC y DLAB alimentan el salario cotizable de TSS",
      abs(total(slip, "SALTSS") - base_esperada) < 0.01,
      "SALTSS=%.2f, esperado vacaciones+días=%.2f" % (total(slip, "SALTSS"), base_esperada))

param = env["hr.rule.parameter"]
sfs_esp = -(total(slip, "SALTSS") * param._get_parameter_from_code("SFS_RET", liq.date_end) / 100)
afp_esp = -(total(slip, "SALTSS") * param._get_parameter_from_code("AFP_RET", liq.date_end) / 100)
check("REG-04b  se retiene SFS y AFP sobre esa base, aunque la salida sea a mitad de mes",
      abs(total(slip, "SFSE") - sfs_esp) < 0.01 and abs(total(slip, "SVDSE") - afp_esp) < 0.01,
      "SFSE=%.2f (esp %.2f), SVDSE=%.2f (esp %.2f)"
      % (total(slip, "SFSE"), sfs_esp, total(slip, "SVDSE"), afp_esp))

dgii_esp = total(slip, "SALTSS") - abs(total(slip, "SFSE")) - abs(total(slip, "SVDSE"))
# Tolerancia de un centavo: la regla acumula sin redondear y aquí se recompone desde
# totales ya redondeados a la moneda.
check("REG-04c / AC-B2-03  la base de ISR es la cotizable neta de seguridad social",
      abs(total(slip, "SALDGII") - dgii_esp) <= 0.011,
      "SALDGII=%.2f, esperado %.2f" % (total(slip, "SALDGII"), dgii_esp))

exentos = {c: total(slip, c) for c in ("PREA", "CESA", "REPA")}
liq_exentos = {"PREA": concept(liq, "preaviso").amount,
               "CESA": concept(liq, "cesantia").amount,
               "REPA": concept(liq, "regalia").amount}
check("REG-04d  preaviso, cesantía y regalía llegan íntegros y NO entran en la base cotizable",
      all(abs(exentos[c] - liq_exentos[c]) < 0.01 for c in exentos)
      and abs(total(slip, "SALTSS") - base_esperada) < 0.01,
      str({c: round(v, 2) for c, v in exentos.items()}))

# ISR con base alta: mismo escenario con sueldo que supere el tramo exento
emp_isr = make_employee("ISR Alto", 150000, date(2020, 9, 1), date(2026, 7, 9))
liq_isr = Liq.create({
    "employee_id": emp_isr.id, "date_start": date(2020, 9, 1), "date_end": date(2026, 7, 9),
    "current_salary": 150000,
})
fill_grid(liq_isr, 150000)
liq_isr.action_compute()
confirm(liq_isr)
check("AC-B2-03b  el ISR se retiene cuando la base anualizada supera el tramo exento",
      total(liq_isr.payslip_id, "ISR") < 0.0,
      "ISR=%.2f sobre SALDGII=%.2f" % (total(liq_isr.payslip_id, "ISR"),
                                       total(liq_isr.payslip_id, "SALDGII")))

# ═══════════════════════════════════════════════════════════════════════════
# R2 / R3 — tabla de días equivalentes y tope al salario mensual
# ═══════════════════════════════════════════════════════════════════════════
TABLA = [(date(2026, 7, 1), 1.00, 3147.29), (date(2026, 7, 4), 3.50, 11015.53),
         (date(2026, 7, 5), 3.50, 11015.53), (date(2026, 7, 9), 7.50, 23604.70),
         (date(2026, 7, 31), 23.83, 75000.00)]
fallos = []
for salida, dias_esp, monto_esp in TABLA:
    e = make_employee("Dias %s" % salida, 75000, date(2020, 1, 1), salida)
    seed_history(e, salida, 6, 75000)
    lq = Liq.create({
        "employee_id": e.id, "date_start": date(2020, 1, 1), "date_end": salida,
        "current_salary": 75000, "include_worked_days": True,
    })
    lq.action_load_payroll_history()
    lq.action_compute()
    w = concept(lq, "worked_days")
    if abs(w.days - dias_esp) > 0.01 or abs(w.amount - monto_esp) > 0.01:
        fallos.append("%s: %.2f días/%.2f (esp %.2f/%.2f)"
                      % (salida, w.days, w.amount, dias_esp, monto_esp))
check("R2 / R3  tabla de días equivalentes y tope al salario mensual (5 fechas)",
      not fallos, "; ".join(fallos) or "01/07=1.00, 04/07=3.50, 05/07=3.50, 09/07=7.50, 31/07=23.83 (RD$75,000)")

# ═══════════════════════════════════════════════════════════════════════════
# REG-05 / AC-B2-07 — fechas históricas
# ═══════════════════════════════════════════════════════════════════════════
emp_2025 = make_employee("Salida 2025", 50000, date(2020, 1, 1), date(2025, 12, 17))
liq_2025 = Liq.create({
    "employee_id": emp_2025.id, "date_start": date(2020, 1, 1), "date_end": date(2025, 12, 17),
})
fill_grid(liq_2025, 50000)
try:
    liq_2025.action_compute()
    calc_ok, calc_err = True, ""
except Exception as error:
    calc_ok, calc_err = False, str(error)[:160]
check("REG-05 / AC-B2-07  el CÁLCULO de una salida 2025 resuelve las escalas legales",
      calc_ok and liq_2025.state == "computed" and liq_2025.amount_total > 0,
      calc_err or "total=%.2f, preaviso=%.2f días, vacaciones=%.2f días, divisor=%.2f"
      % (liq_2025.amount_total, concept(liq_2025, "preaviso").days,
         concept(liq_2025, "vacaciones").days, liq_2025.divisor))

gen_err = ""
if calc_ok:
    try:
        confirm(liq_2025)
        gen_ok, gen_full = True, ""
    except Exception as error:
        gen_ok, gen_full = False, str(error)
        gen_err = gen_full.replace("\n", " ")[:200]
else:
    gen_ok, gen_full = False, ""
accionable = all(t in gen_full for t in ("SFS_TOPE", "AFP_TOPE", "SRL_TOPE",
                                         "2025", "Rule Parameters"))
check("REG-05b  la GENERACIÓN del recibo 2025 pide los topes TSS de ese año, listándolos "
      "todos en un mensaje accionable",
      gen_ok or accionable, gen_err or "recibo generado sin faltantes")

# Cargando los topes reales del período, la liquidación 2025 se genera completa:
# el bloqueo anterior es de DATOS, no de lógica.
TOPES_2025 = {"SFS_TOPE": 214284.0, "AFP_TOPE": 428568.0, "SRL_TOPE": 85713.6}
for code, value in TOPES_2025.items():
    env["hr.rule.parameter.value"].create({
        "rule_parameter_id": env["hr.rule.parameter"].search([("code", "=", code)], limit=1).id,
        "date_from": date(2025, 1, 1),
        "parameter_value": str(value),
    })
env.registry.clear_cache()
emp_2025b = make_employee("Salida 2025 con topes", 50000, date(2020, 1, 1), date(2025, 12, 17))
liq_2025b = Liq.create({
    "employee_id": emp_2025b.id, "date_start": date(2020, 1, 1), "date_end": date(2025, 12, 17),
})
fill_grid(liq_2025b, 50000)
liq_2025b.action_compute()
try:
    confirm(liq_2025b)
    con_topes, con_topes_err = liq_2025b.state == "done", ""
except Exception as error:
    con_topes, con_topes_err = False, str(error).replace("\n", " ")[:180]
check("REG-05c  con los topes del año cargados, la liquidación 2025 se genera completa",
      con_topes, con_topes_err or "recibo 2025 generado, SFSE=%.2f"
      % total(liq_2025b.payslip_id, "SFSE"))

# Mensaje accionable cuando falta un valor
faltante = env.ref("l10n_do_hr_payroll_liquidation.hr_rule_parameter_liq_preaviso_scale_1992")
faltante_data = (faltante.rule_parameter_id, faltante.date_from, faltante.parameter_value)
faltante.unlink()
env.registry.clear_cache()
emp_msg = make_employee("Sin Escala", 50000, date(2020, 1, 1), date(2025, 12, 17))
liq_msg = Liq.create({
    "employee_id": emp_msg.id, "date_start": date(2020, 1, 1), "date_end": date(2025, 12, 17),
})
fill_grid(liq_msg, 50000)
try:
    liq_msg.action_compute()
    msg = ""
except Exception as error:
    msg = str(error)
check("H-04  si falta un parámetro, el mensaje nombra el código y la fecha",
      "LIQ_PREAVISO_SCALE" in msg and "2025" in msg, msg.replace("\n", " ")[:170])
env["hr.rule.parameter.value"].create({
    "rule_parameter_id": faltante_data[0].id,
    "date_from": faltante_data[1],
    "parameter_value": faltante_data[2],
})
env.registry.clear_cache()

# ═══════════════════════════════════════════════════════════════════════════
# REG-06 / AC-B2-08 — dominio y validación de empleado
# ═══════════════════════════════════════════════════════════════════════════
emp_arch = make_employee("Archivado", 40000, date(2021, 1, 1))
liq_arch = Liq.create({
    "employee_id": emp_arch.id, "date_start": date(2021, 1, 1), "date_end": date(2026, 6, 30),
})
fill_grid(liq_arch, 40000)
elegible_antes = emp_arch.l10n_do_liquidation_eligible
emp_arch.action_archive()
en_selector = emp_arch.id in env["hr.employee"].search(
    [("l10n_do_liquidation_eligible", "=", True)]).ids
try:
    liq_arch.action_compute()
    bloqueado = False
except Exception:
    bloqueado = True
check("REG-06a / AC-B2-08  empleado archivado: fuera del selector y bloqueado por el servidor",
      elegible_antes and not en_selector and bloqueado,
      "elegible antes=%s, en selector tras archivar=%s, cálculo bloqueado=%s"
      % (elegible_antes, en_selector, bloqueado))
check("REG-06c  la liquidación existente sigue consultándose tras archivar al empleado",
      liq_arch.employee_id == emp_arch, "employee_id resuelve: %s" % liq_arch.employee_id.display_name)

emp_sin = make_employee("Sin Contrato", 40000, date(2021, 1, 1), contract=False)
liq_sin = Liq.create({
    "employee_id": emp_sin.id, "date_start": date(2021, 1, 1), "date_end": date(2026, 6, 30),
})
fill_grid(liq_sin, 40000)
try:
    liq_sin.action_compute()
    bloq_sin = False
except Exception:
    bloq_sin = True
check("REG-06b / AC-B2-08  empleado sin contrato vigente: fuera del selector y bloqueado",
      not emp_sin.l10n_do_liquidation_eligible
      and emp_sin.id not in env["hr.employee"].search(
          [("l10n_do_liquidation_eligible", "=", True)]).ids
      and bloq_sin,
      "elegible=%s, bloqueado=%s" % (emp_sin.l10n_do_liquidation_eligible, bloq_sin))

# ═══════════════════════════════════════════════════════════════════════════
# REG-07 / AC-B2-09 — advertencia de historial incompleto
# ═══════════════════════════════════════════════════════════════════════════
emp_hist = make_employee("Historial Corto", 50000, date(2020, 1, 1))
liq_hist = Liq.create({
    "employee_id": emp_hist.id, "date_start": date(2020, 1, 1), "date_end": date(2026, 6, 30),
})
fill_grid(liq_hist, 50000, months=6)
aviso = bool(liq_hist.history_warning)
liq_hist.action_compute()
calculo_ok = liq_hist.state == "computed"
fill_grid(liq_hist, 50000, months=12)
aviso_tras_completar = bool(liq_hist.history_warning)
check("REG-07 / AC-B2-09  historial incompleto avisa, no bloquea, y el aviso desaparece al completar",
      aviso and calculo_ok and not aviso_tras_completar,
      "aviso con 6 períodos=%s, calculó=%s, aviso con 12=%s" % (aviso, calculo_ok, aviso_tras_completar))

emp_corto = make_employee("Recién Entrado", 30000, date(2026, 2, 1))
liq_corto = Liq.create({
    "employee_id": emp_corto.id, "date_start": date(2026, 2, 1), "date_end": date(2026, 6, 30),
})
fill_grid(liq_corto, 30000, months=4)
check("REG-07b  una relación menor a un año no genera el aviso",
      not liq_corto.history_warning, "aviso=%s" % bool(liq_corto.history_warning))

# ═══════════════════════════════════════════════════════════════════════════
# REG-08 — recalcular / borrador / confirmar sin duplicidad
# ═══════════════════════════════════════════════════════════════════════════
emp_dup = make_employee("Sin Duplicar", 55000, date(2020, 9, 1), date(2026, 7, 9))
seed_history(emp_dup, date(2026, 7, 9), 12, 55000)
liq_dup = Liq.create({
    "employee_id": emp_dup.id, "date_start": date(2020, 9, 1), "date_end": date(2026, 7, 9),
    "current_salary": 55000, "include_worked_days": True,
})
liq_dup.action_load_payroll_history()
liq_dup.action_compute()
primero = {l.concept: round(l.amount, 2) for l in liq_dup.line_ids}
n_lineas = len(liq_dup.line_ids)
liq_dup.action_compute()
igual = {l.concept: round(l.amount, 2) for l in liq_dup.line_ids} == primero
sin_crecer = len(liq_dup.line_ids) == n_lineas
liq_dup.action_draft()
liq_dup.action_compute()
antes_dup = env["hr.payslip"].search([("employee_id", "=", emp_dup.id)])
confirm(liq_dup)
creados = env["hr.payslip"].search([("employee_id", "=", emp_dup.id)]) - antes_dup
try:
    liq_dup._generate_payslips(liq_dup.payslip_run_id)
    segundo_rechazado = False
except Exception:
    segundo_rechazado = True
check("REG-08  recalcular sustituye líneas; borrador y confirmar dejan un solo recibo; "
      "un segundo intento se rechaza",
      igual and sin_crecer and len(creados) == 1 and segundo_rechazado,
      "líneas %d→%d, mismos montos=%s, recibos creados=%d, segundo intento rechazado=%s"
      % (n_lineas, len(liq_dup.line_ids), igual, len(creados), segundo_rechazado))

# ═══════════════════════════════════════════════════════════════════════════
# REG-09 / AC-B2-10 — confirmación conjunta
# ═══════════════════════════════════════════════════════════════════════════
lote = Liq
for wage in (40000, 50000, 60000):
    e = make_employee("Lote %s" % wage, wage, date(2022, 1, 1), date(2026, 9, 30))
    l = Liq.create({
        "employee_id": e.id, "date_start": date(2022, 1, 1), "date_end": date(2026, 9, 30),
    })
    fill_grid(l, wage)
    l.action_compute()
    lote |= l
esperado_total = sum(lote.mapped("amount_total"))
run_lote = confirm(lote)
recibos = env["hr.payslip"].search([("payslip_run_id", "=", run_lote.id)])
check("REG-09 / AC-B2-10  tres liquidaciones → un lote, un recibo por empleado, total consistente",
      len(lote.mapped("payslip_run_id")) == 1 and len(recibos) == 3
      and len(recibos.mapped("employee_id")) == 3
      and set(lote.mapped("state")) == {"done"}
      and abs(sum(lote.mapped("amount_total")) - esperado_total) < 0.01,
      "lotes=%d, recibos=%d, empleados=%d, total=%.2f"
      % (len(lote.mapped("payslip_run_id")), len(recibos),
         len(recibos.mapped("employee_id")), esperado_total))

# Cancelar libera al empleado y respeta el lote compartido
primera = lote[0]
run_compartido = primera.payslip_run_id
primera.action_cancel()
check("Controles  cancelar elimina el recibo, conserva el lote compartido y libera al empleado",
      primera.state == "cancelled" and not primera.payslip_id
      and run_compartido.exists()
      and env["hr.payslip"].search_count([("payslip_run_id", "=", run_compartido.id)]) == 2,
      "estado=%s, lote vive=%s, recibos restantes=%d"
      % (primera.state, bool(run_compartido.exists()),
         env["hr.payslip"].search_count([("payslip_run_id", "=", run_compartido.id)])))

# ═══════════════════════════════════════════════════════════════════════════
# Reporte
# ═══════════════════════════════════════════════════════════════════════════
print("===ACCEPTANCE_START===")
ok = sum(1 for _, passed, _ in RESULTS if passed)
for criterion, passed, detail in RESULTS:
    print("%s  %s" % ("PASS" if passed else "FAIL", criterion))
    if detail:
        print("        %s" % detail)
print("---")
print("%d/%d criterios PASS" % (ok, len(RESULTS)))
print("===ACCEPTANCE_END===")
env.cr.rollback()
