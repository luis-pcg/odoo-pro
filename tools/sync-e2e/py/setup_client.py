# Prepares the client database: no sync module, only the payroll localisation,
# an admin holding the groups the remote writes need, and an API key.
import json

args = json.load(open("/tmp/sync_e2e_args.json"))
admin = env.ref("base.user_admin")
groups = [
    "base.group_system",
    "hr_payroll.group_hr_payroll_manager",
    "l10n_do_hr_payroll.group_hr_payroll_manager_conf",
]
admin.write({"group_ids": [(4, env.ref(xmlid).id) for xmlid in groups]})

# hr.rule.parameter is filtered by the country of the allowed companies
# (hr_payroll ir_rule_hr_payroll_paramater_multi_company). Without this the
# remote user sees an empty table and the sync would duplicate everything.
env.company.country_id = env.ref("base.do")
key = env["res.users.apikeys"].with_user(admin).sudo()._generate(None, args.get("name", "payroll sync e2e"), False)
env.cr.commit()
print("KEY=%s" % key)
