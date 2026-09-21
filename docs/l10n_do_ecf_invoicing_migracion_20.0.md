# l10n_do_ecf_invoicing — port to the 20.0 line (master)

Reference for what changed when this module moved from 19.0 to the 20.0
development line, and why. The module's behaviour is unchanged: it issues the
same ten e-CF types, signs them the same way, and talks to the same endpoints.
Everything below is the module adapting to Odoo, not changing what it does.

Companion read: `.claude/skills/odoo-module-migration/references/master-breaks.md`,
which catalogues the platform breaks in a form other ports can reuse.

---

## 1. Why the module stays

Odoo now ships **`l10n_do_edi`** (enterprise, OEEL-1, `master` only — it does
not exist on 19.0 or any saas-19.x branch). It is a real e-CF implementation,
so the overlap is worth being precise about.

| | `l10n_do_edi` (Odoo) | `l10n_do_ecf_invoicing` (this module) |
|---|---|---|
| Document types | 31, 32, 33, 34 | 31, 32, 33, 34, 41, 43, 44, 45, 46, 47 |
| Signing | delegated to InFile (PAC) | local, with the company's own `.p12` |
| Endpoints | `fe-webservice[-test].infile.com.do` | Indexa / Fixcal gateways, per version and environment |
| RFCE (consumer invoice < RD$250k) | not implemented | generated, signed and validated |
| XSD validation | none | against the DGII schemas in `xsd/` |
| Status polling | one daily cron, InFile `solicitud_id` | by trackId and by security code, three crons |
| On DGII rejection | sets a state | cancels the invoice and unreconciles its payments |
| Withholdings in the XML | via a tax-level indicator field | computed, including withholding-on-payment |

Nothing this module does at its core exists in core or enterprise, so the
verdict is **port**, not trim and not drop.

### `l10n_do_edi` is not forced on anyone

Checked explicitly, because the two modules would collide if both were
installed (two e-CF emitters over the same invoices):

- its manifest declares no `auto_install`, so it never enters the
  auto-install branch in `ir_module.py::button_install()`;
- no module anywhere in `odoo/`, `enterprise/` or `odoo-pro/` names it in
  `depends` — the only manifest that mentions it is its own;
- `chart_template._load()` installs only the module that provides the
  template, which is `l10n_do`;
- no `module_l10n_do_edi` settings field and no `button_immediate_install`
  call targets it.

It is only ever installed by hand.

### What *does* arrive unavoidably

`l10n_do` itself changed. On 19.0 it was a chart of accounts and taxes; on
master it also depends on `l10n_latam_invoice_document` and ships
`l10n_do.ecf_31..34` (prefixes E31..E34), `l10n_do_purchase_type`,
`l10n_do_payment_type`, `_l10n_do_get_ncf()`, partner RNC helpers and an
override of `_get_l10n_latam_documents_domain`. Those e-CF document types
collide by prefix with this repo's own `l10n_do_accounting.ecf_*`.

`l10n_do_accounting` handles that collision (its domain now matches
`l10n_do_ncf_type` strictly instead of letting core's typeless records
through). This module inherits the fix — and one break out of it, see §2.5.

---

## 2. Platform breaks resolved

### 2.1 `tax_group_itbis` was deleted

The DO chart used to hang all 19 ITBIS taxes off a single `tax_group_itbis`.
On master that group **does not exist**. The taxes split by rate, and the ITBIS
withholdings left ITBIS entirely:

| tax | 19.0 group | master group |
|---|---|---|
| `tax_18_*`, `tax_18_of_10` (1.8) | `tax_group_itbis` | `tax_group_itbis_18` |
| `tax_16_*` | `tax_group_itbis` | `tax_group_itbis_16` |
| `tax_0_purch`, `tax_0_sale` | `tax_group_itbis` | `tax_group_itbis_0` |
| `tax_0_sale_itbis` | — (new) | `tax_group_itbis_tax_0` |
| `ret_100_*`, `ret_30_*`, `ret_75_*` | `tax_group_itbis` | **`tax_group_ret`** |
| `ret_10_*`, `ret_2_*` | — (new) | `tax_group_isr` |

All seven `env.ref(f"account.{id}_tax_group_itbis")` lookups are gone. They now
go through `l10n_do_accounting`'s `_l10n_do_tax_groups()` helper, so both
modules resolve tax groups identically, and a group the chart does not define
is skipped instead of raising.

**One group became three sets**, because one name no longer answers two
different questions:

- **rate groups** — `_18`, `_16`, `_0`, `_tax_0`, `_00015`. Used wherever the
  answer feeds arithmetic: `IndicadorFacturacion`, `IndicadorMontoGravado`, the
  partial-ITBIS item split, the ITBIS base of a retention.
- **withholding groups** — the rate groups *plus* `tax_group_ret` and the
  `tax_group_itbis_retencion_*` pair. The union is deliberate: 19.0 recognised
  an ITBIS retention by the umbrella alone, and a company may still book one
  under a rate group. It is safe only because this set is never matched against
  anything but a tax already known to be negative — `tax_group_ret` also holds
  *positive* 18% taxes, which must never be counted as an ITBIS rate.
- **ISR groups** — `tax_group_isr`, unchanged.

`_l10n_do_withholding_groups()` returns the three; `_l10n_do_line_itbis()` and
`_l10n_do_withholding_amount()` take the ones they need.

### 2.2 `is_withholding_tax_on_payment` → `is_withholding_tax`

`account.tax.is_withholding_tax_on_payment` (from core
`l10n_account_withholding_tax`) was renamed `is_withholding_tax`. Same
semantics: a tax withheld at payment, not posted on the invoice.

**This one was silent, and it was the worst of them.** The module gates the
whole withholding-on-payment path on `"..." in self.env["account.tax"]._fields`.
On master the gate simply closed, and the retentions vanished from

- `<Totales>` → `TotalITBISRetenido`, `TotalISRRetencion`
- each `<Item>` → `MontoITBISRetenido`, `MontoISRRetenido`

on every e-CF **41** and **47**. Nothing raised. The three tests covering it
(`test_017`, `test_018`, `test_019`) were skipping on the same stale field
name, which is why the suite stayed green while the feature was off. They run
now.

### 2.3 `_get_rates()` returns a tuple

`res.currency._get_rates(company, date)` returned `{currency_id: rate}` on
19.0. On master it returns `{currency_id: (rate, rate_date)}`.

`_get_l10n_do_amounts()` divided by that value directly, so any
foreign-currency invoice carrying a withholding-on-payment tax raised:

```
TypeError: unsupported operand type(s) for /: 'int' and 'tuple'
```

Unwrapped once, in `_l10n_do_date_currency_rate()`, which both call sites use.
Each site keeps the preference it already had for `invoice_currency_rate`, so
the rate in the XML still matches the accounting entry and a credit note still
inherits the rate of the invoice it reverses.

Separately, the lookup moved from `name <= date` to `name < date` — a rate now
applies the day *after* its date. That is core behaviour for every
localization. This module reads `invoice_currency_rate`, which core computes,
so it follows along automatically; no code change, but worth knowing when
comparing an e-CF against a 19.0 one.

### 2.4 `_display_address(without_company=...)` → `without_name=...`

`res.partner._display_address()` renamed the keyword, and now strips each line
and collapses runs of spaces before returning. The call in `_get_Emisor_data()`
is renamed; the flattening `.replace()` chain stays, for a multi-line address.

`DireccionEmisor` changes cosmetically as a result: `"dummy address,    Dominican
Republic"` becomes `"dummy address Dominican Republic"`. The comma and the four
spaces were an artifact of 19.0 emitting a blank address line, which core now
drops. This is core cleaning up its own output, not a regression — the module
was shipping that whitespace to DGII before.

### 2.5 `_get_l10n_do_enabled_ecf_domain()` sliced a domain by position

This is the one break caused directly by core `l10n_do` shipping its own e-CF
types, through a chain worth spelling out:

1. Core `l10n_do` starts shipping `l10n_do.ecf_31..34`, which have no
   `l10n_do_ncf_type`.
2. To keep them out of the dropdown, `l10n_do_accounting` drops the
   `'|', ('l10n_do_ncf_type', '=', False)` branch from
   `_get_l10n_latam_documents_domain()`.
3. That domain goes from **6 elements to 4**.
4. This module did `domain[:5]` to strip the trailing `code` condition. On a
   4-element domain that slice strips nothing.
5. With `code` still restricted to `E`, disabling e-CF issuing for a document
   type matched no document type at all — so the invoice got **no document
   type**, instead of falling back to its paper NCF (B02).

Now the condition is matched by field name through master's
`Domain.map_conditions()`, replacing the `code` condition with `Domain.TRUE`.
The domain's shape stops mattering.

### 2.6 `account.move.line.name` no longer holds the product name

Core commit `c5037bbe078`, *[IMP] sale,account,purchase,*: remove product name
from description*, split one field into two:

| | 19.0 | master |
|---|---|---|
| `name` | product `display_name` + `description_sale`/`_purchase` | the description **alone**, empty when nobody typed one |
| `label` | — | what `name` used to be: `display_name`, or `display_name + "\n" + name` |

So `line.name` is empty for an ordinary product line, and the replacement for
the old value is the new `label`.

Three sites read it, and all three go through
`AccountMoveLine._l10n_do_line_label()` now, which prefers `label` and falls
back to `name` on a build from before the split:

- `_get_Item_list()` -> `DescripcionItem`, which was going out **empty**;
- `_get_Discount_list()` -> `DescripcionDescuentooRecargo`, which would also
  have raised `TypeError` on `len(None)` for a line with no description;
- `_l10n_do_edi_check_configuration()`, whose "All invoice lines require a
  description" check would otherwise fire on **every** product line and block
  posting any e-CF at all.

Caught by CI rather than locally: the dev image
(`dev_env_odoo_pro-20-odoo:latest`, `19.5a1-20260901`) ships an odoo older than
its own version string suggests and has none of this, while CI builds on
`ghcr.io/indexa-git/odoo:master` (`19.5a1-20260914`). Reproduced locally with a
throwaway addon that re-creates the split, which failed exactly the two tests
CI failed and passes with the fix.

### 2.7 `self._context` → `self.env.context`

Two call sites in `button_cancel()` / `button_draft()`.

---

## 3. Manifest

| | before | after |
|---|---|---|
| `version` | `20.0.1.0.9` | `19.5.1.1.0` |
| `installable` | `False` | `True` |
| `external_dependencies` | `["signxml"]` | `["dict2xml", "signxml"]` |

The series prefix must be exactly `19.5.` — `check_version()` is a string
prefix compare and silently forces `installable=False` otherwise. The module
segment takes a **minor** bump: the port changes no data model, no security
record and no xmlid.

`dict2xml` has always been imported by `models/dgii_tools.py` and was only ever
declared in `requirements.txt`. Data files are reordered data-then-views.

### No migration script

Verified rather than assumed: a database stamped back to `19.0.1.0.9` and run
through `-u l10n_do_ecf_invoicing` upgrades clean to `19.5.1.1.0`. There is
nothing to migrate — the module ships no ACLs (so no `ir.model.access` →
`ir.access` xmlid conflict), renames no field and moves no xmlid between
models. The frozen `upgrades/17.0.*` and `upgrades/19.0.1.0.4` folders are left
exactly as they are.

---

## 4. What was verified

- **Install** on a fresh master database; `state = installed`,
  `latest_version = 19.5.1.1.0`.
- **28 of 28 tests**, with `l10n_account_withholding_tax` installed so nothing
  skips. The suite started at 5 failures and 3 silent skips.
- **Views**: all 5 the module ships and all 4 it inherits render through
  `get_view()`, plus `account.view_move_form` for `out_invoice`, `out_refund`
  and `in_invoice` — as superuser and as a plain billing user. The four data
  records (server action, three crons) resolve.
- **Upgrade** from a simulated 19.0-era database, with and without the
  migration folder that turned out not to be needed.
- **`_get_rates` unwrap** proven against real data: raw
  `(0.02, datetime.date(2026, 9, 11))`, helper returns `0.02`.
- **pre-commit**: every hook passes over the whole module.

---

## 5. Known gaps and follow-ups

Not defects introduced by the port; things a reader should know about.

1. **Ley 30-26 taxes — pending functional decision.** Core now ships the DO
   chart with different rates (ISR personal and rent 15% → 10%, transfers
   3% → 2%), several taxes removed (`tax_8_purch`, `tax_9_purch`,
   `ret_15_income_*`, `ret_3_income_*`) and fiscal positions renamed. This
   repo's `l10n_do_accounting/upgrades/19.0.1.3.0` and `19.0.1.4.0` create
   overlapping taxes. Whoever resolves that has to decide which group the
   recreated taxes land in — §2.1's rate/withholding sets classify by group,
   so a tax recreated into a group not on those lists is invisible to the e-CF
   totals. Flagged in PR #1168 as well; it is one decision, not two.

2. **Core's `l10n_do.ecf_31..34` records stay active.** `l10n_do_accounting`
   keeps them out of the document-type dropdown, but the records exist, with
   the same `doc_code_prefix` (E31..E34) as ours. Any code resolving a document
   type by prefix or by `code` will see two. This module branches on
   `doc_code_prefix` throughout `_l10n_do_edi_check_configuration()` — it reads
   the prefix off the invoice's own document type, so it is not affected, but
   new code should not `search()` by prefix.

3. **`models/account_journal.py` is a compatibility shim for `account_edi`.**
   Its `hasattr(self, "_compute_compatible_edi_ids")` guard is always true (the
   method is defined right there), so it relies on the field not existing when
   `account_edi` is uninstalled. `account_edi` still exists on master and the
   behaviour is unchanged, so this was left alone.

4. **`_compute_payment_state()` raises a `ValidationError`.** Raising from a
   compute makes the record unreadable from any context that touches
   `payment_state` — including `account.payment.register.default_get()`, which
   reads it to check for blocked invoices. That is intended behaviour here (an
   ECF company with no certificate should fail loudly on payment), and it is
   unchanged, but the module's own tests now pass `l10n_do_active_test=True` to
   the whole payment wizard rather than only to `action_create_payments()`.

5. **Patterns from `l10n_do_edi` deliberately not adopted**, because each would
   change behaviour:
   - an explicit `l10n_do_edi_invoicing_indicator` field on `account.tax`
     instead of inferring the indicator from tax groups. Cleaner, but the field
     lives in the enterprise module and adopting it would mean a data migration
     plus a per-tax configuration step.
   - surfacing configuration problems as non-blocking form warnings
     (`l10n_do_edi_warnings`) instead of raising at post time.
   - hooking into `account.move.send` as an extra EDI rather than signing in
     `_post()`.

   Worth revisiting as deliberate product decisions; out of scope for a port.
