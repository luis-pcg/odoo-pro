# Deterministic ISR fingerprint: it must not move when the sync module or its
# dependency tree is installed.
scale = env["l10n.do.hr.retention.scale"]
salaries = [180000.0, 420000.0, 500000.0, 700000.0, 900000.0, 1500000.0]
figures = [round(scale._compute_annual_retention(salary), 2) for salary in salaries]
print("ISR=%s" % "|".join("%.2f" % figure for figure in figures))
