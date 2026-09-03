"""Make an instance look like a real deployment before the screenshots.

* Activates es_DO and puts the admin in it: the manual is in Spanish.
* Renames the company and gives it the Dominican Republic as its country.
  hr.rule.parameter is filtered by the country of the allowed companies, so
  without it the payroll parameters are invisible on both ends.
* Grants the groups the role needs.
"""

import json

args = json.load(open("/tmp/sync_manual_args.json"))

MASTER_GROUPS = ["databases.group_databases_manager", "l10n_do_hr_payroll.group_hr_payroll_manager_conf"]
# What the master's api user needs on a client to be able to apply everything.
CLIENT_GROUPS = [
    "base.group_system",
    "hr_payroll.group_hr_payroll_manager",
    "l10n_do_hr_payroll.group_hr_payroll_manager_conf",
]

env["res.lang"]._activate_lang("es_DO")  # noqa: F821
admin = env.ref("base.user_admin")  # noqa: F821
groups = MASTER_GROUPS if args["role"] == "master" else CLIENT_GROUPS
admin.write({"lang": "es_DO", "group_ids": [(4, env.ref(xmlid).id) for xmlid in groups]})  # noqa: F821

env.company.write({"name": args["company"], "country_id": env.ref("base.do").id})  # noqa: F821
env.cr.commit()  # noqa: F821

print("OK company=%s pais=%s lang=%s" % (env.company.name, env.company.country_id.code, admin.lang))  # noqa: F821
