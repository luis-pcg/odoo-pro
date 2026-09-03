#!/bin/bash
# Regression guard: installing the sync module must not disturb payroll, and
# the known upgrade hazards must stay exactly as documented.
#
# Uses its own throwaway database so nothing else is disturbed.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

REG_DB="sync_regression"
DEPENDENTS="l10n_do_hr_payroll_news,l10n_do_hr_report_base,l10n_do_payroll_file_base,l10n_do_hr_payroll_import_inputs,l10n_do_hr_payroll_liquidation"

PASS=0
FAIL=0
FAILED_NAMES=()
ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
ko()   { FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); printf '  \033[31mFAIL\033[0m  %s\n     %s\n' "$1" "$2"; }
head2(){ printf '\n\033[1m%s\033[0m\n' "$1"; }
assert_eq() { if [[ "$2" == "$3" ]]; then ok "$1"; else ko "$1" "expected '$2', got '$3'"; fi; }
assert_ne() { if [[ "$2" != "$3" ]]; then ok "$1"; else ko "$1" "expected something other than '$2'"; fi; }

# Odoo logs a real problem as "<LEVEL> <db> <logger>"; the docutils manifest
# noise and the addons_path warning are not failures.
odoo_errors() { grep -E "(CRITICAL|ERROR) $REG_DB|Traceback \(most recent" || true; }

payroll_fingerprint() {
  psql_q "$REG_DB" "SELECT md5(string_agg(p.code || ':' || v.date_from || ':' || v.parameter_value, ',' ORDER BY p.code, v.date_from))
    FROM hr_rule_parameter_value v JOIN hr_rule_parameter p ON p.id = v.rule_parameter_id"
}

echo "=============================================="
echo " Payroll sync — regression guard ($REG_DB)"
echo "=============================================="

head2 "1. Baseline: payroll installs on its own"
drop_db "$REG_DB"
OUT="$(odoo_cli "$REG_DB" --without-demo=all --log-level=warn --stop-after-init --no-http \
  -i l10n_do_hr_payroll 2>&1 | odoo_errors)"
assert_eq "l10n_do_hr_payroll installs clean" "" "$OUT"
assert_eq "the four DGII scales are loaded" "4" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_retention_scale")"
assert_eq "the three payment divisions are loaded" "3" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_payroll_payment_division")"
PARAMS_BEFORE="$(payroll_fingerprint)"

head2 "2. ISR computation before the sync module exists"
odoo_shell "$REG_DB" < "$HERE/py/compute_isr_probe.py" > /tmp/_isr_before.txt 2>/dev/null
ISR_BEFORE="$(grep '^ISR=' /tmp/_isr_before.txt | cut -d= -f2- || true)"
assert_ne "the probe produced ISR figures" "" "$ISR_BEFORE"
echo "     $ISR_BEFORE"

head2 "3. Installing the sync module does not disturb payroll"
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http \
  -i l10n_do_hr_payroll_sync 2>&1 | odoo_errors)"
assert_eq "l10n_do_hr_payroll_sync installs clean" "" "$OUT"
odoo_shell "$REG_DB" < "$HERE/py/compute_isr_probe.py" > /tmp/_isr_after.txt 2>/dev/null
ISR_AFTER="$(grep '^ISR=' /tmp/_isr_after.txt | cut -d= -f2- || true)"
assert_eq "ISR is bit-for-bit identical" "$ISR_BEFORE" "$ISR_AFTER"
assert_eq "no payroll parameter was touched" "$PARAMS_BEFORE" "$(payroll_fingerprint)"
assert_eq "five models are registered" "5" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_model")"
assert_eq "four of them are active" "4" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_model WHERE active")"
assert_eq "installing writes to no client" "0" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_run")"
assert_eq "no database is enabled by default" "0" "$(psql_q "$REG_DB" "SELECT count(*) FROM project_project WHERE l10n_do_payroll_sync_enabled")"

head2 "4. Every direct dependent still installs"
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http \
  -i "$DEPENDENTS" 2>&1 | odoo_errors)"
assert_eq "all dependents install alongside the sync module" "" "$OUT"
for module in ${DEPENDENTS//,/ }; do
  assert_eq "  $module is installed" "installed" "$(psql_q "$REG_DB" "SELECT state FROM ir_module_module WHERE name = '$module'")"
done

head2 "5. ISR still identical with the whole dependency tree installed"
odoo_shell "$REG_DB" < "$HERE/py/compute_isr_probe.py" > /tmp/_isr_full.txt 2>/dev/null
ISR_FULL="$(grep '^ISR=' /tmp/_isr_full.txt | cut -d= -f2- || true)"
assert_eq "ISR unchanged with every dependent installed" "$ISR_BEFORE" "$ISR_FULL"

head2 "6. A full payslip run still computes"
odoo_shell "$REG_DB" < "$ROOT_DIR/tools/manual-generator/configs/l10n_do_hr_payroll.seed.py" \
  > /tmp/_seed.txt 2>&1 || true
if grep -q "SEED OK" /tmp/_seed.txt; then
  ok "the four-employee payslip scenario computes end to end"
  grep -E "^   " /tmp/_seed.txt | head -6 | sed 's/^/     /'
else
  ko "the four-employee payslip scenario computes end to end" \
     "$(grep -E 'SEED FAIL|Error|Traceback' /tmp/_seed.txt | head -3)"
fi

head2 "7. Known hazard: upgrading payroll rewrites its own seeds"
# Documented risk: data/hr_rule_parameter.xml and the payment divisions carry no
# noupdate, so `-u l10n_do_hr_payroll` on a client puts the seeded values back.
# The nightly sync corrects it within 24h and the log shows it. Pinned here so
# that the day someone adds noupdate, this guard is the one that tells us.
psql_q "$REG_DB" "UPDATE l10n_do_hr_payroll_payment_division SET payment_division = 9.9 WHERE name = 'monthly'" >/dev/null
psql_q "$REG_DB" "UPDATE hr_rule_parameter_value SET parameter_value = '111111.0'
  WHERE id IN (SELECT v.id FROM hr_rule_parameter_value v JOIN hr_rule_parameter p ON p.id = v.rule_parameter_id
               WHERE p.code = 'SFS_TOPE' AND v.date_from = '2026-02-01')" >/dev/null
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http -u l10n_do_hr_payroll 2>&1 | odoo_errors)"
assert_eq "the upgrade runs without errors" "" "$OUT"
assert_eq "a locally tuned divisor is reverted by the upgrade" "1.0" \
  "$(psql_q "$REG_DB" "SELECT round(payment_division::numeric, 1) FROM l10n_do_hr_payroll_payment_division WHERE name = 'monthly' ORDER BY company_id LIMIT 1")"
assert_eq "a locally tuned TSS cap is reverted too" "232230.0" \
  "$(psql_q "$REG_DB" "SELECT v.parameter_value FROM hr_rule_parameter_value v JOIN hr_rule_parameter p ON p.id = v.rule_parameter_id WHERE p.code = 'SFS_TOPE' AND v.date_from = '2026-02-01'")"
assert_eq "no duplicate scale was created" "4" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_retention_scale")"
assert_eq "no duplicate division was created" "3" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_payroll_payment_division")"

head2 "8. The sync module upgrades cleanly and idempotently"
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http -u l10n_do_hr_payroll_sync 2>&1 | odoo_errors)"
assert_eq "re-upgrading the sync module is clean" "" "$OUT"
assert_eq "the registry was not duplicated" "5" "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_model")"
assert_eq "payment divisions stay opt-in after an upgrade" "0" \
  "$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_model WHERE model_name = 'l10n.do.hr.payroll.payment.division' AND active")"

head2 "Summary"
printf '  %s passed, %s failed\n' "$PASS" "$FAIL"
if (( FAIL > 0 )); then
  printf '  failed: %s\n' "${FAILED_NAMES[*]}"
  exit 1
fi
echo "  (database $REG_DB kept for inspection; drop it with: tools/sync-e2e/teardown.sh --drop-db)"
exit 0
