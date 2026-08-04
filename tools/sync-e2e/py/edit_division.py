"""Edit the monthly payment division on the master (company-scoped parameter)."""

import json

args = json.load(open("/tmp/sync_e2e_args.json"))

division = env.ref("l10n_do_hr_payroll.payment_division_monthly")  # noqa: F821
division.payment_division = float(args["division"])
env.cr.commit()  # noqa: F821

print("OK division=%s company=%s" % (division.payment_division, division.company_id.id))
