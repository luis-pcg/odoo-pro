"""Run the client's reconciliation pull immediately, as the hourly cron does."""

applied = env["l10n.do.payroll.sync.service"].sudo()._pull_from_master()  # noqa: F821
env.cr.commit()  # noqa: F821

print("OK applied=%s" % applied)
