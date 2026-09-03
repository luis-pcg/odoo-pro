# Registers the client instance on the master, using the fields of the
# `databases` module. The api key column is written through its inverse.
import json

args = json.load(open("/tmp/sync_e2e_args.json"))
project = env["project.project"].search([("database_url", "=", args["url"])], limit=1)
values = {
    "name": args.get("name", "E2E client"),
    "database_hosting": "premise",
    "database_name": args["db"],
    "database_url": args["url"],
    "database_api_login": args.get("login", "admin"),
    "l10n_do_payroll_sync_enabled": True,
}
if project:
    project.write(values)
else:
    project = env["project.project"].create(values)
project.database_api_key = args["key"]
env.cr.commit()
print("PROJECT_ID=%s" % project.id)
