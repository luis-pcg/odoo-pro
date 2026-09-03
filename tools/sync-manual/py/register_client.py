"""Register a client instance on the master, as a database of the fleet."""

import json

args = json.load(open("/tmp/sync_manual_args.json"))
project = env["project.project"].search([("database_url", "=", args["url"])], limit=1)  # noqa: F821
values = {
    "name": args["name"],
    "database_hosting": "premise",
    "database_name": args["db"],
    "database_url": args["url"],
    "database_api_login": "admin",
    "database_version": "19.0",
    "l10n_do_payroll_sync_enabled": True,
}
if project:
    project.write(values)
else:
    project = env["project.project"].create(values)  # noqa: F821
project.database_api_key = args["key"]
env.cr.commit()  # noqa: F821
print("PROJECT_ID=%s" % project.id)
