# Seed for the certification manual of l10n_do_ecf_invoicing (Odoo 19).
#
# Builds a Dominican company that is already an e-CF issuer and whose service
# environment is Certification, which is the only state where the generator is
# available, and then leaves a first batch of test documents already generated so
# the wizard screenshots show the progress columns with real numbers.
#
# The DGII answers are simulated by writing the send state directly: the manual
# has to regenerate the same way on any machine, with no network and no sandbox
# account. What the screenshots show is the state the module itself writes when
# the real answer arrives.
#
# Executed inside `odoo shell`; the global `env` is available. Ends with commit.

from odoo import fields

DO = env.ref("base.do")
COMPANY_RNC = "131793916"


def title(text):
    print("\n" + "=" * 74)
    print("  " + text)
    print("=" * 74)


def show(label, value):
    print("   %-34s %s" % (label + ":", value))


# =============================================================================
title("Dominican company, chart of accounts and fiscal journals")
# =============================================================================
company = env.ref("base.main_company")
company.write(
    {
        "name": "COMERCIAL DEL CARIBE SRL",
        "country_id": DO.id,
        "vat": COMPANY_RNC,
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
    }
)
if company.chart_template != "do":
    env["account.chart.template"].try_loading("do", company=company, install_demo=False)
    env.cr.commit()

company.l10n_do_ecf_issuer = True
company.l10n_do_dgii_start_date = fields.Date.to_date("2020-01-01")

for journal in env["account.journal"].search(
    [("type", "in", ("sale", "purchase")), ("company_id", "=", company.id)]
):
    if not journal.l10n_latam_use_documents:
        journal.l10n_latam_use_documents = True
    else:
        journal._l10n_do_create_document_types()

company.write(
    {
        "l10n_do_ecf_api_version": "v3",
        # The whole feature hangs off this: the generator is only reachable here.
        "l10n_do_ecf_service_env": "CerteCF",
    }
)
env.cr.commit()

show("Company / RNC", "%s / %s" % (company.name, company.vat))
show("Chart of accounts", company.chart_template)
show("e-CF environment", company.l10n_do_ecf_service_env)

# =============================================================================
title("Operator: groups, password and Dominican Spanish")
# =============================================================================
admin = env.ref("base.user_admin")
# The e-CF environment selector is groups="base.group_no_one": it only renders on a
# session in debug mode AND for a user in that group, so the manual needs both.
admin.group_ids |= (
    env.ref("account.group_account_manager") | env.ref("uom.group_uom") | env.ref("base.group_no_one")
)
admin.password = "admin"

env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
admin.lang = "es_DO"
env.cr.commit()
show("Interface language", admin.lang)

env = env(context=dict(env.context, lang="es_DO"))

# =============================================================================
title("First batch of test documents, as if it had already been run once")
# =============================================================================
# l10n_do_active_test keeps _post from signing: the manual's database has no .p12
# certificate, and signing is not what these screenshots are about.
wizard = env["l10n_do.ecf.certification.wizard"].with_context(l10n_do_active_test=True).create(
    {"automation": "post"}
)
wizard.line_ids.write({"selected": False, "qty": 0})

for prefix, qty in (("E31", 3), ("E32", 2)):
    line = wizard.line_ids.filtered(lambda line, p=prefix: line.l10n_latam_document_type_id.doc_code_prefix == p)
    line.write({"selected": True, "qty": qty})

action = wizard.action_generate()
moves = env["account.move"].browse(action["domain"][0][2])
show("Documents generated", len(moves))
show("NCF handed out", ", ".join(moves.mapped("name")))

# =============================================================================
title("Simulated DGII answers")
# =============================================================================
fiscal = moves.filtered(lambda m: m.l10n_latam_document_type_id.doc_code_prefix == "E31")
consumer = moves.filtered(lambda m: m.l10n_latam_document_type_id.doc_code_prefix == "E32")

fiscal[:2].write({"l10n_do_ecf_send_state": "delivered_accepted", "l10n_do_ecf_trackid": "CERT-TRK-0001"})
consumer[:1].write({"l10n_do_ecf_send_state": "delivered_accepted", "l10n_do_ecf_trackid": "CERT-TRK-0002"})
consumer[1:].write({"l10n_do_ecf_send_state": "delivered_pending", "l10n_do_ecf_trackid": "CERT-TRK-0003"})

# A refused e-CF is cancelled by the module itself, which is what makes the
# wizard propose it again on the next run.
refused = fiscal[2:]
refused.write({"l10n_do_ecf_send_state": "delivered_refused"})
refused.with_context(cancelled_by_dgii=True, skip_cancel_wizard=True).button_cancel()

env.cr.commit()

for move in moves:
    show(move.name, "%s / %s" % (move.state, move.l10n_do_ecf_send_state))

title("Seed ready")
