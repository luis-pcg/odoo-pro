# Seed para el manual de l10n_do_account_batch_payment_base — "Archivos de pago".
#
# Desde una base LIMPIA arma un escenario de pagos a proveedores dominicanos:
#
#   * Compañía "Empresa Dominicana SRL" (RD, es_DO) con catálogo de cuentas RD
#   * Diario de banco "Banco Popular DOP" con su propia cuenta bancaria (BPD)
#   * Tres suplidores con cuenta bancaria en distintos bancos RD (BPD, BHD,
#     BanReservas), cada una con su tipo de cuenta (cheque / ahorros)
#   * Tres facturas de proveedor publicadas y pagadas -> tres pagos en estado
#     "Pagado", que son los que lista el asistente de archivo de pagos
#   * Un suplidor sin cuenta bancaria, para mostrar el error de validación
#   * Acciones demo para que Playwright capture cada pantalla
#
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date, timedelta

MODULE = "l10n_do_account_batch_payment_base"

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

# ── 2. Diario de banco y su cuenta bancaria propia ────────────────────────────
Journal = env["account.journal"]
Bank = env["res.partner.bank"]

journal = Journal.search([("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)
if not journal:
    journal = Journal.create({"name": "Banco Popular DOP", "type": "bank", "code": "BPD", "company_id": company.id})
# El nombre del diario es traducible: se fija en ambos idiomas para que la
# captura y la base en inglés muestren lo mismo.
for lang in ("en_US", "es_DO"):
    journal.with_context(lang=lang).name = "Banco Popular DOP"

own_account = Bank.search([("account_number", "=", "774000123")], limit=1)
if not own_account:
    own_account = Bank.create(
        {
            "account_number": "774000123",
            "partner_id": company.partner_id.id,
            "l10n_do_bank": "bpd",
            "l10n_do_account_type": "cheque",
        }
    )
    own_account._onchange_l10n_do_bank()
journal.bank_account_id = own_account

# ── 3. Suplidores con cuenta bancaria ─────────────────────────────────────────
Partner = env["res.partner"]

# account.res.partner.bank.create() fuerza allow_out_payment a False y solo lo
# vuelve a activar si _user_can_trust(), que excluye a OdooBot / SUPERUSER_ID.
# De ahí que las cuentas se creen como el usuario admin, con el grupo que
# autoriza a marcar una cuenta como de confianza.
admin = env.ref("base.user_admin")
admin.group_ids |= env.ref("account.group_validate_bank_account")
TrustedBank = Bank.with_user(admin)

VENDORS = [
    # (nombre, RNC, teléfono, email, cuenta, banco, tipo de cuenta, monto)
    ("Suplidores del Caribe SRL", "131000001", "809-555-1234", "pagos@caribe.do", "774555001", "bpd", "cheque", 18500.00),
    ("José Almonte & Asociados", "131000002", "(829) 777-4488", "jose@almonte.do", "402777002", "bhd", "savings", 7250.50),
    ("Ferretería Industrial SRL", "131000003", "809-333-9900", "ventas@ferrind.do", "960333003", "brd", "cheque", 42100.75),
]

vendors = []
for name, rnc, phone, mail, acc, bank, acc_type, amount in VENDORS:
    partner = Partner.search([("name", "=", name)], limit=1)
    if not partner:
        partner = Partner.create({"name": name, "vat": rnc, "phone": phone, "email": mail, "supplier_rank": 1})
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
        # El onchange que rellena nombre, BIC y dirección del banco solo corre
        # en la interfaz; desde código hay que invocarlo a mano.
        account._onchange_l10n_do_bank()
    vendors.append((partner, account, amount))

# Un suplidor deliberadamente sin cuenta bancaria: es el que dispara el error
# "Recipient Bank Account is required to generate batch payment file".
no_bank_vendor = Partner.search([("name", "=", "Transporte Rápido SRL")], limit=1)
if not no_bank_vendor:
    no_bank_vendor = Partner.create(
        {"name": "Transporte Rápido SRL", "vat": "131000004", "supplier_rank": 1, "email": "info@transrapido.do"}
    )

# ── 4. Facturas de proveedor pagadas -> pagos en estado "Pagado" ──────────────
Move = env["account.move"]
expense = env["account.account"].search(
    [("account_type", "=", "expense"), ("company_ids", "in", company.id)], limit=1
)

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

print("PAGOS:", [(p.name, p.state, p.partner_bank_id.display_name) for p in payments])

# ── 5. Acciones demo para las capturas ────────────────────────────────────────
Action = env["ir.actions.act_window"]
Data = env["ir.model.data"]


def demo_action(xmlid, vals):
    record = Data.search([("module", "=", MODULE), ("name", "=", xmlid)], limit=1)
    if record:
        action = env["ir.actions.act_window"].browse(record.res_id)
        action.write(vals)
        return action
    action = Action.create(vals)
    Data.create(
        {"module": MODULE, "name": xmlid, "model": "ir.actions.act_window", "res_id": action.id, "noupdate": True}
    )
    return action


wizard_view = env.ref("l10n_do_account_batch_payment_base.l10n_do_account_batch_payment_wizard_form")

demo_action(
    "demo_wizard_empty",
    {
        "name": "Generar Archivo de Pagos",
        "res_model": "l10n_do.account.batch.payment",
        "view_mode": "form",
        "view_id": wizard_view.id,
        "target": "new",
    },
)

demo_action(
    "demo_wizard_journal",
    {
        "name": "Generar Archivo de Pagos",
        "res_model": "l10n_do.account.batch.payment",
        "view_mode": "form",
        "view_id": wizard_view.id,
        "target": "new",
        "context": "{'default_journal_id': %d}" % journal.id,
    },
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

demo_action(
    "demo_bank_account_form",
    {
        "name": "Cuenta bancaria - %s" % vendors[1][0].name,
        "res_model": "res.partner.bank",
        "view_mode": "form",
        "res_id": vendors[1][1].id,
    },
)

demo_action(
    "demo_payments",
    {
        "name": "Pagos a suplidores",
        "res_model": "account.payment",
        "view_mode": "list,form",
        "domain": "[('payment_type', '=', 'outbound')]",
    },
)

demo_action(
    "demo_payment_form",
    {
        "name": "Pago - %s" % vendors[0][0].name,
        "res_model": "account.payment",
        "view_mode": "form",
        "res_id": payments[0].id,
    },
)

filled_wizard = env["l10n_do.account.batch.payment"].create(
    {"journal_id": journal.id, "payment_ids": [(6, 0, payments.ids)]}
)

demo_action(
    "demo_wizard_filled",
    {
        "name": "Generar Archivo de Pagos",
        "res_model": "l10n_do.account.batch.payment",
        "view_mode": "form",
        "view_id": wizard_view.id,
        "res_id": filled_wizard.id,
        "target": "new",
    },
)

env.cr.commit()
print(
    "SEED OK: %s pagos, %s cuentas bancarias de suplidores"
    % (len(payments), Bank.search_count([("partner_id.supplier_rank", ">", 0)]))
)
