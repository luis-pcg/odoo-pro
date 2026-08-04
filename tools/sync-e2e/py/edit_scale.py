"""Edit an ISR retention scale on the master, exactly as a user would.

The write goes through the ORM so the change trigger fires and the post-commit
flush delivers it, which is the whole point of the scenario.
"""

import json

args = json.load(open("/tmp/sync_e2e_args.json"))

scale = env.ref("l10n_do_hr_payroll.l10n_do_hr_retention_scale_2")  # noqa: F821
scale.percent = float(args["percent"])
env.cr.commit()  # noqa: F821

print("OK percent=%s" % scale.percent)
