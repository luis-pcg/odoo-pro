# Applies one edit on the master, described by the args file.
import json

args = json.load(open("/tmp/sync_e2e_args.json"))
action = args["action"]

if action == "set_parameter_value":
    value = env["hr.rule.parameter.value"].search(
        [("code", "=", args["code"]), ("date_from", "=", args["date_from"])], limit=1
    )
    value.parameter_value = args["value"]
elif action == "new_parameter":
    parameter = env["hr.rule.parameter"].create(
        {"name": args["name"], "code": args["code"], "country_id": env.ref("base.do").id}
    )
    env["hr.rule.parameter.value"].create(
        {
            "rule_parameter_id": parameter.id,
            "date_from": args["date_from"],
            "parameter_value": args["value"],
        }
    )
elif action == "edit_scale":
    scale = env["l10n.do.hr.retention.scale"].search([("sequence", "=", args["sequence"])], limit=1)
    scale.write({"name": args["name"], "top_amount": args["top_amount"]})
elif action == "drop_risk_type":
    env["l10n.do.occupational.risk.type"].search([("name", "=", args["name"])]).unlink()
elif action == "new_scale":
    env["l10n.do.hr.retention.scale"].create(
        {
            "name": args["name"],
            "sequence": args["sequence"],
            "percent": args.get("percent", 30.0),
            "base_amount": args.get("base_amount", 1000000.0),
            "fixed_amount": args.get("fixed_amount", 150000.0),
        }
    )
elif action == "drop_scale":
    env["l10n.do.hr.retention.scale"].search([("sequence", "=", args["sequence"])]).unlink()
elif action == "set_api_user":
    database = env["project.project"].browse(args["project_id"])
    database.database_api_login = args["login"]
    if args.get("key"):
        database.database_api_key = args["key"]
else:
    raise ValueError("unknown action %s" % action)

env.cr.commit()
print("DONE=%s" % action)
