import json

args = json.load(open("/tmp/sync_e2e_args.json"))
env["project.project"].browse(args["project_id"]).action_l10n_do_payroll_sync_reset_errors()
env.cr.commit()
print("DONE=reset")
