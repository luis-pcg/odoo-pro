#!/bin/bash
# End to end scenarios. Every assertion reads the client database with psql,
# never the response of the sync itself.
#
# The scenarios mutate both databases, so the bench is rebuilt first. Pass
# --no-setup to replay them against the bench as it currently stands.
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ "${1:-}" == "--no-setup" ]] || "$HERE/setup.sh" >/dev/null
source "$HERE/lib.sh"
source "$HERE/creds.env"

PASS=0
FAIL=0
ok() { echo "  ok   $1"; PASS=$((PASS + 1)); }
ko() { echo "  FAIL $1"; echo "       $2"; FAIL=$((FAIL + 1)); }
check() { if [[ "$2" == "$3" ]]; then ok "$1"; else ko "$1" "expected [$2] got [$3]"; fi; }

sync() {
  put_args "$(printf '{"project_id": %s, "dry_run": %s}' "$PROJECT_ID" "${1:-false}")"
  RESULT="$(run_py "$MASTER_DB" sync_now.py | sed -n 's/^RESULT=//p' | tail -1)"
}
field() { python3 -c "import json,sys; print(json.loads(sys.argv[1])[sys.argv[2]])" "$RESULT" "$1"; }
master() { put_args "$1"; run_py "$MASTER_DB" edit_master.py >/dev/null; }
client() { put_args "$1"; run_py "$CLIENT_DB" edit_client.py >/dev/null; }
reset_errors() { put_args "$(printf '{"project_id": %s}' "$PROJECT_ID")"; run_py "$MASTER_DB" reset_errors.py >/dev/null; }
restart_client() { docker restart "$CLIENT_NAME" >/dev/null; wait_http "$CLIENT_URL" >/dev/null; }
param_value() { psql_q "$CLIENT_DB" "SELECT v.parameter_value FROM hr_rule_parameter_value v JOIN hr_rule_parameter p ON p.id = v.rule_parameter_id WHERE p.code = '$1' AND v.date_from = '$2'"; }

echo "== 1. A freshly installed client is already in sync =="
sync
check "state is success" "success" "$(field state)"
check "nothing is created" "0" "$(field created)"
check "nothing is written" "0" "$(field updated)"
check "everything matched" "42" "$(field unchanged)"
check "five RPC calls" "5" "$(field rpc_calls)"
check "no duplicate parameter appeared" "17" "$(psql_q "$CLIENT_DB" "SELECT count(*) FROM hr_rule_parameter")"

echo "== 2. A record missing on the client is created =="
client '{"action": "drop_risk_type", "name": "IV"}'
sync
check "one risk class created" "1" "$(field created)"
check "the client has the four classes back" "4" "$(psql_q "$CLIENT_DB" "SELECT count(*) FROM l10n_do_occupational_risk_type")"
check "with the legal rate" "0.30" "$(psql_q "$CLIENT_DB" "SELECT round(percentage::numeric, 2) FROM l10n_do_occupational_risk_type WHERE name = 'IV'")"

echo "== 3. A TSS cap raised on the master reaches the client =="
master '{"action": "set_parameter_value", "code": "SFS_TOPE", "date_from": "2026-02-01", "value": "240000.0"}'
sync
check "one value updated" "1" "$(field updated)"
check "the client holds the new cap" "240000.0" "$(param_value SFS_TOPE 2026-02-01)"

echo "== 4. A parameter typed by hand, with no external id, still travels =="
master '{"action": "new_parameter", "code": "REC_NOCT", "name": "Recargo nocturno", "date_from": "2026-01-01", "value": "1.15"}'
sync
check "the parameter and its value are created" "2" "$(field created)"
check "the client knows REC_NOCT" "1" "$(psql_q "$CLIENT_DB" "SELECT count(*) FROM hr_rule_parameter WHERE code = 'REC_NOCT'")"
check "its value hangs from the right parent" "1.15" "$(param_value REC_NOCT 2026-01-01)"

echo "== 5. The ISR scale, which needs base.group_system on the client =="
master '{"action": "edit_scale", "sequence": 2, "name": "Rentas desde RD$420,000.01 hasta RD$630,000.00", "top_amount": 630000.0}'
sync
check "one bracket updated" "1" "$(field updated)"
check "the bracket name was rewritten" "Rentas desde RD\$420,000.01 hasta RD\$630,000.00" "$(psql_q "$CLIENT_DB" "SELECT name FROM l10n_do_hr_retention_scale WHERE sequence = 2")"
check "and its ceiling too" "630000.00" "$(psql_q "$CLIENT_DB" "SELECT round(top_amount::numeric, 2) FROM l10n_do_hr_retention_scale WHERE sequence = 2")"

echo "== 6. A manual edit on the client is overwritten =="
client '{"action": "set_risk_percentage", "name": "I", "value": 9.99}'
sync
check "the master wins" "1" "$(field updated)"
check "the legal value is back" "0.10" "$(psql_q "$CLIENT_DB" "SELECT round(percentage::numeric, 2) FROM l10n_do_occupational_risk_type WHERE name = 'I'")"

echo "== 7. Rows the client owns are reported and left alone =="
client '{"action": "add_retro_value", "code": "SFS_RET", "date_from": "2003-01-01", "value": "3.04"}'
sync
check "nothing was written" "0" "$(field updated)"
check "the extra row is reported" "1" "$(field extras)"
check "the extra row survives" "1" "$(psql_q "$CLIENT_DB" "SELECT count(*) FROM hr_rule_parameter_value WHERE date_from = '2003-01-01'")"

echo "== 8. A record deleted on the master is kept on the client =="
master '{"action": "drop_risk_type", "name": "IV"}'
sync
check "the client still has four classes" "4" "$(psql_q "$CLIENT_DB" "SELECT count(*) FROM l10n_do_occupational_risk_type")"
check "both orphans are reported" "2" "$(field extras)"

echo "== 9. Missing permissions: partial state, the rest still goes through =="
reset_errors
client '{"action": "revoke_group", "group": "l10n_do_hr_payroll.group_hr_payroll_manager_conf"}'
restart_client
master '{"action": "set_parameter_value", "code": "SFS_TOPE", "date_from": "2026-02-01", "value": "250000.0"}'
client '{"action": "set_risk_percentage", "name": "II", "value": 8.88}'
sync
check "the client is only partially synchronized" "partial" "$(field state)"
check "the risk class could not be written" "1" "$(field errors)"
check "rule parameters went through anyway" "250000.0" "$(param_value SFS_TOPE 2026-02-01)"
check "the error counter moved" "1" "$(field db_errors)"
client '{"action": "grant_group", "group": "l10n_do_hr_payroll.group_hr_payroll_manager_conf"}'
restart_client
sync
check "the counter clears once fixed" "0" "$(field db_errors)"

echo "== 10. A simulation reports without writing =="
master '{"action": "set_parameter_value", "code": "AFP_TOPE", "date_from": "2026-02-01", "value": "999999.0"}'
sync true
check "the diff is reported" "1" "$(field updated)"
check "the client was not touched" "464460.0" "$(param_value AFP_TOPE 2026-02-01)"
sync
check "the real run then applies it" "999999.0" "$(param_value AFP_TOPE 2026-02-01)"

echo "== 11. An unreachable client fails alone, then recovers =="
reset_errors
docker rm -f "$CLIENT_NAME" >/dev/null
sync
check "the run reports an error" "error" "$(field state)"
check "the error counter moved" "1" "$(field db_errors)"
start_server "$CLIENT_NAME" "$CLIENT_DB" "$CLIENT_PORT"
wait_http "$CLIENT_URL" >/dev/null
sync
check "the next night recovers" "success" "$(field state)"
check "the counter is cleared" "0" "$(field db_errors)"

echo "== 12. A new ISR bracket needs base.group_system to be created =="
# The bracket that never travelled: hr_payroll.group_hr_payroll_manager can
# read and write the scale but not create it, so the corrections of the
# existing brackets land and a brand new one is refused.
reset_errors
CLIENT_KEY_RESTRICTED="$(put_args '{"action": "restricted_api_user"}'; run_py "$CLIENT_DB" edit_client.py | sed -n 's/^KEY=//p' | tail -1)"
master "$(printf '{"action": "set_api_user", "project_id": %s, "login": "sync_api", "key": "%s"}' \
  "$PROJECT_ID" "$CLIENT_KEY_RESTRICTED")"
master '{"action": "new_scale", "sequence": 9, "name": "Rentas desde RD$1,000,000.01 en adelante"}'
sync
check "the client is only partially synchronized" "partial" "$(field state)"
check "the bracket was refused" "1" "$(field errors)"
check "the client never got it" "" "$(psql_q "$CLIENT_DB" "SELECT name FROM l10n_do_hr_retention_scale WHERE sequence = 9")"
MESSAGE="$(psql_q "$MASTER_DB" "SELECT message FROM l10n_do_payroll_sync_log ORDER BY id DESC LIMIT 1")"
if [[ "$MESSAGE" == *"not allowed to create"* ]]; then ok "the log says what the client refused"
else ko "the log says what the client refused" "message was [$MESSAGE]"; fi
if [[ "$MESSAGE" == *"base.group_system"* ]]; then ok "and which group would fix it"
else ko "and which group would fix it" "message was [$MESSAGE]"; fi
NOTE="$(psql_q "$MASTER_DB" "SELECT count(*) FROM mail_message WHERE model = 'project.project' AND res_id = $PROJECT_ID")"
if [[ "${NOTE:-0}" -ge 1 ]]; then ok "the client database chatter carries the failure"
else ko "the client database chatter carries the failure" "no message logged"; fi

echo "== 13. The same bracket travels once the group is granted =="
reset_errors
master "$(printf '{"action": "set_api_user", "project_id": %s, "login": "admin", "key": "%s"}' \
  "$PROJECT_ID" "$CLIENT_KEY")"
sync
check "the bracket is created" "1" "$(field created)"
check "the client holds it" "Rentas desde RD\$1,000,000.01 en adelante" \
  "$(psql_q "$CLIENT_DB" "SELECT name FROM l10n_do_hr_retention_scale WHERE sequence = 9")"
master '{"action": "drop_scale", "sequence": 9}'

echo
echo "$PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]]
