#!/usr/bin/env bash
# =====================================================================
# replicate_ir3_double_count.sh
# Replica de forma controlada el doble-conteo de Horas Nocturnas (HNI)
# en las casillas 3 (Sueldos) y 4 (Otras Remuneraciones) del IR-3.
#
# Clona una base de test que ya tiene el módulo instalado, inyecta un
# escenario conocido sobre un empleado (COM, HNI, INC, VAC), recomputa el
# IR-3 y muestra el desglose. Detecta el doble-conteo comparando el
# total_paid contra la suma sin duplicar HNI:
#   - código CON bug   -> diferencia == monto HNI
#   - código corregido -> diferencia == 0
#
# Uso:
#   ./replicate_ir3_double_count.sh
#   TEMPLATE_DB=otra_base ./replicate_ir3_double_count.sh
# =====================================================================
set -euo pipefail

ODOO_CONTAINER="${ODOO_CONTAINER:-lfernandez_v19}"
PG_CONTAINER="${PG_CONTAINER:-odoo-db}"
PG_USER="${PG_USER:-odoo}"
PG_PASS="${PG_PASS:-odoo_password}"
PG_HOST="${PG_HOST:-odoo-db}"
TEMPLATE_DB="${TEMPLATE_DB:-test_v19_l10n_do_hr_report_base}"
REPRO_DB="${REPRO_DB:-repro_ir3_double_count}"

echo ">> Clonando $TEMPLATE_DB -> $REPRO_DB"
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$TEMPLATE_DB','$REPRO_DB') AND pid<>pg_backend_pid();" >/dev/null 2>&1 || true
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c "DROP DATABASE IF EXISTS $REPRO_DB;" >/dev/null
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d postgres -c "CREATE DATABASE $REPRO_DB TEMPLATE $TEMPLATE_DB;" >/dev/null

PYSCRIPT="$(cat <<'PY'
report = env['dgii.reports'].search([('name', '=', '05/2026')], limit=1)
assert report, "no hay reporte DGII 05/2026 en la base template"
slip = env['hr.payslip'].search([('company_id', '=', report.company_id.id),
                                 ('state', 'in', ('validated', 'paid'))], limit=1)
assert slip, "no hay payslip validado en el periodo"
emp = slip.employee_id

def ref(x):
    return env.ref('l10n_do_hr_payroll.' + x)

inject = [('hr_rule_commissions', 50000.0),
          ('hr_rule_night_hours', 16156.0),
          ('hr_rule_incentives', 20000.0),
          ('hr_rule_vacations', 10000.0)]

slip.line_ids.filtered(lambda l: l.salary_rule_id in [ref(x) for x, _ in inject]).unlink()
for xmlid, amount in inject:
    r = ref(xmlid)
    env['hr.payslip.line'].create({
        'slip_id': slip.id, 'salary_rule_id': r.id, 'category_id': r.category_id.id,
        'name': r.name, 'code': r.code, 'amount': amount, 'quantity': 1.0,
        'rate': 100.0, 'total': amount})
env.cr.commit()

report._compute_l10n_do_ir3()
env.cr.commit()

line = report.l10n_do_ir3_line_ids.filtered(lambda l: l.employee_id == emp)
apagar = sum(slip.line_ids.filtered(lambda l: l.salary_rule_id == ref('hr_rule_base')).mapped('total'))
com = sum(slip.line_ids.filtered(lambda l: l.salary_rule_id == ref('hr_rule_commissions')).mapped('total'))
hni = sum(slip.line_ids.filtered(lambda l: l.salary_rule_id == ref('hr_rule_night_hours')).mapped('total'))
inc = sum(slip.line_ids.filtered(lambda l: l.salary_rule_id == ref('hr_rule_incentives')).mapped('total'))
vac = sum(slip.line_ids.filtered(lambda l: l.salary_rule_id == ref('hr_rule_vacations')).mapped('total'))

print("\n=== Empleado:", emp.name, "===")
print("APAGAR=%.2f  COM=%.2f  HNI=%.2f  INC=%.2f  VAC=%.2f" % (apagar, com, hni, inc, vac))
print("casilla 3 (salaries_paid)     =", line.salaries_paid)
print("casilla 4 (other_remuneration)=", line.other_remuneration)
print("total_paid                    =", line.total_paid)
sin_doble = (apagar + com + hni) + (inc + vac)
diff = line.total_paid - sin_doble
print("total sin doble-conteo        =", sin_doble)
print("DIFERENCIA por doble-conteo   =", round(diff, 2),
      "  (== HNI %.2f => BUG presente)" % hni if abs(diff) > 0.001 else "  (== 0 => corregido)")
PY
)"

echo ">> Inyectando escenario y recomputando IR-3"
echo "$PYSCRIPT" | docker exec -i "$ODOO_CONTAINER" odoo shell -d "$REPRO_DB" \
  --db_host="$PG_HOST" --db_port=5432 --db_user="$PG_USER" --db_password="$PG_PASS" \
  --no-http --logfile=/dev/null 2>&1 | grep -vE "^(INFO|WARNING|DEBUG|ERROR odoo)"
