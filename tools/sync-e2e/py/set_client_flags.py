"""Toggle push/pull on the registered client, to isolate one transport at a time."""

import json

args = json.load(open("/tmp/sync_e2e_args.json"))

Client = env["l10n.do.payroll.sync.client"].sudo()  # noqa: F821
client = Client.search([], limit=1)
values = {k: v for k, v in args.items() if k in ("push_enabled", "pull_enabled", "active")}
client.write(values)
env.cr.commit()  # noqa: F821

print("OK push=%s pull=%s" % (client.push_enabled, client.pull_enabled))
