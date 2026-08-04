"""Drive one event through its whole retry budget without waiting for backoff.

Each pass makes the event due immediately and then drains the queue; the client
is down, so every attempt fails and the retry counter climbs until the event
dead-letters. This is what the real cron does, minus the waiting.
"""

import json

from odoo import fields

from odoo.addons.l10n_do_hr_payroll_sync.models.sync_event import MAX_RETRIES

args = json.load(open("/tmp/sync_e2e_args.json"))

Event = env["l10n.do.payroll.sync.event"].sudo()  # noqa: F821
event = Event.browse(int(args["event_id"]))

for _ in range(MAX_RETRIES + 2):
    if event.state == "dead":
        break
    event.write({"state": "pending", "next_retry_at": fields.Datetime.now()})
    env.cr.commit()  # noqa: F821
    Event._process_queue(client_ids=event.client_id.ids)
    env.cr.commit()  # noqa: F821
    event.invalidate_recordset()

print("OK state=%s retries=%s" % (event.state, event.retry_count))
