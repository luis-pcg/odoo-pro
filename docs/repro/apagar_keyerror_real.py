# -*- coding: utf-8 -*-
# Reproducción del KeyError: 'REAL' en la regla APAGAR (Salario a Pagar).
#
# Uso (dentro del contenedor Odoo / Odoo.sh shell):
#   odoo shell -d <DB> --no-http < docs/repro/apagar_keyerror_real.py
#
# En Odoo.sh:  Branch > Shell  ->  odoo-bin shell -d $PGDATABASE  luego pegar.
#
# Qué hace: toma el CÓDIGO REAL de la regla APAGAR tal como está en la base
# (campo amount_python_compute) y lo ejecuta contra un escenario donde SOLO
# viene el input DLAB (Días Laborados) y NO viene REAL (Salario Real).
# Ese es el escenario exacto que dispara el error en producción.
#
# No crea nóminas ni toca datos: solo evalúa el texto de la regla en un
# localdict controlado. Read-only.

rule = env.ref("l10n_do_hr_payroll.hr_rule_base")  # code = APAGAR
code = rule.amount_python_compute
print("=" * 70)
print("Regla:", rule.name, "(%s)" % rule.code)
print("-" * 70)
print(code)
print("=" * 70)

# Escenario que rompe: DLAB presente (>1 día), REAL ausente.
inputs = {"DLAB": {"amount": 10.0}}


class _Contract:
    wage = 30000.0
    l10n_do_payment_division = 2.0


BASE = 30000.0  # resultado de la regla BASE (= contract.wage)
localdict = {
    "contract": _Contract(),
    "inputs": inputs,
    "BASE": BASE,
    "result": 0.0,
}

try:
    exec(code, {}, localdict)
    print("SIN ERROR  ->  result =", round(localdict["result"], 2))
    print("La regla desplegada YA está corregida.")
except KeyError as e:
    print("REPRODUCIDO  ->  KeyError:", e)
    print("La regla desplegada tiene el bug (linea del elif usa inputs['REAL']).")
