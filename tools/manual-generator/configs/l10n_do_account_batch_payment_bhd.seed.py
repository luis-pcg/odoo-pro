# Seed para el manual de l10n_do_account_batch_payment_bhd — archivo de BHD.
#
# Desde una base LIMPIA arma el escenario de pago por lotes a BHD:
#
#   * Compañía "Empresa Dominicana SRL" (RD, es_DO) con catálogo de cuentas RD
#   * Diario "Banco BHD DOP" con su cuenta propia en BHD (corriente)
#   * Tres suplidores con cuenta en tres bancos distintos (Popular, Reservas
#     y BHD), para que el archivo muestre tres códigos de banco diferentes
#     y los dos tipos de cuenta
#   * Tres facturas publicadas y pagadas -> tres pagos "Conciliado"
#   * Un asistente ya ejecutado, con el archivo .txt generado y descargable
#   * Acciones demo para que Playwright capture cada pantalla
#
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date, timedelta

MODULE = "l10n_do_account_batch_payment_bhd"

company = env.ref("base.main_company")
do = env.ref("base.do")
today = date.today()

# ── 0. Español ────────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

# ── 1. Compañía RD + catálogo de cuentas ──────────────────────────────────────
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id, "vat": "131793916"})
company.partner_id.lang = "es_DO"
env["account.chart.template"].try_loading("do", company=company, install_demo=False)

# ── 2. Diario en BanReservas con su cuenta propia ─────────────────────────────
Journal = env["account.journal"]
Bank = env["res.partner.bank"]

journal = Journal.search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
for lang in ("en_US", "es_DO"):
    journal.with_context(lang=lang).name = "Banco BHD DOP"

own_account = Bank.search([("account_number", "=", "402123456")], limit=1)
if not own_account:
    own_account = Bank.create(
        {
            "account_number": "402123456",
            "partner_id": company.partner_id.id,
            "l10n_do_bank": "bhd",
            "l10n_do_account_type": "cheque",
        }
    )
    own_account._onchange_l10n_do_bank()
journal.bank_account_id = own_account

# ── 3. Suplidores con cuenta bancaria ─────────────────────────────────────────
Partner = env["res.partner"]

# account.res.partner.bank.create() fuerza allow_out_payment a False y solo lo
# vuelve a activar si _user_can_trust(), que excluye a OdooBot / SUPERUSER_ID.
admin = env.ref("base.user_admin")
admin.group_ids |= env.ref("account.group_validate_bank_account")
TrustedBank = Bank.with_user(admin)

VENDORS = [
    # (nombre, RNC, teléfono, email, cuenta, banco, tipo de cuenta, monto)
    ("Suplidores del Caribe SRL", "131000001", "809-555-1234", "pagos@caribe.do", "774555001", "bpd", "cheque", 18500.00),
    ("José Almonte & Asociados", "131000002", "(829) 777-4488", "jose@almonte.do", "096777002", "brd", "savings", 7250.50),
    ("Ferretería Industrial SRL", "131000003", "809-333-9900", "ventas@ferrind.do", "402333003", "bhd", "cheque", 42100.75),
]

vendors = []
for name, rnc, phone, mail, acc, bank, acc_type, amount in VENDORS:
    partner = Partner.search([("name", "=", name)], limit=1)
    if not partner:
        partner = Partner.create(
            {"name": name, "vat": rnc, "phone": phone, "email": mail, "supplier_rank": 1}
        )
    account = Bank.search([("account_number", "=", acc)], limit=1)
    if not account:
        account = TrustedBank.create(
            {
                "account_number": acc,
                "partner_id": partner.id,
                "l10n_do_bank": bank,
                "l10n_do_account_type": acc_type,
                "allow_out_payment": True,
            }
        ).sudo()
        account._onchange_l10n_do_bank()
    vendors.append((partner, account, amount))

# ── 4. Facturas de proveedor pagadas -> pagos "Conciliado" ───────────────────
Move = env["account.move"]
expense = env["account.account"].search([("account_type", "=", "expense"), ("company_ids", "in", company.id)], limit=1)

payments = env["account.payment"]
for index, (partner, account, amount) in enumerate(vendors):
    bill = Move.create(
        {
            "move_type": "in_invoice",
            "partner_id": partner.id,
            "invoice_date": today - timedelta(days=20 - index * 5),
            "date": today - timedelta(days=20 - index * 5),
            "invoice_line_ids": [
                (0, 0, {"name": "Servicios contratados", "quantity": 1, "price_unit": amount, "account_id": expense.id})
            ],
        }
    )
    bill.action_post()
    wizard = (
        env["account.payment.register"]
        .with_context(active_model="account.move", active_ids=bill.ids)
        .create({"journal_id": journal.id, "payment_date": today - timedelta(days=10 - index * 3)})
    )
    wizard.action_create_payments()
    payment = bill.matched_payment_ids[:1]
    payment.partner_bank_id = account
    payments |= payment

# ── 5. Asistentes: uno cargado y uno ya generado ─────────────────────────────
Wizard = env["l10n_do.account.batch.payment"]

loaded_wizard = Wizard.create({"journal_id": journal.id, "payment_ids": [(6, 0, payments.ids)]})

generated_wizard = Wizard.create({"journal_id": journal.id, "payment_ids": [(6, 0, payments.ids)]})
generated_wizard.generate_bank_file()
print("ARCHIVO:", generated_wizard.filename)
print("CONTENIDO:\n" + generated_wizard.file.decode())

# ── 6. Acciones demo para las capturas ────────────────────────────────────────
Action = env["ir.actions.act_window"]
Data = env["ir.model.data"]
wizard_view = env.ref("l10n_do_account_batch_payment_base.l10n_do_account_batch_payment_wizard_form")


def demo_action(xmlid, vals):
    record = Data.search([("module", "=", MODULE), ("name", "=", xmlid)], limit=1)
    if record:
        action = Action.browse(record.res_id)
        action.write(vals)
        return action
    action = Action.create(vals)
    Data.create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": action.id, "noupdate": True}
    )
    return action


for xmlid, res_id in (("demo_wizard_loaded", loaded_wizard.id), ("demo_wizard_generated", generated_wizard.id)):
    demo_action(
        xmlid,
        {
            "name": "Generar Archivo de Pagos",
            "res_model": "l10n_do.account.batch.payment",
            "view_mode": "form",
            "view_id": wizard_view.id,
            "res_id": res_id,
            "target": "new",
        },
    )

demo_action(
    "demo_journal_form",
    {"name": "Diario Banco BHD", "res_model": "account.journal", "view_mode": "form", "res_id": journal.id},
)

demo_action(
    "demo_bank_accounts",
    {
        "name": "Cuentas bancarias de suplidores",
        "res_model": "res.partner.bank",
        "view_mode": "list,form",
        "domain": "[('partner_id.supplier_rank', '>', 0)]",
    },
)

env.cr.commit()
print("SEED OK: %s pagos, archivo %s" % (len(payments), generated_wizard.filename))
