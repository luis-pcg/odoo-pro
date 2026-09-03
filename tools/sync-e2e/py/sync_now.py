# Runs one synchronization and prints a machine readable summary.
import json

args = json.load(open("/tmp/sync_e2e_args.json"))
database = env["project.project"].browse(args["project_id"])
run = env["l10n.do.payroll.sync.run"].sync_databases(database, trigger="manual", dry_run=args.get("dry_run", False))
env.cr.commit()
log = run.log_ids[:1]
print(
    "RESULT=%s"
    % json.dumps(
        {
            "run": run.name,
            "state": log.state if log else "none",
            "created": log.created_count if log else 0,
            "updated": log.updated_count if log else 0,
            "unchanged": log.unchanged_count if log else 0,
            "extras": log.extra_remote_count if log else 0,
            "errors": log.error_count if log else 0,
            "rpc_calls": log.rpc_call_count if log else 0,
            "message": (log.message or "")[:400] if log else "",
            "db_status": database.l10n_do_payroll_sync_last_status,
            "db_errors": database.l10n_do_payroll_sync_error_count,
        }
    )
)
