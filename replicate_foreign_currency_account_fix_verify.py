import json
import logging
from datetime import date

from odoo.exceptions import UserError

logging.disable(logging.WARNING)

snap = json.load(open("/tmp/fx_snapshot.json"))
acc = {code: env["account.account"].browse(aid) for code, aid in snap["accounts"].items()}
usd = env.ref("base.USD")
dop = env.company.currency_id
results = []


def check(name, ok, detail=""):
    results.append(ok)
    print(("PASS" if ok else "FAIL"), name, detail)


expected = {
    "110199001": "USD", "110199002": "USD", "110199003": "EUR", "220399001": "USD",
    "110399001": "USD", "110199005": "USD", "220399002": False, "110199004": False,
}
for code, cur in expected.items():
    got = acc[code].currency_id.name or False
    check(f"account {code} currency", got == cur, f"expected={cur} got={got}")

diffs = []
for aid, bal in snap["balances"].items():
    lines = env["account.move.line"].search([("account_id", "=", int(aid))])
    now = round(sum(lines.mapped("balance")), 2)
    if now != bal:
        diffs.append((aid, bal, now))
check("company-currency balances unchanged (all accounts)", not diffs, str(diffs))

fixed = env["account.account"].browse([a.id for c, a in acc.items() if expected[c]])
fixed._check_journal_consistency()
check("account._check_journal_consistency", True)

lines = env["account.move.line"].search([("account_id", "in", fixed.ids)])
bad = lines.filtered(lambda l: l.currency_id not in (l.account_id.currency_id, l.company_currency_id))
check("no line with a currency different from its account", not bad, str(bad.ids))
lines.filtered(lambda l: l.parent_state == "posted")._check_constrains_account_id_journal_id()
check("_check_constrains_account_id_journal_id on posted lines", True)

stale = lines.filtered(lambda l: (l.account_id.reconcile or l.account_id.account_type in ("asset_cash", "liability_credit_card"))
                       and not l.matched_debit_ids and not l.matched_credit_ids
                       and l.currency_id.compare_amounts(l.amount_residual_currency, l.amount_currency))
check("amount_residual_currency = amount_currency on unreconciled lines", not stale, str(stale.ids))

bill = env["account.move"].browse(snap["bill"])
check("bill still paid", bill.payment_state == snap["bill_state"], bill.payment_state)

caja = env["account.journal"].browse(snap["journals"]["caja"])
misc_move = env["account.move.line"].search([("account_id", "=", acc["110199002"].id), ("move_id.ref", "=", "BALANCE INICIAL"), ("parent_state", "=", "posted")], limit=1).move_id
try:
    misc_move.button_draft()
    misc_move.action_post()
    check("reset to draft + repost converted opening entry", misc_move.state == "posted")
except Exception as e:
    check("reset to draft + repost converted opening entry", False, repr(e))

draft = env["account.move.line"].search([("account_id", "=", acc["110199002"].id), ("parent_state", "=", "draft")], limit=1).move_id
try:
    draft.action_post()
    check("post converted draft entry", draft.state == "posted")
except Exception as e:
    check("post converted draft entry", False, repr(e))

partner = env["res.partner"].search([("name", "=", "Suplidor Local")], limit=1)
payment = env["account.payment"].create({"payment_type": "outbound", "partner_type": "supplier", "partner_id": partner.id,
                                         "amount": 100, "currency_id": usd.id, "journal_id": caja.id, "date": date(2026, 3, 1)})
payment.action_post()
check("new USD payment on USD cash journal posts", payment.state in ("in_process", "paid"), payment.state)

try:
    with env.cr.savepoint():
        p = env["account.payment"].create({"payment_type": "outbound", "partner_type": "supplier", "partner_id": partner.id,
                                           "amount": 100, "currency_id": dop.id, "journal_id": caja.id, "date": date(2026, 3, 1)})
        p.action_post()
    check("DOP payment on USD journal now rejected (expected)", False, "it was accepted")
except UserError as e:
    check("DOP payment on USD journal now rejected (expected)", True, str(e)[:80])

print("\n=== Partner ledger-like USD balance per fixed account ===")
for a in fixed:
    ls = env["account.move.line"].search([("account_id", "=", a.id), ("parent_state", "=", "posted")])
    print(f"  {a.code} {a.currency_id.name}: balance={sum(ls.mapped('balance')):,.2f} {dop.name}  amount_currency={sum(ls.mapped('amount_currency')):,.2f} {a.currency_id.name}")

env.cr.rollback()
print("\nALL PASS" if all(results) else "\nSOME CHECKS FAILED")
