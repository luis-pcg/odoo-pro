"""Requeue a dead-lettered event and drain the queue, as the Retry button does."""

import json

args = json.load(open("/tmp/sync_e2e_args.json"))

Event = env["l10n.do.payroll.sync.event"].sudo()  # noqa: F821
event = Event.browse(int(args["event_id"]))
event.action_retry()
env.cr.commit()  # noqa: F821

Event._process_queue(client_ids=event.client_id.ids)
env.cr.commit()  # noqa: F821
event.invalidate_recordset()

print("OK state=%s" % event.state)
