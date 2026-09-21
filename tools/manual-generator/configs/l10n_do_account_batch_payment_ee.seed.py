# Seed para el manual de l10n_do_account_batch_payment_ee — "Pagos por lotes".
#
# Desde una base LIMPIA arma el escenario enterprise de pagos a suplidores:
#
#   * Compañía "Empresa Dominicana SRL" (RD, es_DO) con catálogo de cuentas RD
#   * Diario de banco "Banco Popular DOP" con su propia cuenta bancaria (BPD)
#   * Tres suplidores con cuenta bancaria en BPD, BHD y BanReservas
#   * Tres facturas de proveedor publicadas y pagadas -> tres pagos "Conciliado"
#   * Un lote de pagos (account.batch.payment) en borrador con los tres dentro
#   * Un lote de tipo "Transferencia interna", el tipo que agrega este módulo
#   * Acciones demo para que Playwright capture cada pantalla
#
# Se ejecuta dentro de `odoo shell` (global `env`). Termina con commit.
from datetime import date, timedelta

MODULE = "l10n_do_account_batch_payment_ee"

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
admin = env.ref("base.user_admin")
admin.group_ids |= env.ref("account.group_validate_bank_account")
TrustedBank = Bank.with_user(admin)

VENDORS = [
    # (nombre, RNC, teléfono, email, cuenta, banco, tipo de cuenta, monto)
    ("Suplidores del Caribe SRL", "131000001", "809-555-1234", "pagos@caribe.do", "774555001", "bpd", "cheque", 18500.00),
    ("José Almonte & Asociados", "131000002", "(829) 777-4488", "jose@almonte.do", "402777002", "bhd", "savings", 7250.50),
    ("Ferretería Industrial SRL", "131000003", "809-333-9900", "ventas@ferrind.do", "960333003", "brd", "cheque", 42100.75),
    # El cuarto queda deliberadamente fuera del lote: es el que aparece como
    # candidato al abrir "Agregar una línea".
    ("Transporte Rápido SRL", "131000004", "809-222-7788", "info@transrapido.do", "774222004", "bpd", "cheque", 9800.00),
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
        account._onchange_l10n_do_bank()
    vendors.append((partner, account, amount))

# ── 4. Facturas de proveedor pagadas -> pagos en estado "Conciliado" ──────────
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

# ── 5. Lotes de pago ─────────────────────────────────────────────────────────
Batch = env["account.batch.payment"]
method = payments[:1].payment_method_line_id.payment_method_id

batch = Batch.create(
    {
        "journal_id": journal.id,
        "batch_type": "outbound",
        "payment_method_id": method.id,
        "date": today,
        # Los tres primeros pagos; el cuarto queda suelto a propósito.
        "payment_ids": [(6, 0, payments[:3].ids)],
    }
)

# El tipo de lote que agrega este módulo. Va sin pagos: lo que documenta es que
# el tipo existe y que la acción de salida lo lista.
transfer_batch = Batch.create(
    {
        "journal_id": journal.id,
        "batch_type": "transfer",
        "payment_method_id": method.id,
        "date": today,
    }
)

demo_payments_out_of_batch = payments[3:]

print(
    "LOTES:",
    [(b.name or "(sin número)", b.batch_type, b.state, b.file_generation_enabled) for b in (batch, transfer_batch)],
)

# ── 6. Acciones demo para las capturas ────────────────────────────────────────
Action = env["ir.actions.act_window"]
Data = env["ir.model.data"]


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


demo_action(
    "demo_batch_list",
    {
        "name": "Pagos por lotes",
        "res_model": "account.batch.payment",
        "view_mode": "list,form",
        "domain": "[('batch_type', 'in', ('outbound', 'transfer'))]",
    },
)

demo_action(
    "demo_batch_form",
    {
        "name": "Lote de pagos",
        "res_model": "account.batch.payment",
        "view_mode": "form",
        "res_id": batch.id,
    },
)

demo_action(
    "demo_transfer_batch_form",
    {
        "name": "Lote de transferencia interna",
        "res_model": "account.batch.payment",
        "view_mode": "form",
        "res_id": transfer_batch.id,
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

wizard_view = env.ref("l10n_do_account_batch_payment_base.l10n_do_account_batch_payment_wizard_form")
demo_action(
    "demo_base_wizard",
    {
        "name": "Generar Archivo de Pagos",
        "res_model": "l10n_do.account.batch.payment",
        "view_mode": "form",
        "view_id": wizard_view.id,
        "target": "new",
        "context": "{'default_journal_id': %d}" % journal.id,
    },
)

env.cr.commit()
print(
    "SEED OK: %s pagos (%s fuera del lote), %s lotes"
    % (len(payments), len(demo_payments_out_of_batch), Batch.search_count([]))
)
