"""Deterministic ISR fingerprint of the current parameter set.

Prints one `ISR=` line whose value must not change when the sync module is
installed. Uses `_compute_annual_retention` directly so the probe depends only
on the retention scales, not on employee or contract demo data.
"""

scale = env["l10n.do.hr.retention.scale"]  # noqa: F821

SALARIES = (300000.0, 416220.0, 500000.0, 700000.0, 900000.0, 1500000.0)
values = ["%.2f" % scale._compute_annual_retention(s) for s in SALARIES]

print("EXEMPT=%.2f" % scale._get_annual_exempt_amount())
print("ISR=" + ",".join(values))
