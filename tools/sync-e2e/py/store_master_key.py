"""Point the client's pull mode at the master.

Run through `odoo shell`. Reads master_url / master_key from
/tmp/sync_e2e_args.json. Mints nothing: keys are created by their owner.
"""

import json

args = json.load(open("/tmp/sync_e2e_args.json"))

params = env["ir.config_parameter"].sudo()  # noqa: F821 - provided by odoo shell
params.set_param("l10n_do_payroll_sync.master_url", args["master_url"])
params.set_param("l10n_do_payroll_sync.master_api_key", args["master_key"])
env.cr.commit()  # noqa: F821

print("OK")
