import json
import logging
from datetime import date

logging.disable(logging.WARNING)

company = env.company
company.country_id = env.ref("base.do")
env["account.chart.template"].try_loading("do", company, install_demo=False)
dop = company.currency_id
usd = env.ref("base.USD")
eur = env.ref("base.EUR")
(usd | eur).active = True
assert dop.name == "DOP", dop.name

env["res.currency.rate"].search([("currency_id", "in", (usd | eur).ids)]).unlink()
for d, r_usd, r_eur in [("2025-10-01", 0.0160, 0.0140), ("2025-12-01", 0.0157, 0.0137), ("2026-02-01", 0.0162, 0.0141)]:
    env["res.currency.rate"].create({"currency_id": usd.id, "name": d, "rate": r_usd, "company_id": company.id})
    env["res.currency.rate"].create({"currency_id": eur.id, "name": d, "rate": r_eur, "company_id": company.id})

misc = env["account.journal"].search([("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
partner = env["res.partner"].create({"name": "Suplidor Local"})
customer = env["res.partner"].create({"name": "Cliente USD"})
expense = env["account.account"].search([("account_type", "=", "expense")], limit=1)
equity = env["account.account"].search([("account_type", "=", "equity")], limit=1)


def account(code, name, account_type, reconcile=False):
    return env["account.account"].create({"code": code, "name": name, "account_type": account_type, "reconcile": reconcile})


def journal(code, name, jtype, currency, acc):
    j = env["account.journal"].create({"code": code, "name": name, "type": jtype, "currency_id": currency.id, "default_account_id": acc.id})
    (j.inbound_payment_method_line_ids | j.outbound_payment_method_line_ids).payment_account_id = acc
    return j


def entry(d, lines, post=True):
    move = env["account.move"].create({
        "move_type": "entry", "journal_id": misc.id, "date": d, "ref": "BALANCE INICIAL",
        "line_ids": [(0, 0, {"account_id": a.id, "currency_id": c.id, "amount_currency": amc, "balance": bal, "name": n})
                     for a, c, amc, bal, n in lines],
    })
    if post:
        move.action_post()
    return move


def pay(j, ptype, cur, amount, d, p=partner):
    payment = env["account.payment"].create({
        "payment_type": ptype, "partner_type": "supplier" if ptype == "outbound" else "customer",
        "partner_id": p.id, "amount": amount, "currency_id": cur.id, "journal_id": j.id, "date": d,
    })
    payment.action_post()
    return payment


acc_bank_usd = account("110199001", "Banco USD limpio", "asset_cash")
acc_caja = account("110199002", "Caja Estructura USD", "asset_cash")
acc_bank_eur = account("110199003", "Banco EUR limpio", "asset_cash")
acc_ant_cli = account("220399001", "Anticipos de Clientes USD", "liability_current", reconcile=True)
acc_ant_sup = account("110399001", "Anticipos Suplidores USD", "asset_current")
acc_recon = account("220399002", "Anticipos conciliados USD", "liability_current", reconcile=True)
acc_shared = account("110199004", "Cuenta compartida USD/EUR", "asset_cash")
acc_empty = account("110199005", "Banco USD sin movimientos", "asset_cash")

j_bank_usd = journal("BUSD", "Banco USD limpio", "bank", usd, acc_bank_usd)
j_caja = journal("CJDLR", "Caja Estructura", "cash", usd, acc_caja)
j_bank_eur = journal("BEUR", "Banco EUR limpio", "bank", eur, acc_bank_eur)
j_ant_cli = journal("CNTUS", "Anticipos de Clientes USD", "bank", usd, acc_ant_cli)
j_ant_sup = journal("ANTUS", "Anticipos Suplidores USD", "bank", usd, acc_ant_sup)
j_recon = journal("RCUSD", "Anticipos conciliados USD", "bank", usd, acc_recon)
j_shared_usd = journal("SHUSD", "Compartida USD", "bank", usd, acc_shared)
j_shared_eur = journal("SHEUR", "Compartida EUR", "bank", eur, acc_shared)
j_empty = journal("EMUSD", "Banco USD sin movimientos", "bank", usd, acc_empty)

pay(j_bank_usd, "inbound", usd, 1000, date(2025, 11, 5), customer)
pay(j_bank_usd, "outbound", usd, 250, date(2026, 2, 10))
pay(j_bank_eur, "inbound", eur, 500, date(2025, 11, 5), customer)

pay(j_caja, "inbound", usd, 5000, date(2025, 11, 1), customer)
pay(j_caja, "outbound", dop, 21534.41, date(2025, 11, 4))
pay(j_caja, "outbound", dop, 51032.10, date(2025, 12, 15))
pay(j_caja, "inbound", dop, 44075.71, date(2026, 2, 16), customer)
cancelled = pay(j_caja, "outbound", dop, 59856.09, date(2026, 1, 31))
cancelled.action_draft()
cancelled.action_cancel()

bill = env["account.move"].create({
    "move_type": "in_invoice", "partner_id": partner.id, "invoice_date": date(2025, 12, 1), "date": date(2025, 12, 1),
    "currency_id": dop.id,
    "invoice_line_ids": [(0, 0, {"name": "Materiales", "quantity": 1, "price_unit": 12343.98, "account_id": expense.id, "tax_ids": [(6, 0, [])]})],
})
bill.action_post()
env["account.payment.register"].with_context(active_model="account.move", active_ids=bill.ids).create({
    "journal_id": j_caja.id, "currency_id": dop.id, "payment_date": date(2025, 12, 2),
})._create_payments()

entry(date(2026, 3, 31), [
    (acc_caja, dop, -68780.48, -68780.48, "Saldo inicial caja"),
    (equity, dop, 68780.48, 68780.48, "Saldo inicial caja"),
])
cancelled_entry = entry(date(2026, 1, 31), [
    (acc_caja, dop, -36653.65, -36653.65, "Pago cancelado RD$"),
    (expense, dop, 36653.65, 36653.65, "Pago cancelado RD$"),
])
cancelled_entry.button_draft()
cancelled_entry.button_cancel()
entry(date(2026, 3, 31), [
    (acc_caja, dop, 638.39, 638.39, "Borrador"),
    (equity, dop, -638.39, -638.39, "Borrador"),
], post=False)

pay(j_ant_cli, "inbound", usd, 3000, date(2025, 12, 5), customer)
entry(date(2026, 2, 28), [
    (acc_ant_cli, dop, 78075.74, 78075.74, "Ajustes noviembre"),
    (equity, dop, -78075.74, -78075.74, "Ajustes noviembre"),
])

pay(j_ant_sup, "outbound", usd, 2000, date(2025, 11, 20))
entry(date(2026, 3, 31), [
    (acc_ant_sup, eur, 190.05, 13166.79, "Anticipo EUR en cuenta USD"),
    (equity, dop, -13166.79, -13166.79, "Anticipo EUR en cuenta USD"),
])

entry(date(2025, 12, 10), [
    (acc_recon, usd, -100.0, -6369.43, "Anticipo USD"),
    (equity, dop, 6369.43, 6369.43, "Anticipo USD"),
])
entry(date(2025, 12, 20), [
    (acc_recon, dop, 6369.43, 6369.43, "Aplicacion en DOP"),
    (equity, dop, -6369.43, -6369.43, "Aplicacion en DOP"),
])
env["account.move.line"].search([("account_id", "=", acc_recon.id), ("parent_state", "=", "posted")]).reconcile()

pay(j_shared_usd, "inbound", usd, 300, date(2025, 11, 5), customer)
pay(j_shared_eur, "inbound", eur, 200, date(2025, 11, 5), customer)

env.cr.commit()

snapshot = {}
for acc in env["account.account"].search([]):
    lines = env["account.move.line"].search([("account_id", "=", acc.id)])
    if lines:
        snapshot[acc.id] = round(sum(lines.mapped("balance")), 2)
open("/tmp/fx_snapshot.json", "w").write(json.dumps({
    "balances": snapshot, "bill": bill.id, "bill_state": bill.payment_state,
    "accounts": {a.code: a.id for a in [acc_bank_usd, acc_caja, acc_bank_eur, acc_ant_cli, acc_ant_sup, acc_recon, acc_shared, acc_empty]},
    "journals": {"caja": j_caja.id},
}))
print("seeded; bill", bill.name, bill.payment_state)
