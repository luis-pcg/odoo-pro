"""Tamper with a client the way one of its users would."""

import json

args = json.load(open("/tmp/sync_manual_args.json"))
action = args["action"]

if action == "set_risk_percentage":
    env["l10n.do.occupational.risk.type"].search([("name", "=", args["name"])]).percentage = args["value"]  # noqa: F821
elif action == "add_retro_value":
    parameter = env["hr.rule.parameter"].search([("code", "=", args["code"])], limit=1)  # noqa: F821
    exists = env["hr.rule.parameter.value"].search(  # noqa: F821
        [("code", "=", args["code"]), ("date_from", "=", args["date_from"])]
    )
    if not exists:
        env["hr.rule.parameter.value"].create(  # noqa: F821
            {
                "rule_parameter_id": parameter.id,
                "date_from": args["date_from"],
                "parameter_value": args["value"],
            }
        )
elif action == "revoke_group":
    env.ref("base.user_admin").write({"group_ids": [(3, env.ref(args["group"]).id)]})  # noqa: F821
elif action == "grant_group":
    env.ref("base.user_admin").write({"group_ids": [(4, env.ref(args["group"]).id)]})  # noqa: F821
elif action == "restricted_api_user":
    # What a client normally grants an integration login: the payroll groups,
    # and not base.group_system, which nobody hands out lightly.
    groups = [
        "base.group_user",
        "hr.group_hr_manager",
        "hr_payroll.group_hr_payroll_manager",
        "l10n_do_hr_payroll.group_hr_payroll_manager_conf",
    ]
    user = env["res.users"].search([("login", "=", "sync_api")], limit=1)  # noqa: F821
    if not user:
        user = env["res.users"].create({"name": "Sincronización de nómina", "login": "sync_api"})  # noqa: F821
    user.write({"group_ids": [(6, 0, [env.ref(xmlid).id for xmlid in groups])]})  # noqa: F821
    env.cr.commit()  # noqa: F821
    print("KEY=%s" % env["res.users.apikeys"].with_user(user).sudo()._generate(None, "Sync API", False))  # noqa: F821
else:
    raise ValueError("unknown action %s" % action)

env.cr.commit()  # noqa: F821
print("DONE=%s" % action)
