from datetime import date

company = env.company
env.ref("base.DOP").active = True
company.write({"country_id": env.ref("base.do").id, "currency_id": env.ref("base.DOP").id})
company.partner_id.country_id = env.ref("base.do")
company.l10n_do_occupational_risk_type_id = env["l10n.do.occupational.risk.type"].search([], limit=1)

structure = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
stype = env.ref("l10n_do_hr_payroll.structure_type_employee")
stype.default_schedule_pay = "semi-monthly"
structure.journal_id = env["account.journal"].create(
    {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id}
)

employees = env["hr.employee"]
for name, wage, schedule in (
    ("Ana Mercedes Pérez", 85000.0, "distributed"),
    ("Beto Antonio Gómez", 45000.0, "end_of_month"),
):
    employee = env["hr.employee"].create({"name": name, "company_id": company.id, "country_id": env.ref("base.do").id})
    employee.version_id.write(
        {
            "wage": wage,
            "date_version": date(2022, 1, 1),
            "contract_date_start": date(2022, 1, 1),
            "structure_type_id": stype.id,
            "schedule_pay": "semi-monthly",
            "l10n_do_schedule_retentions": schedule,
        }
    )
    employees |= employee
ana, beto = employees

rule = lambda xmlid: env.ref("l10n_do_hr_payroll." + xmlid)
loan = env["hr.salary.attachment"].create(
    {
        "employee_id": ana.id,
        "salary_rule_id": rule("hr_rule_employee_loan").id,
        "description": "Préstamo personal",
        "amount": 2000.0,
        "is_recurring": True,
        "date_start": date(2026, 8, 1),
        "date_estimated_end": date(2026, 11, 30),
        "l10n_do_apply_on": "second",
    }
)
env["hr.salary.attachment"].create(
    {
        "employee_id": beto.id,
        "salary_rule_id": rule("hr_rule_employee_unbalance").id,
        "description": "Faltante de caja 12/08",
        "amount": 500.0,
        "date_start": date(2026, 8, 1),
    }
)

payrun = env["hr.payslip.run"].create(
    {
        "name": "Nómina 2da quincena Agosto 2026",
        "company_id": company.id,
        "structure_id": structure.id,
        "date_start": date(2026, 8, 16),
        "date_end": date(2026, 8, 31),
    }
)
payrun.action_add_versions(employees.version_id.ids)
payslips = payrun._generate_payslips()

for vals in (
    {"name": "Regalía Pascual 2026", "date_start": "2026-12-01", "date_end": "2026-12-15", "l10n_do_christmas_run": True},
    {"name": "Nómina extraordinaria Agosto 2026", "date_start": "2026-08-01", "date_end": "2026-08-15", "l10n_do_extraordinary": True},
    {"name": "Liquidación Agosto 2026", "date_start": "2026-08-01", "date_end": "2026-08-31", "l10n_do_is_liquidation": True},
):
    env["hr.payslip.run"].create({"company_id": company.id, "structure_id": structure.id, **vals})

slip = payslips.filtered(lambda p: p.employee_id == ana)
slip.write(
    {
        "input_line_ids": [
            (0, 0, {"salary_rule_id": rule("hr_rule_incentives").id, "amount": 5000.0}),
        ]
    }
)
payslips.compute_sheet()

admin = env["res.users"].search([("login", "=", "admin")], limit=1)
admin.write({"password": "admin", "group_ids": [(4, env.ref("l10n_do_hr_payroll.group_hr_payroll_manager_conf").id)]})
env.cr.commit()
print(
    "SEED OK payrun=%s slip=%s ana=%s beto=%s loan=%s lines=%s"
    % (payrun.id, slip.id, ana.id, beto.id, loan.id, [len(p.line_ids) for p in payslips])
)
