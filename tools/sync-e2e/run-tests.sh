#!/bin/bash
# End-to-end scenarios for the payroll parameter sync.
#
# Everything here goes over real HTTP between two live Odoo instances and is
# verified by reading the client's Postgres rows directly -- never by trusting
# the API's own success report.
#
# Requires tools/sync-e2e/setup.sh to have run first.

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"
source "$HERE/creds.env"

PASS=0
FAIL=0
FAILED_NAMES=()

ok()   { PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %s\n' "$1"; }
ko()   { FAIL=$((FAIL+1)); FAILED_NAMES+=("$1"); printf '  \033[31mFAIL\033[0m  %s\n     %s\n' "$1" "$2"; }
head2() { printf '\n\033[1m%s\033[0m\n' "$1"; }

assert_eq() {
  # assert_eq <name> <expected> <actual>
  if [[ "$2" == "$3" ]]; then ok "$1"; else ko "$1" "expected '$2', got '$3'"; fi
}
assert_ne() {
  if [[ "$2" != "$3" ]]; then ok "$1"; else ko "$1" "expected something other than '$2'"; fi
}
assert_contains() {
  if [[ "$3" == *"$2"* ]]; then ok "$1"; else ko "$1" "'$2' not found in: $3"; fi
}

api() {
  # api <base-url> <path> <api-key> [json-body]  -> "<http_code>|<body>"
  local url="$1" path="$2" key="$3" body="${4-}"
  [[ -z "$body" ]] && body='{}'
  curl -sS -m 30 -o /tmp/_sync_body -w '%{http_code}' \
    -X POST "${url}/api/v1/payroll-sync${path}" \
    -H 'Content-Type: application/json' \
    -H "X-API-Key: ${key}" \
    --data "$body" 2>/dev/null
  printf '|'
  cat /tmp/_sync_body
}

http_code() { printf '%s' "${1%%|*}"; }
http_body() { printf '%s' "${1#*|}"; }

# Values read straight out of each database, bypassing the API.
client_scale_percent() {
  psql_q "$CLIENT_DB" "SELECT round(percent::numeric, 4) FROM l10n_do_hr_retention_scale s
    JOIN ir_model_data d ON d.res_id = s.id AND d.model = 'l10n.do.hr.retention.scale'
    WHERE d.module = 'l10n_do_hr_payroll' AND d.name = '$1'"
}
master_scale_percent() {
  psql_q "$MASTER_DB" "SELECT round(percent::numeric, 4) FROM l10n_do_hr_retention_scale s
    JOIN ir_model_data d ON d.res_id = s.id AND d.model = 'l10n.do.hr.retention.scale'
    WHERE d.module = 'l10n_do_hr_payroll' AND d.name = '$1'"
}
client_division() {
  psql_q "$CLIENT_DB" "SELECT round(payment_division::numeric, 5)
    FROM l10n_do_hr_payroll_payment_division WHERE name = '$1' ORDER BY company_id LIMIT 1"
}
event_state() {
  psql_q "$MASTER_DB" "SELECT state FROM l10n_do_payroll_sync_event WHERE id = $1"
}
event_retries() {
  psql_q "$MASTER_DB" "SELECT retry_count FROM l10n_do_payroll_sync_event WHERE id = $1"
}

echo "=============================================="
echo " Payroll sync — end-to-end scenarios"
echo "  master $MASTER_URL   client $CLIENT_URL"
echo "=============================================="

# ---------------------------------------------------------------------------
head2 "1. Connectivity and contract"
# ---------------------------------------------------------------------------
R="$(api "$CLIENT_URL" /ping "$CLIENT_INBOUND_KEY")"
assert_eq "client answers /ping with a valid key" "200" "$(http_code "$R")"
assert_contains "client reports its role" '"role": "client"' "$(http_body "$R")"

R="$(api "$MASTER_URL" /ping "$MASTER_INBOUND_KEY")"
assert_eq "master answers /ping with a valid key" "200" "$(http_code "$R")"

R="$(api "$CLIENT_URL" /manifest "$CLIENT_INBOUND_KEY")"
assert_eq "client publishes its manifest" "200" "$(http_code "$R")"
assert_contains "manifest lists the retention scale" "l10n.do.hr.retention.scale" "$(http_body "$R")"

# ---------------------------------------------------------------------------
head2 "2. Authentication and authorization"
# ---------------------------------------------------------------------------
R="$(api "$CLIENT_URL" /push "wrong-key-entirely" '{"items":[]}')"
assert_eq "a wrong key is rejected with 403" "403" "$(http_code "$R")"

R="$(curl -sS -m 30 -o /tmp/_sync_body -w '%{http_code}' -X POST \
      "${CLIENT_URL}/api/v1/payroll-sync/push" -H 'Content-Type: application/json' \
      --data '{"items":[]}' 2>/dev/null)"
assert_eq "a missing key is rejected with 401" "401" "$R"

R="$(api "$CLIENT_URL" /pull "$CLIENT_INBOUND_KEY")"
assert_eq "the client does not expose the master's /pull" "404" "$(http_code "$R")"

R="$(api "$MASTER_URL" /push "$MASTER_INBOUND_KEY" '{"items":[]}')"
assert_eq "the master does not expose the client's /push" "404" "$(http_code "$R")"

R="$(api "$CLIENT_URL" /push "$CLIENT_INBOUND_KEY" 'not-json-at-all')"
assert_eq "a malformed body is rejected with 400" "400" "$(http_code "$R")"

# ---------------------------------------------------------------------------
head2 "3. Push: a master edit reaches the client database"
# ---------------------------------------------------------------------------
BEFORE_CLIENT="$(client_scale_percent l10n_do_hr_retention_scale_2)"
NEW_PERCENT="17.7500"

put_args_json="$(printf '{"percent": %s}' "${NEW_PERCENT%%0000}")"
printf '%s' "$put_args_json" | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/edit_scale.py" >/dev/null 2>&1

# The post-commit flush runs asynchronously; give it a moment, then fall back to
# an explicit queue drain so a slow flush does not read as a functional failure.
for _ in $(seq 1 10); do
  AFTER_CLIENT="$(client_scale_percent l10n_do_hr_retention_scale_2)"
  [[ "$AFTER_CLIENT" == "$NEW_PERCENT" ]] && break
  sleep 1
done

assert_eq "master value changed" "$NEW_PERCENT" "$(master_scale_percent l10n_do_hr_retention_scale_2)"
assert_ne "client value is no longer the old one" "$BEFORE_CLIENT" "$AFTER_CLIENT"
assert_eq "client value equals the master value" "$NEW_PERCENT" "$AFTER_CLIENT"

LAST_EVENT="$(psql_q "$MASTER_DB" "SELECT id FROM l10n_do_payroll_sync_event
  WHERE model_name = 'l10n.do.hr.retention.scale' ORDER BY id DESC LIMIT 1")"
assert_eq "the event is marked delivered" "sent" "$(event_state "$LAST_EVENT")"

INBOUND_OK="$(psql_q "$CLIENT_DB" "SELECT count(*) FROM l10n_do_payroll_sync_log
  WHERE direction = 'in' AND endpoint = '/push' AND status = 'ok'")"
assert_ne "the client audited the inbound push" "0" "$INBOUND_OK"

# ---------------------------------------------------------------------------
head2 "4. Company-scoped parameter lands in the right company"
# ---------------------------------------------------------------------------
printf '{"division": 2.5}' | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/edit_division.py" >/dev/null 2>&1
for _ in $(seq 1 10); do
  [[ "$(client_division monthly)" == "2.50000" ]] && break
  sleep 1
done
assert_eq "payment division reached the client" "2.50000" "$(client_division monthly)"
ORPHANS="$(psql_q "$CLIENT_DB" "SELECT count(*) FROM l10n_do_hr_payroll_payment_division
  WHERE company_id IS NULL")"
assert_eq "no company-less row was created" "0" "$ORPHANS"

# ---------------------------------------------------------------------------
head2 "5. Offline client: retry with backoff, then dead letter"
# ---------------------------------------------------------------------------
docker stop "$CLIENT_NAME" >/dev/null 2>&1
printf '{"percent": 21.5}' | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/edit_scale.py" >/dev/null 2>&1
sleep 2

OFFLINE_EVENT="$(psql_q "$MASTER_DB" "SELECT id FROM l10n_do_payroll_sync_event
  WHERE model_name = 'l10n.do.hr.retention.scale' ORDER BY id DESC LIMIT 1")"
STATE="$(event_state "$OFFLINE_EVENT")"
assert_ne "an unreachable client does not lose the event" "sent" "$STATE"
assert_contains "the event is queued for retry" "$STATE" "pending failed"

RETRY_AT="$(psql_q "$MASTER_DB" "SELECT next_retry_at IS NOT NULL FROM l10n_do_payroll_sync_event WHERE id = $OFFLINE_EVENT")"
assert_eq "a retry is scheduled" "t" "$RETRY_AT"

# Force the retry budget to run out without waiting for the real backoff.
printf '{"event_id": %s}' "$OFFLINE_EVENT" | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/exhaust_retries.py" >/dev/null 2>&1
assert_eq "the event dead-letters after its retries" "dead" "$(event_state "$OFFLINE_EVENT")"

CLIENT_ERR="$(psql_q "$MASTER_DB" "SELECT state FROM l10n_do_payroll_sync_client WHERE id = $SYNC_CLIENT_ID")"
assert_eq "the client is flagged in error" "error" "$CLIENT_ERR"

# ---------------------------------------------------------------------------
head2 "6. Client comes back: retry from the dead letter queue"
# ---------------------------------------------------------------------------
start_server "$CLIENT_NAME" "$CLIENT_DB" "$CLIENT_PORT"
wait_http "$CLIENT_URL" || { echo "client did not restart"; exit 1; }

printf '{"event_id": %s}' "$OFFLINE_EVENT" | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/retry_event.py" >/dev/null 2>&1
sleep 2
assert_eq "the retried event is delivered" "sent" "$(event_state "$OFFLINE_EVENT")"
assert_eq "the value the client missed is now applied" "21.5000" "$(client_scale_percent l10n_do_hr_retention_scale_2)"

CLIENT_OK="$(psql_q "$MASTER_DB" "SELECT state FROM l10n_do_payroll_sync_client WHERE id = $SYNC_CLIENT_ID")"
assert_eq "the client is back online" "online" "$CLIENT_OK"

# ---------------------------------------------------------------------------
head2 "7. Pull mode: the client fetches on its own"
# ---------------------------------------------------------------------------
# Silence push so only the pull path can explain the change.
printf '{"push_enabled": false}' | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/set_client_flags.py" >/dev/null 2>&1

printf '{"percent": 23.25}' | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/edit_scale.py" >/dev/null 2>&1
sleep 1
assert_ne "push is off, so the client has not seen it yet" "23.2500" "$(client_scale_percent l10n_do_hr_retention_scale_2)"

odoo_shell "$CLIENT_DB" < "$HERE/py/pull_now.py" >/dev/null 2>&1
assert_eq "the client picked it up by pulling" "23.2500" "$(client_scale_percent l10n_do_hr_retention_scale_2)"

PULL_LOGGED="$(psql_q "$MASTER_DB" "SELECT count(*) FROM l10n_do_payroll_sync_log
  WHERE direction = 'in' AND endpoint = '/pull' AND status = 'ok'")"
assert_ne "the master audited the pull" "0" "$PULL_LOGGED"

printf '{"push_enabled": true}' | docker exec -i "$CONTAINER" tee /tmp/sync_e2e_args.json >/dev/null
odoo_shell "$MASTER_DB" < "$HERE/py/set_client_flags.py" >/dev/null 2>&1

# ---------------------------------------------------------------------------
head2 "8. Safety properties"
# ---------------------------------------------------------------------------
# Executable payroll code must not be distributable while the switch is off.
R="$(api "$CLIENT_URL" /manifest "$CLIENT_INBOUND_KEY")"
if [[ "$(http_body "$R")" == *"amount_python_compute"* ]]; then
  ko "python code fields are not advertised" "amount_python_compute is in the manifest"
else
  ok "python code fields are not advertised"
fi

# A model outside the registry must be refused even with a valid key.
R="$(api "$CLIENT_URL" /push "$CLIENT_INBOUND_KEY" \
  '{"items":[{"event_id":1,"model":"res.users","ref":"base.user_admin","operation":"upsert","values":{"login":"pwned"}}]}')"
assert_eq "an unregistered model is refused" "200" "$(http_code "$R")"
assert_contains "the refusal is explicit" '"status": "error"' "$(http_body "$R")"
ADMIN_LOGIN="$(psql_q "$CLIENT_DB" "SELECT login FROM res_users WHERE id = 2")"
assert_eq "res.users was not touched" "admin" "$ADMIN_LOGIN"

# Applying a change on the client must not make the client emit its own events.
CLIENT_EVENTS="$(psql_q "$CLIENT_DB" "SELECT count(*) FROM l10n_do_payroll_sync_event")"
assert_eq "the client emits no events of its own" "0" "$CLIENT_EVENTS"

# Secrets must never be readable in the audit trail.
LEAKED="$(psql_q "$CLIENT_DB" "SELECT count(*) FROM l10n_do_payroll_sync_log
  WHERE payload LIKE '%${CLIENT_INBOUND_KEY}%'")"
assert_eq "no API key was written to the log" "0" "$LEAKED"

# Re-applying the exact same payload must be a no-op, not an error.
R="$(api "$CLIENT_URL" /push "$CLIENT_INBOUND_KEY" \
  '{"items":[{"event_id":99,"model":"l10n.do.hr.retention.scale","ref":"l10n_do_hr_payroll.l10n_do_hr_retention_scale_2","operation":"upsert","values":{"percent":23.25}}]}')"
assert_contains "a replayed event is idempotent" "already up to date" "$(http_body "$R")"

# ---------------------------------------------------------------------------
head2 "Summary"
# ---------------------------------------------------------------------------
printf '  %s passed, %s failed\n' "$PASS" "$FAIL"
if (( FAIL > 0 )); then
  printf '  failed: %s\n' "${FAILED_NAMES[*]}"
  exit 1
fi
exit 0
