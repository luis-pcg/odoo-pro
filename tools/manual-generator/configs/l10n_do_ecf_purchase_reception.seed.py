# Seed for the functional manual of l10n_do_ecf_purchase_reception (Odoo 17).
#
# The inbox is a sandbox: anybody who opens this database to try the buttons
# leaves it in a different state than the one the manual describes -- a document
# gets linked, an alias gets learned, a clone gets created to exercise the three
# accounting routes. This puts back the premises each flow of the manual claims:
#
#   - E310000000034 is the "to link" example: five lines with no product, so the
#     header offers *Vincular líneas* and the wizard has something to show,
#   - the aliases that would resolve those lines are archived, because otherwise
#     the importer links them again the moment the state is re-evaluated,
#   - only the documents the cron brought from the sandbox are left in the inbox,
#     so the list capture shows the six the manual counts.
#
# Executed inside `odoo shell`; the global `env` is available. Ends with commit.
# Nothing here touches configuration, products or learned links of other
# documents: E310000000005 keeps its half-learned lines on purpose, that is what
# the widget capture is about.

Document = env["l10n_do.ecf.received.document"]
ProductMap = env["l10n_do.ecf.product.map"]

TO_LINK_ENCF = "E310000000034"
# What the sandbox returns for our RNC. Anything else in the inbox was made here.
SANDBOX_ENCF = [
    "E340000000015",
    "E330000000001",
    "E310000000034",
    "E310000000008",
    "E310000000005",
    "E310000000002",
]

# --- documents made by hand while testing ------------------------------------
extra = Document.search([("encf", "not in", SANDBOX_ENCF)])
if extra:
    print("seed: dropping hand-made documents %s" % ", ".join(extra.mapped("encf")))
    # Their purchase orders and bills, if any, are left alone: deleting
    # accounting documents is not this script's business.
    extra.unlink()

# --- the "to link" document --------------------------------------------------
document = Document.search([("encf", "=", TO_LINK_ENCF)], limit=1)
if not document:
    raise ValueError("%s is not in this database; run setup_test_ecf_purchase_reception.py --reset --inbox" % TO_LINK_ENCF)

# The wording lives on l10n_do.ecf.product.item, which is what the importer
# looks up; the alias is whatever map that wording points at.
aliases = ProductMap.search(
    [
        ("partner_id", "=", document.partner_id.id),
        ("item_ids.item_name_norm", "in", document.line_ids.mapped("item_name_norm")),
    ]
)
if aliases:
    print("seed: archiving %s alias(es) that resolve %s" % (len(aliases), TO_LINK_ENCF))
    aliases.action_archive()

document.line_ids.write(
    {
        "product_id": False,
        "product_uom_id": False,
        "tax_ids": [(5, 0, 0)],
        "account_id": False,
        "map_id": False,
        "match_source": False,
        "state": "pending",
    }
)
document._l10n_do_evaluate_state()
print("seed: %s -> %s, %s line(s) pending" % (document.encf, document.state, document.pending_line_count))

env.cr.commit()
