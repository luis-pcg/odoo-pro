"""Configure sync_master as the master and register the client instance.

Run through `odoo shell`. Reads the client URL and the client's inbound key from
/tmp/sync_e2e_args.json, prints `KEY=<secret>` -- the key the client will use to
call our pull/ack endpoints.
"""

import json
import secrets

from odoo.addons.base.models.res_users import KEY_CRYPT_CONTEXT

args = json.load(open("/tmp/sync_e2e_args.json"))

key = secrets.token_urlsafe(24)
params = env["ir.config_parameter"].sudo()  # noqa: F821 - provided by odoo shell
params.set_param("l10n_do_payroll_sync.role", "master")
params.set_param("l10n_do_payroll_sync.push_on_commit", "True")
params.set_param("l10n_do_payroll_sync.rate_limit_per_minute", 1000)

Client = env["l10n.do.payroll.sync.client"].sudo()  # noqa: F821
values = {
    "name": "Cliente E2E",
    "base_url": args["client_url"],
    "api_key_hash": KEY_CRYPT_CONTEXT.hash(key),
    "remote_api_key": args["client_key"],
    "push_enabled": True,
    "pull_enabled": True,
}
client = Client.with_context(active_test=False).search(
    [("base_url", "=", args["client_url"])], limit=1
)
if client:
    client.write(dict(values, active=True))
else:
    client = Client.create(values)
env.cr.commit()  # noqa: F821

print("KEY=" + key)
print("CLIENT_ID=%s" % client.id)
