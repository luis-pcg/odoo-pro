from datetime import date

company = env.company
dop = env.ref("base.DOP")
dop.active = True

es = env["res.lang"]._activate_lang("es_DO")
env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
admin = env["res.users"].search([("login", "=", "admin")], limit=1)
admin.lang = "es_DO"

company.write(
    {
        "name": "Empresa Dominicana SRL",
        "country_id": env.ref("base.do").id,
        "currency_id": dop.id,
        "email": "nomina@empresa.do",
        "l10n_do_occupational_risk_type_id": env["l10n.do.occupational.risk.type"].search([], limit=1).id,
    }
)
company.partner_id.write({"country_id": env.ref("base.do").id, "lang": "es_DO"})
company.partner_id.with_context(no_vat_validation=True).vat = "131793916"

structure = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
stype = env.ref("l10n_do_hr_payroll.structure_type_employee")
stype.default_schedule_pay = "semi-monthly"
structure.journal_id = env["account.journal"].create(
    {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id}
)

JOURNALS = [
    ("NBPD", "Banco Popular - Nómina", "bpd", "788397489"),
    ("NBHD", "Banco BHD - Nómina", "bhd", "909489302"),
    ("NBDI", "Banco BDI - Nómina", "bdi", "550011223"),
    ("NBRD", "BanReservas - Nómina", "brd", "240-012345-6"),
]
for code, name, bank, number in JOURNALS:
    account = env["res.partner.bank"].create(
        {
            "account_number": number,
            "partner_id": company.partner_id.id,
            "l10n_do_bank": bank,
            "l10n_do_account_type": "cheque",
            "currency_id": dop.id,
        }
    )
    env["account.journal"].create(
        {"name": name, "code": code, "type": "bank", "bank_account_id": account.id, "company_id": company.id}
    )

EMPLOYEES = [
    ("Ana Mercedes Pérez", 85000.0, "00112345678", False, "960-123456-7", "brd", "savings", "ana.perez@correo.do"),
    ("Beto Antonio Gómez", 45000.0, "40298765432", False, "774-55500-1", "bpd", "cheque", "beto.gomez@correo.do"),
    ("Carlos Pérez Marval", 52000.0, False, "VEN1234567", "123-4567-8", "bhd", "savings", False),
]
employees = env["hr.employee"]
for name, wage, cedula, passport, number, bank, acc_type, email in EMPLOYEES:
    employee = env["hr.employee"].create(
        {
            "name": name,
            "company_id": company.id,
            "country_id": env.ref("base.do").id,
            "identification_id": cedula,
            "passport_id": passport,
            "private_email": email,
            "work_phone": "809-555-0101",
        }
    )
    employee.version_id.write(
        {
            "wage": wage,
            "date_version": date(2022, 1, 1),
            "contract_date_start": date(2022, 1, 1),
            "structure_type_id": stype.id,
            "schedule_pay": "semi-monthly",
            "l10n_do_schedule_retentions": "distributed",
        }
    )
    account = env["res.partner.bank"].create(
        {
            "account_number": number,
            "partner_id": employee.work_contact_id.id,
            "l10n_do_bank": bank,
            "l10n_do_account_type": acc_type,
            "currency_id": dop.id,
            "allow_out_payment": True,
        }
    )
    employee.bank_account_ids = [(4, account.id)]
    employees |= employee

payrun = env["hr.payslip.run"].create(
    {
        "name": "Nómina 1ra quincena Septiembre 2026",
        "company_id": company.id,
        "structure_id": structure.id,
        "date_start": date(2026, 9, 1),
        "date_end": date(2026, 9, 15),
    }
)
payrun.action_add_versions(employees.version_id.ids)
payslips = payrun._generate_payslips()
payslips.compute_sheet()
payrun.action_validate()

env["hr.payslip.run"].create(
    {
        "name": "Nómina 2da quincena Septiembre 2026",
        "company_id": company.id,
        "structure_id": structure.id,
        "date_start": date(2026, 9, 16),
        "date_end": date(2026, 9, 30),
    }
)

admin.write({"password": "admin", "group_ids": [(4, env.ref("l10n_do_hr_payroll.group_hr_payroll_manager_conf").id)]})
env.cr.commit()
print("SEED OK payrun=%s state=%s slips=%s" % (payrun.id, payrun.state, payslips.mapped("state")))
