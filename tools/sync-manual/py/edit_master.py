"""One edit on the master, described by the args file."""

import json

args = json.load(open("/tmp/sync_manual_args.json"))
action = args["action"]

if action == "set_parameter_value":
    value = env["hr.rule.parameter.value"].search(  # noqa: F821
        [("code", "=", args["code"]), ("date_from", "=", args["date_from"])], limit=1
    )
    value.parameter_value = args["value"]
elif action == "edit_scale":
    scale = env["l10n.do.hr.retention.scale"].search([("sequence", "=", args["sequence"])], limit=1)  # noqa: F821
    scale.write({"name": args["name"], "top_amount": args["top_amount"]})
elif action == "set_risk_percentage":
    env["l10n.do.occupational.risk.type"].search([("name", "=", args["name"])]).percentage = args["value"]  # noqa: F821
elif action == "reset_errors":
    env["project.project"].search([("l10n_do_payroll_sync_enabled", "=", True)]).action_l10n_do_payroll_sync_reset_errors()  # noqa: F821
elif action == "new_scale":
    scale = env["l10n.do.hr.retention.scale"].search([("sequence", "=", args["sequence"])], limit=1)  # noqa: F821
    if not scale:
        env["l10n.do.hr.retention.scale"].create(  # noqa: F821
            {
                "name": args["name"],
                "sequence": args["sequence"],
                "percent": args.get("percent", 30.0),
                "base_amount": args.get("base_amount", 1000000.0),
                "fixed_amount": args.get("fixed_amount", 150000.0),
            }
        )
elif action == "set_api_user":
    database = env["project.project"].search([("name", "=", args["name"])], limit=1)  # noqa: F821
    database.database_api_login = args["login"]
    if args.get("key"):
        database.database_api_key = args["key"]
elif action == "diagnose":
    env["project.project"].search([("name", "=", args["name"])]).action_l10n_do_payroll_sync_diagnose()  # noqa: F821
else:
    raise ValueError("unknown action %s" % action)

env.cr.commit()  # noqa: F821
print("DONE=%s" % action)
