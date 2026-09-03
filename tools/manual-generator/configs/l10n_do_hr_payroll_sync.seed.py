# Seed for the payroll parameter sync manual.
#
# Builds a master instance that looks like one which has been running for a
# while: two registered clients, a queue holding every event state, and an audit
# trail with successes, a rejection and a denied call. Nothing here talks to a
# real client -- the rows are written directly so the monitoring screens have
# something worth photographing and the manual is reproducible offline.

import json
import secrets
from datetime import timedelta

from odoo import fields
from odoo.addons.base.models.res_users import KEY_CRYPT_CONTEXT

errors = []
now = fields.Datetime.now()

params = env["ir.config_parameter"].sudo()
params.set_param("l10n_do_payroll_sync.role", "master")
params.set_param("l10n_do_payroll_sync.push_on_commit", "True")
params.set_param("l10n_do_payroll_sync.rate_limit_per_minute", 120)

# The developer's main Odoo server has no dbfilter, so it picks up this database
# and runs its crons. The queue cron would try to reach the fictional client URLs
# below and rewrite the very rows the screenshots are meant to show. Park the
# crons so the manual is reproducible.
env["ir.cron"].sudo().search([
    ("name", "like", "Payroll Sync%"),
]).write({"active": False})

Client = env["l10n.do.payroll.sync.client"].sudo()
Event = env["l10n.do.payroll.sync.event"].sudo()
Log = env["l10n.do.payroll.sync.log"].sudo()

Event.search([]).unlink()
Log.search([]).unlink()
Client.with_context(active_test=False).search([]).unlink()

# ---------------------------------------------------------------------------
# Two clients: one healthy, one that has stopped answering.
# ---------------------------------------------------------------------------
healthy = Client.create({
    "name": "Ferretería Duarte SRL",
    "base_url": "https://ferreteria-duarte.odoo.com",
    "api_key_hash": KEY_CRYPT_CONTEXT.hash(secrets.token_urlsafe(24)),
    "remote_api_key": secrets.token_urlsafe(24),
    "push_enabled": True,
    "pull_enabled": True,
    "state": "online",
    "last_seen": now - timedelta(minutes=3),
    "dest_company_id": 1,
})
offline = Client.create({
    "name": "Transporte Cibao SA",
    "base_url": "https://transporte-cibao.odoo.com",
    "api_key_hash": KEY_CRYPT_CONTEXT.hash(secrets.token_urlsafe(24)),
    "remote_api_key": secrets.token_urlsafe(24),
    "push_enabled": True,
    "pull_enabled": True,
    "state": "error",
    "last_seen": now - timedelta(hours=26),
    "last_error": "HTTP 0 - HTTPSConnectionPool(host='transporte-cibao.odoo.com', port=443): "
                  "Max retries exceeded (connection refused)",
    "dest_company_id": 1,
})

scale_2 = env.ref("l10n_do_hr_payroll.l10n_do_hr_retention_scale_2")
scale_3 = env.ref("l10n_do_hr_payroll.l10n_do_hr_retention_scale_3")
risk_2 = env.ref("l10n_do_hr_payroll.risk_type_2")
division = env.ref("l10n_do_hr_payroll.payment_division_monthly")
service = env["l10n.do.payroll.sync.service"].sudo()
scale_line = env.ref("l10n_do_hr_payroll_sync.sync_model_retention_scale")
risk_line = env.ref("l10n_do_hr_payroll_sync.sync_model_occupational_risk_type")
division_line = env.ref("l10n_do_hr_payroll_sync.sync_model_payment_division")


def make_event(client, line, record, state, **extra):
    values = {
        "client_id": client.id,
        "model_name": record._name,
        "res_id": record.id,
        "ref": service._build_ref(line, record),
        "operation": "upsert",
        "payload": json.dumps(service._serialize(line, record), sort_keys=True, indent=2),
        "state": state,
    }
    values.update(extra)
    return Event.create(values)


# Delivered: the ordinary case, an ISR scale update that landed everywhere.
make_event(healthy, scale_line, scale_2, "sent", sent_at=now - timedelta(minutes=12),
           acked_at=now - timedelta(minutes=12))
make_event(healthy, scale_line, scale_3, "sent", sent_at=now - timedelta(minutes=12),
           acked_at=now - timedelta(minutes=12))
make_event(healthy, risk_line, risk_2, "sent", sent_at=now - timedelta(hours=5))
make_event(healthy, division_line, division, "sent", sent_at=now - timedelta(days=2))

# Waiting: queued a moment ago, the flush has not run yet.
make_event(healthy, division_line, division, "pending", next_retry_at=now)

# Retrying with backoff: the client is down but the retry budget is not spent.
make_event(offline, scale_line, scale_2, "failed", retry_count=2,
           next_retry_at=now + timedelta(minutes=2),
           error="HTTP 0 - connection refused")
make_event(offline, scale_line, scale_3, "failed", retry_count=1,
           next_retry_at=now + timedelta(minutes=1),
           error="HTTP 0 - connection refused")

# Dead letter: retries exhausted, needs a human.
make_event(offline, risk_line, risk_2, "dead", retry_count=6,
           error="HTTP 0 - connection refused")
make_event(offline, division_line, division, "dead", retry_count=6,
           error="HTTP 500 - client rejected the event: unique constraint violated")

# ---------------------------------------------------------------------------
# Audit trail: successes, one rejection, one denied credential.
# ---------------------------------------------------------------------------
Log.record(direction="out", status="ok", endpoint="/push", client_id=healthy.id, http_code=200,
           message="2/2 applied", payload={"version": "1.0", "items": 2})
Log.record(direction="out", status="ok", endpoint="/ping", client_id=healthy.id, http_code=200,
           message="pong")
Log.record(direction="in", status="ok", endpoint="/ack", client_id=healthy.id, http_code=200,
           message="2 confirmed, 0 nacked", remote_addr="190.80.14.22",
           payload={"results": [{"event_id": 1, "status": "ok"}]})
Log.record(direction="in", status="ok", endpoint="/pull", client_id=healthy.id, http_code=200,
           message="9 items", remote_addr="190.80.14.22")
Log.record(direction="out", status="error", endpoint="/push", client_id=offline.id, http_code=0,
           message="Max retries exceeded (connection refused)",
           payload={"version": "1.0", "items": 2})
Log.record(direction="in", status="denied", endpoint="/pull", http_code=403,
           message="unknown credential", remote_addr="45.132.88.7",
           payload={"api_key": "should-never-appear", "since": None})

env.cr.commit()

# ---------------------------------------------------------------------------
# Self-checks: the manual must not document a broken state.
# ---------------------------------------------------------------------------
if Client.search_count([]) != 2:
    errors.append("expected 2 clients")
if Event.search_count([("state", "=", "dead")]) != 2:
    errors.append("expected 2 dead-letter events")
if Event.search_count([("state", "=", "sent")]) != 4:
    errors.append("expected 4 delivered events")
leaked = Log.search([("payload", "like", "%should-never-appear%")])
if leaked:
    errors.append("the API key was not redacted in the sync log")
if not all(e.ref for e in Event.search([])):
    errors.append("some event has no cross-database reference")

if errors:
    print("SEED FAIL:")
    for e in errors:
        print("  -", e)
else:
    print("SEED OK: 2 clientes, %d eventos, %d entradas de bitácora"
          % (Event.search_count([]), Log.search_count([])))
