"""Run a synchronization over every enabled database, or just one."""

import json

args = json.load(open("/tmp/sync_manual_args.json"))
Project = env["project.project"]  # noqa: F821
if args.get("name"):
    databases = Project.search([("name", "=", args["name"])])
else:
    databases = Project.search([("l10n_do_payroll_sync_enabled", "=", True)])
admin = env.ref("base.user_admin")  # noqa: F821
run = env["l10n.do.payroll.sync.run"].with_user(admin).sync_databases(  # noqa: F821
    databases, trigger=args.get("trigger", "manual"), dry_run=args.get("dry_run", False)
)
env.cr.commit()  # noqa: F821
print(
    "RUN=%s"
    % json.dumps(
        {
            "run": run.name,
            "clients": run.client_count,
            "states": run.log_ids.mapped("state"),
            "created": sum(run.log_ids.mapped("created_count")),
            "updated": sum(run.log_ids.mapped("updated_count")),
        }
    )
)
