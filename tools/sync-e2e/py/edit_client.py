# Tampers with the client database the way an end user would.
import json

args = json.load(open("/tmp/sync_e2e_args.json"))
action = args["action"]

if action == "set_risk_percentage":
    env["l10n.do.occupational.risk.type"].search([("name", "=", args["name"])]).percentage = args["value"]
elif action == "add_retro_value":
    parameter = env["hr.rule.parameter"].search([("code", "=", args["code"])], limit=1)
    env["hr.rule.parameter.value"].create(
        {
            "rule_parameter_id": parameter.id,
            "date_from": args["date_from"],
            "parameter_value": args["value"],
        }
    )
elif action == "drop_risk_type":
    env["l10n.do.occupational.risk.type"].search([("name", "=", args["name"])]).unlink()
elif action == "revoke_group":
    env.ref("base.user_admin").write({"group_ids": [(3, env.ref(args["group"]).id)]})
elif action == "grant_group":
    env.ref("base.user_admin").write({"group_ids": [(4, env.ref(args["group"]).id)]})
elif action == "restricted_api_user":
    # What a client really grants: the payroll groups the notes ask for, and
    # not base.group_system, which nobody hands out to an integration login.
    groups = [
        "base.group_user",
        "hr.group_hr_manager",
        "hr_payroll.group_hr_payroll_manager",
        "l10n_do_hr_payroll.group_hr_payroll_manager_conf",
    ]
    user = env["res.users"].search([("login", "=", "sync_api")], limit=1)
    if not user:
        user = env["res.users"].create({"name": "Payroll Sync API", "login": "sync_api"})
    user.write({"group_ids": [(6, 0, [env.ref(xmlid).id for xmlid in groups])]})
    env.cr.commit()
    print("KEY=%s" % env["res.users.apikeys"].with_user(user).sudo()._generate(None, "payroll sync e2e", False))
else:
    raise ValueError("unknown action %s" % action)

env.cr.commit()
print("DONE=%s" % action)
