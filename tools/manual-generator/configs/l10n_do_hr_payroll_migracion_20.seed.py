from datetime import date

company = env.company
company.write({"country_id": env.ref("base.do").id, "currency_id": env.ref("base.DOP").id})
env.ref("base.DOP").active = True
env["res.partner"].browse(company.partner_id.id).write({"country_id": env.ref("base.do").id})

structure = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
stype = env.ref("l10n_do_hr_payroll.structure_type_employee")
stype.default_schedule_pay = "semi-monthly"

# The module already ships monthly / semi-monthly / weekly divisions.
division = env.ref("l10n_do_hr_payroll.payment_division_biweekly")
assert division.name == "semi-monthly" and division.payment_division == 2.0

risk = env["l10n.do.occupational.risk.type"].search([], limit=1)
company.write({"l10n_do_occupational_risk_type_id": risk.id})

employees = env["hr.employee"]
for name, wage, schedule in (
    ("Ana Mercedes Pérez", 85000.0, "distributed"),
    ("Beto Antonio Gómez", 45000.0, "end_of_month"),
):
    employees |= env["hr.employee"].create(
        {
            "name": name,
            "company_id": company.id,
            "country_id": env.ref("base.do").id,
            "l10n_do_has_papers": True,
            "wage": wage,
            "date_version": date(2022, 1, 1),
            "contract_date_start": date(2022, 1, 1),
            "structure_type_id": stype.id,
            "schedule_pay": "semi-monthly",
            "l10n_do_schedule_retentions": schedule,
        }
    )

# A salary adjustment restricted to the second fortnight.
itype = env["hr.payslip.input.type"].search(
    [("code", "=", "PRE"), ("available_in_attachments", "=", True)], limit=1
) or env["hr.payslip.input.type"].search([("available_in_attachments", "=", True)], limit=1)

attachment = env["hr.salary.attachment"].create(
    {
        "employee_id": employees[0].id,
        "other_input_type_id": itype.id,
        "description": "Préstamo personal",
        "monthly_amount": 2000.0,
        "total_amount": 8000.0,
        "duration_type": "limited",
        "date_start": date(2026, 8, 1),
        "l10n_do_apply_on": "second",
    }
)

# A pay run over the second fortnight of August, flagged extraordinary=False.
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
payrun.payrun_step = "500_payslip"
payslips = payrun._generate_payslips()

payrun.write({"l10n_do_christmas_run": True})

extra = env["hr.payslip.run"].create({
    "name": "Nómina extraordinaria Agosto 2026",
    "company_id": env.company.id,
    "structure_id": env.ref("l10n_do_hr_payroll.hr_payroll_structure_base").id,
    "date_start": "2026-08-01",
    "date_end": "2026-08-15",
    "l10n_do_extraordinary": True,
})
liq = env["hr.payslip.run"].create({
    "name": "Liquidación Agosto 2026",
    "company_id": env.company.id,
    "structure_id": env.ref("l10n_do_hr_payroll.hr_payroll_structure_base").id,
    "date_start": "2026-08-01",
    "date_end": "2026-08-31",
    "l10n_do_is_liquidation": True,
})

slip = payslips.sorted("id")[0]
dter = env.ref("l10n_do_hr_payroll.hr_payslip_input_type_deposit_third_parties")
employee = slip.employee_id
if not employee.work_contact_id:
    employee.work_contact_id = env["res.partner"].create({"name": employee.name}).id
bank = env["res.partner.bank"].create({
    "account_number": "0123456789",
    "partner_id": employee.work_contact_id.id,
    "company_id": env.company.id,
})
slip.write({"input_line_ids": [(0, 0, {"input_type_id": dter.id, "amount": 3000.0})]})
slip.write({"l10n_do_deposit_third_parties_ids": [(0, 0, {"bank_account_id": bank.id, "amount": 3000.0})]})
slip.compute_sheet()

user = env["res.users"].search([("login", "=", "admin")], limit=1)
user.write({"password": "admin"})

env.cr.commit()
print(
    "SEED OK employees=%s attachment=%s payrun=%s payslips=%s lines=%s"
    % (employees.ids, attachment.id, payrun.id, payslips.ids, [len(p.line_ids) for p in payslips])
)
