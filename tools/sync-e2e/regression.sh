#!/bin/bash
# Regression guard for the payroll parameter sync work.
#
# Answers three questions:
#   1. Does l10n_do_hr_payroll still upgrade cleanly, and does the new
#      19.0.1.0.9 migration actually flip the payment-division noupdate flags?
#   2. Do all direct dependents of l10n_do_hr_payroll still install alongside
#      the new sync module?
#   3. Does payroll still compute the same ISR once the sync module is present?
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

# Odoo logs a real problem as "<LEVEL> <db> <logger>"; docutils' "(ERROR/3)"
# manifest-rendering noise and the addons_path warning are not failures.
odoo_errors() { grep -E "(CRITICAL|ERROR) $REG_DB|Traceback \(most recent" || true; }

echo "=============================================="
echo " Payroll sync — regression guard ($REG_DB)"
echo "=============================================="

# ---------------------------------------------------------------------------
head2 "1. Baseline: payroll installs on its own"
# ---------------------------------------------------------------------------
drop_db "$REG_DB"
OUT="$(odoo_cli "$REG_DB" --without-demo=all --log-level=warn --stop-after-init --no-http \
  -i l10n_do_hr_payroll 2>&1 | odoo_errors)"
assert_eq "l10n_do_hr_payroll installs clean" "" "$OUT"

BASE_SCALES="$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_retention_scale")"
assert_eq "the four DGII scales are loaded" "4" "$BASE_SCALES"

# ---------------------------------------------------------------------------
head2 "2. The 19.0.1.0.9 migration flips the payment-division noupdate flags"
# ---------------------------------------------------------------------------
# Recreate the pre-change state: flags off, module pinned to the old version.
psql_q "$REG_DB" "UPDATE ir_model_data SET noupdate = false
  WHERE module = 'l10n_do_hr_payroll'
    AND model = 'l10n.do.hr.payroll.payment.division'" >/dev/null
psql_q "$REG_DB" "UPDATE ir_module_module SET latest_version = '19.0.1.0.8'
  WHERE name = 'l10n_do_hr_payroll'" >/dev/null
BEFORE="$(psql_q "$REG_DB" "SELECT count(*) FROM ir_model_data
  WHERE module = 'l10n_do_hr_payroll'
    AND model = 'l10n.do.hr.payroll.payment.division' AND noupdate IS NOT true")"
assert_ne "pre-migration state has unprotected rows" "0" "$BEFORE"

# A locally tuned value must survive the upgrade; that is the whole point.
psql_q "$REG_DB" "UPDATE l10n_do_hr_payroll_payment_division SET payment_division = 9.9
  WHERE name = 'monthly'" >/dev/null

OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http \
  -u l10n_do_hr_payroll 2>&1 | odoo_errors)"
assert_eq "the upgrade runs without errors" "" "$OUT"

AFTER="$(psql_q "$REG_DB" "SELECT count(*) FROM ir_model_data
  WHERE module = 'l10n_do_hr_payroll'
    AND model = 'l10n.do.hr.payroll.payment.division' AND noupdate IS NOT true")"
assert_eq "every payment-division xmlid is now noupdate" "0" "$AFTER"

KEPT="$(psql_q "$REG_DB" "SELECT round(payment_division::numeric, 1)
  FROM l10n_do_hr_payroll_payment_division WHERE name = 'monthly' ORDER BY company_id LIMIT 1")"
assert_eq "a locally tuned value survived the upgrade" "9.9" "$KEPT"

# Put it back so the payroll computation below uses the real divisor.
psql_q "$REG_DB" "UPDATE l10n_do_hr_payroll_payment_division SET payment_division = 1
  WHERE name = 'monthly'" >/dev/null

# ---------------------------------------------------------------------------
head2 "3. ISR computation before the sync module is installed"
# ---------------------------------------------------------------------------
odoo_shell "$REG_DB" < "$HERE/py/compute_isr_probe.py" > /tmp/_isr_before.txt 2>/dev/null
ISR_BEFORE="$(grep '^ISR=' /tmp/_isr_before.txt | cut -d= -f2- || true)"
assert_ne "the probe produced ISR figures" "" "$ISR_BEFORE"
echo "     $ISR_BEFORE"

# ---------------------------------------------------------------------------
head2 "4. Installing the sync module does not disturb payroll"
# ---------------------------------------------------------------------------
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http \
  -i l10n_do_hr_payroll_sync 2>&1 | odoo_errors)"
assert_eq "l10n_do_hr_payroll_sync installs clean" "" "$OUT"

odoo_shell "$REG_DB" < "$HERE/py/compute_isr_probe.py" > /tmp/_isr_after.txt 2>/dev/null
ISR_AFTER="$(grep '^ISR=' /tmp/_isr_after.txt | cut -d= -f2- || true)"
assert_eq "ISR is bit-for-bit identical after installing the sync module" "$ISR_BEFORE" "$ISR_AFTER"

# With no role configured the triggers must stay completely inert.
ROLE="$(psql_q "$REG_DB" "SELECT coalesce((SELECT value FROM ir_config_parameter
  WHERE key = 'l10n_do_payroll_sync.role'), 'none')")"
assert_eq "the default role is inert" "none" "$ROLE"
EVENTS="$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_event")"
assert_eq "no events were queued by the install" "0" "$EVENTS"

# Editing a parameter with no role must not queue anything either.
odoo_shell "$REG_DB" < "$HERE/py/touch_scale.py" >/dev/null 2>&1
EVENTS="$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_payroll_sync_event")"
assert_eq "editing a parameter queues nothing when the role is none" "0" "$EVENTS"

# ---------------------------------------------------------------------------
head2 "5. Every direct dependent still installs"
# ---------------------------------------------------------------------------
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http \
  -i "$DEPENDENTS" 2>&1 | odoo_errors)"
assert_eq "all dependents install alongside the sync module" "" "$OUT"

for module in ${DEPENDENTS//,/ }; do
  STATE="$(psql_q "$REG_DB" "SELECT state FROM ir_module_module WHERE name = '$module'")"
  assert_eq "  $module is installed" "installed" "$STATE"
done

# ---------------------------------------------------------------------------
head2 "6. ISR still identical with the whole dependency tree installed"
# ---------------------------------------------------------------------------
odoo_shell "$REG_DB" < "$HERE/py/compute_isr_probe.py" > /tmp/_isr_full.txt 2>/dev/null
ISR_FULL="$(grep '^ISR=' /tmp/_isr_full.txt | cut -d= -f2- || true)"
assert_eq "ISR unchanged with every dependent installed" "$ISR_BEFORE" "$ISR_FULL"

# ---------------------------------------------------------------------------
head2 "7. A full payslip run still computes"
# ---------------------------------------------------------------------------
odoo_shell "$REG_DB" < "$ROOT_DIR/tools/manual-generator/configs/l10n_do_hr_payroll.seed.py" \
  > /tmp/_seed.txt 2>&1 || true
if grep -q "SEED OK" /tmp/_seed.txt; then
  ok "the four-employee payslip scenario computes end to end"
  grep -E "^   " /tmp/_seed.txt | head -6 | sed 's/^/     /'
else
  ko "the four-employee payslip scenario computes end to end" \
     "$(grep -E 'SEED FAIL|Error|Traceback' /tmp/_seed.txt | head -3)"
fi

# ---------------------------------------------------------------------------
head2 "8. Payroll's own upgrade is still idempotent"
# ---------------------------------------------------------------------------
OUT="$(odoo_cli "$REG_DB" --log-level=warn --stop-after-init --no-http \
  -u l10n_do_hr_payroll 2>&1 | odoo_errors)"
assert_eq "re-upgrading payroll is clean" "" "$OUT"
SCALES="$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_retention_scale")"
assert_eq "no duplicate scales were created" "4" "$SCALES"
DIVISIONS="$(psql_q "$REG_DB" "SELECT count(*) FROM l10n_do_hr_payroll_payment_division")"
assert_eq "no duplicate payment divisions were created" "3" "$DIVISIONS"

# ---------------------------------------------------------------------------
head2 "Summary"
# ---------------------------------------------------------------------------
printf '  %s passed, %s failed\n' "$PASS" "$FAIL"
if (( FAIL > 0 )); then
  printf '  failed: %s\n' "${FAILED_NAMES[*]}"
  exit 1
fi
echo "  (database $REG_DB kept for inspection; drop it with tools/sync-e2e/teardown.sh --drop-db)"
exit 0
