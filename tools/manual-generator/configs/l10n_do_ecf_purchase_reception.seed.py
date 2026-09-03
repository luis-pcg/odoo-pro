# Seed for the functional manual of l10n_do_ecf_purchase_reception (Odoo 19).
#
# Self-contained on purpose: `generate-manual.sh` hands this script a database
# that only has the module installed, so everything the manual shows is built
# here -- company, chart of accounts, products, learned links, the bill that was
# keyed in by hand -- and then the cron is run with the reception API **mocked
# over the module's own test fixtures** (`tests/fixtures.py`). Two consequences
# worth stating:
#
#   * no network and no sandbox account: the manual regenerates the same way on
#     any machine, and it cannot go stale because somebody clicked a button in a
#     shared database,
#   * what the screenshots show is the same document the unit tests assert on.
#
# The order of the payloads below is the order the documents are created in, and
# the manual addresses them by database id, so **do not reorder it** without
# fixing `configs/l10n_do_ecf_purchase_reception.json`:
#
#   id 1  E310000000500  error       totals do not reconcile
#   id 2  E340000000007  duplicate   already keyed in by hand
#   id 3  E310000000202  to_map      one code for the whole invoice, 2 lines to link
#   id 4  E310000000200  done        ITBIS already inside the amounts, billed automatically
#   id 5  E310000000034  ready       linked without learning, with a PO -> widget
#   id 6  E310000000201  to_map      carries ISC outside every line
#   id 7  E310000000035  done        second invoice, resolved with no clicks
#   id 8  E310000000099  to_map      foreign currency
#   id 9  E310000000101  ready       the product is taxed at 16%, the e-CF declares 18%
#   id 10 E340000000203  to_map      indicators DGII does not document
#
# Executed inside `odoo shell`; the global `env` is available. Ends with commit.

from odoo import fields

from odoo.addons.l10n_do_ecf_purchase_reception.lib import reception_service as svc
from odoo.addons.l10n_do_ecf_purchase_reception.tests import fixtures

DO = env.ref("base.do")
BUYER_RNC = "131793916"
VENDOR_RNC = "131880681"


def title(text):
    print("\n" + "=" * 74)
    print("  " + text)
    print("=" * 74)


def show(label, value):
    print("   %-32s %s" % (label + ":", value))


# =============================================================================
title("Dominican company, chart of accounts and fiscal purchase journal")
# =============================================================================
company = env.ref("base.main_company")
company.write(
    {
        "name": "INDEXA SRL",
        "country_id": DO.id,
        "vat": BUYER_RNC,
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
    }
)
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
    env.cr.commit()

company.l10n_do_ecf_issuer = True
company.l10n_do_dgii_start_date = fields.Date.to_date("2020-01-01")

purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
)
if not purchase_journal.l10n_latam_use_documents:
    purchase_journal.l10n_latam_use_documents = True
else:
    purchase_journal._l10n_do_create_document_types()

company.write(
    {
        "l10n_do_ecf_reception_enabled": True,
        "l10n_do_ecf_api_version": "v3",
        "l10n_do_ecf_service_env": "TesteCF",
        # The mock answers whatever day the cron asks for, so one day is enough.
        "l10n_do_ecf_reception_lookback_days": 0,
        "l10n_do_ecf_reception_xml_limit": 50,
        "l10n_do_ecf_acecf_deadline_days": 30,
        "l10n_do_ecf_purchase_journal_id": purchase_journal.id,
    }
)
env.cr.commit()

show("Company / RNC", "%s / %s" % (company.name, company.vat))
show("Chart of accounts", company.chart_template)
show("Fiscal purchase journal", purchase_journal.display_name)

# =============================================================================
title("Operator: groups, password and Dominican Spanish")
# =============================================================================
admin = env.ref("base.user_admin")
admin.group_ids |= (
    env.ref("purchase.group_purchase_manager")
    | env.ref("account.group_account_manager")
    | env.ref("stock.group_stock_user")
    | env.ref("uom.group_uom")
    # The Technical page of a received e-CF is `groups="base.group_no_one"`, and that
    # group only takes effect on a session in debug mode: the manual needs both, the
    # membership here and `?debug=1` on the flow that captures the page.
    | env.ref("base.group_no_one")
)
admin.password = "admin"

# The module's strings are English and `i18n/es_DO.po` translates them, which is
# what a real Dominican instance reads: the screenshots have to come out in the
# language the operator uses, not in the source strings.
env["res.lang"]._activate_lang("es_DO")
# Every installed module, not just this one: a half-translated screenshot -- our
# menu in Spanish under an English navbar -- reads as a packaging bug rather than
# as the instance the operator actually uses.
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin.lang = "es_DO"
env.cr.commit()
show("Interface language", admin.lang)

# From here on the seeding itself runs in es_DO. It is not cosmetic: the chatter
# messages and the tracked state changes below are written *now*, in whatever
# language this shell is in, and the manual captures that chatter -- an English
# "Imported -> To link" under a Spanish form reads as a missing translation.
env = env(context=dict(env.context, lang="es_DO"))

# =============================================================================
title("Products, vendor and pre-learned links")
# =============================================================================
Product = env["product.product"]


def purchase_tax(rate):
    """The company's ordinary purchase tax at that rate, as the chart ships it."""
    return env["account.tax"].search(
        [
            ("company_id", "=", company.id),
            ("type_tax_use", "=", "purchase"),
            ("amount_type", "=", "percent"),
            ("amount", "=", rate),
            ("price_include", "=", False),
        ],
        limit=1,
    )


def product(name, code, kind="consu", taxes=None):
    existing = Product.search([("default_code", "=", code)], limit=1)
    if existing:
        return existing
    vals = {"name": name, "default_code": code, "type": kind, "purchase_ok": True}
    if kind == "service":
        # A service billed "on received quantities" never becomes billable: it
        # produces no stock move, so the purchase chain would drop the line.
        vals["purchase_method"] = "purchase"
    if taxes is not None:
        vals["supplier_taxes_id"] = [(6, 0, taxes.ids)]
    return Product.create(vals)


# The tax lives on the product: that is where the accounting department keeps it
# and it is the first thing the importer asks. Every product here is set up at
# the rate its vendor really invoices it at -- 18% by default, exempt for the
# cable, 16% for the biscuits -- except the last one, which is set up wrong on
# purpose so the manual can show the module reporting the disagreement.
p_meat = product("Carne de res paquete 2lb", "CARNE-2LB")
p_install = product("Instalación de red", "INSTAL-RED", kind="service")
p_cable = product("Cable UTP categoría 6", "CABLE-UTP6", taxes=purchase_tax(0))
p_pencils = product("Lápices HB caja", "LAPICES-HB")
p_cookies = product("Galletas surtidas", "GALLETAS-SUR", taxes=purchase_tax(16))
p_gouda = product("Queso Gouda importado", "QUESO-GOUDA")
p_consulting = product("Servicios profesionales", "SERV-PROF", kind="service", taxes=purchase_tax(16))

vendor = env["res.partner"].search([("vat", "=", VENDOR_RNC)], limit=1)
if not vendor:
    vendor = env["res.partner"].create(
        {
            "name": "DOCUMENTOS ELECTRONICOS DE 02",
            "vat": VENDOR_RNC,
            "company_type": "company",
            "supplier_rank": 1,
            "country_id": DO.id,
            "l10n_do_dgii_tax_payer_type": "taxpayer",
        }
    )
# Switched on *before* the import, which is what the switch is for: the
# documents this vendor sends whose lines all resolve by themselves come out of
# the cron as draft bills, with nobody clicking anything.
vendor.l10n_do_ecf_auto_bill = True
# The manual opens this record by xmlid, which survives a rebuilt database.
env["ir.model.data"]._update_xmlids([{"xml_id": "__manual__.ecf_vendor", "record": vendor}])
show("Issuing vendor", "%s (%s)" % (vendor.name, vendor.vat))
show("Automatic billing", vendor.l10n_do_ecf_auto_bill)

# Links learned on earlier invoices. They are what makes part of the lines
# arrive already resolved, so the effect of the learning shows on the very first
# screen without anybody touching a line.
ProductMap = env["l10n_do.ecf.product.map"]
ProductMap._learn(vendor, "", "Carnes paq 2lb", p_meat, company=company)
ProductMap._learn(vendor, "", "LAPICES", p_pencils, company=company)
ProductMap._learn(vendor, "", "GALLETAS", p_cookies, company=company)
# Code *and* name: this vendor sends 1521 on every line of E310000000202, so the
# code alone identifies nothing and only the Gouda line resolves.
ProductMap._learn(vendor, "1521", "Gouda Import", p_gouda, company=company)
# Resolves on its own too, and that is the point: the product is on file at 16%
# while this vendor invoices it at 18%, so the document arrives linked *and*
# flagged, which is the case the manual is about.
ProductMap._learn(vendor, "", "Servicios profesionales", p_consulting, company=company)
env.cr.commit()
show("Pre-learned links", ProductMap.search_count([]))

# =============================================================================
title("Credit note keyed in by hand (the duplicate case)")
# =============================================================================
# E340000000007 is captured *before* the import: when the cron brings it, the
# document has to land in `duplicate` and offer to attach the evidence to this
# refund, never create a second one. Since 19.0 the NCF is the move name.
credit_note_type = env["l10n_latam.document.type"].search(
    [("l10n_do_ncf_type", "=", "e-credit_note"), ("country_id", "=", DO.id)], limit=1
)
manual = env["account.move"].search([("name", "=", "E340000000007")], limit=1)
if not manual:
    manual = env["account.move"].create(
        {
            "move_type": "in_refund",
            "company_id": company.id,
            "journal_id": purchase_journal.id,
            "partner_id": vendor.id,
            "invoice_date": "2020-04-10",
            "invoice_line_ids": [
                (0, 0, {"product_id": p_meat.id, "quantity": 1, "price_unit": 100})
            ],
        }
    )
    manual.write(
        {
            "l10n_latam_document_type_id": credit_note_type.id,
            "l10n_latam_document_number": "E340000000007",
        }
    )
env.cr.commit()
show("Hand-keyed refund", "%s for %s (%s)" % (manual.name, manual.amount_total, manual.state))

# =============================================================================
title("Reception API mocked over the module's test fixtures")
# =============================================================================


def fetch_received_invoices(self, start_date, end_date, buyer_rnc=None):
    return svc.ReceptionResult(True, list(FEED))


def fetch_invoices_count(self, start_date, end_date, buyer_rnc=None):
    return svc.ReceptionSummary(total_invoices=len(FEED), total_amount=0.0)


def fetch_ecf_xml(self, encf, issuer_rnc):
    content = fixtures.XML_BY_ENCF.get(encf)
    if content is None:
        return svc.ReceptionResult(False, error="no XML fixture for %s" % encf)
    return svc.ReceptionResult(True, content.encode())


def submit_acecf(self, payload, submit_to_dgii=True):
    return svc.ReceptionResult(True, {"status": "accepted"})


def fetch_taxpayer(self, rnc):
    return svc.ReceptionResult(True, {"name": "DOCUMENTOS ELECTRONICOS DE 02"})


def fetch_commercial_approval(self, encf):
    return svc.ReceptionResult(True, {"approval_status": "pending"})


svc.ReceptionService.fetch_received_invoices = fetch_received_invoices
svc.ReceptionService.fetch_invoices_count = fetch_invoices_count
svc.ReceptionService.fetch_ecf_xml = fetch_ecf_xml
svc.ReceptionService.submit_acecf = submit_acecf
svc.ReceptionService.fetch_taxpayer = fetch_taxpayer
svc.ReceptionService.fetch_commercial_approval = fetch_commercial_approval

# Received today, so the approval deadline on screen is a date in the future.
RECEIVED_ON = "%sT09:15:45" % fields.Date.context_today(env["res.company"])
DOCUMENTS = [
    ("E310000000500", "9999.00"),
    ("E340000000007", "118.00"),
    ("E310000000202", "354.00"),
    ("E310000000200", "2340.00"),
    ("E310000000034", "3034.00"),
    ("E310000000201", "4674.35"),
    ("E310000000035", "118.00"),
    ("E310000000099", "7139.00"),
    ("E310000000101", "1180.00"),
    ("E340000000203", "1.00"),
]
FEED = [
    fixtures.api_payload(encf, total, date_received=RECEIVED_ON)
    for encf, total in DOCUMENTS
]

Document = env["l10n_do.ecf.received.document"]
Document._cron_fetch_received_documents()
env.cr.commit()
show("Documents in the inbox", Document.search_count([]))


def get(encf):
    return Document.search([("encf", "=", encf)], limit=1)


# =============================================================================
title("E310000000035: second invoice from the vendor, billed with no clicks")
# =============================================================================
# Its only item is "CARNES  PAQ 2LB" and the learned wording was
# "Carnes paq 2lb": same normalized name, so it arrives `ready` and can be
# billed straight away. This is also what fills the "times used" column of the
# learned-links list.
recurring = get("E310000000035")
if recurring.state == "ready":
    recurring.action_create_invoice()
    env.cr.commit()
show("E310000000035", "%s -> bill %s" % (recurring.state, recurring.move_id.name))

# =============================================================================
title("E310000000034: linked without learning, with a purchase order")
# =============================================================================
# Line 1 arrived resolved by the learned wording; lines 2 and 3 are linked here
# **without remembering**, so the three states of the vendor-item widget live
# side by side on one document: saved link, product set but link not saved, and
# the order route already started -- which is why its header only offers
# "Receive + bill".
widget_doc = get("E310000000034")
# Automatic billing off while this one is set up: the manual needs a document that
# went out through the purchase order, and the vendor's switch would have billed it
# the moment its last line was linked.
vendor.l10n_do_ecf_auto_bill = False
if widget_doc.state in ("to_map", "ready"):
    for line in widget_doc.line_ids.filtered(lambda line: line.state == "pending"):
        # Product chosen on the line and *no wand*: that is what leaves the link
        # unsaved, which is the state the capture is about.
        product = p_install if "SRV" in (line.item_code or "") else p_cable
        # Same resolution the widget uses: the product's own purchase taxes
        # first, and only while they charge the rate this e-CF declares.
        taxes, tax_source = line._l10n_do_resolve_taxes(product=product)
        line.write(
            {
                "product_id": product.id,
                "product_uom_id": product.uom_id.id,
                "tax_ids": [(6, 0, taxes.ids)],
                "tax_source": tax_source,
                "state": "mapped",
            }
        )
    widget_doc._l10n_do_evaluate_state()
    widget_doc.action_create_purchase_order()
    env.cr.commit()
vendor.l10n_do_ecf_auto_bill = True
env.cr.commit()
show("E310000000034", "%s, PO %s" % (widget_doc.state, widget_doc.purchase_order_id.name))
for line in widget_doc.line_ids:
    print(
        "     %-26s %-24s %-8s %s"
        % (
            (line.product_id.display_name or "")[:26],
            (line.item_name or "-")[:24],
            line.item_code or "-",
            line.map_state,
        )
    )

# =============================================================================
title("E310000000101: the product is taxed at 16%, the e-CF declares 18%")
# =============================================================================
# Nothing is done here: the document came out of the import already linked, by
# the pre-learned wording, and already flagged. Printed to prove that the module
# kept the tax the product carries -- it does not silently bill what DGII was
# told -- and that it said so on the chatter and refused to bill it.
mismatch = get("E310000000101")
line = mismatch.line_ids[:1]
show(
    "E310000000101",
    "%s | %s | declared %.2f%% vs linked %.2f%% | mismatch %s"
    % (
        mismatch.state,
        line.product_id.display_name,
        line.tax_rate_reported,
        line._l10n_do_tax_rate(line.tax_ids),
        mismatch.tax_mismatch,
    ),
)
show("Bill", mismatch.move_id.display_name or "not created, as it should be")

# =============================================================================
title("Inbox as the manual describes it")
# =============================================================================
print(
    "   %-4s %-16s %-4s %-11s %-6s %14s %-7s %-8s %-9s %s"
    % ("id", "e-NCF", "type", "state", "incl", "total", "lines", "to link", "tax diff", "bill")
)
for document in Document.search([], order="id"):
    print(
        "   %-4s %-16s %-4s %-11s %-6s %14.2f %-7s %-8s %-9s %s"
        % (
            document.id,
            document.encf,
            document.ecf_type,
            document.state,
            "YES" if document.tax_included else "no",
            document.amount_total_xml,
            document.line_count,
            document.pending_line_count,
            "YES" if document.tax_mismatch else "no",
            document.move_id.display_name or "-",
        )
    )

print("\n   Learned links (the system's memory):")
for link in ProductMap.search([]):
    wordings = ", ".join(
        "%s%s" % ("[%s] " % item.item_code if item.item_code else "", item.item_name)
        for item in link.item_ids
    )
    print("     %-28s <- %-46s %s uses" % (link.product_id.display_name[:28], wordings[:46], link.hit_count))

env.cr.commit()
print("\nSEED OK")
