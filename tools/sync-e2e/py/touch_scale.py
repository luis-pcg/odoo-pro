"""Edit a retention scale, to prove the trigger stays inert without a role."""

scale = env.ref("l10n_do_hr_payroll.l10n_do_hr_retention_scale_2")  # noqa: F821
scale.percent = scale.percent  # a real write, same value
scale.top_amount = scale.top_amount + 1
env.cr.commit()  # noqa: F821

print("OK")
