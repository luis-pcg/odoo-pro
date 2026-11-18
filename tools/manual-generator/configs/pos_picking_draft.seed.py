# Seed for the functional manual of pos_picking_draft (Odoo 17).
# Leaves the database ready to record one POS sale end to end:
#   - the company updates stock in real time, so the picking shows up as soon as
#     the order is paid (with 'closing' it would only appear when the session is
#     closed; the module behaves the same either way),
#   - the company keeps the POS pickings pending validation (pos_picking_keep_draft),
#     which is the default but can be switched off per company,
#   - one storable product with stock, available in the POS,
#   - the Shop config with a cash payment method, so opening the session asks for
#     the opening cash balance (the "caja"),
#   - no session left open, so the dashboard shows "New Session",
#   - no POS picking left pending from an earlier run.
# Executed inside `odoo shell`; the global `env` is available. Ends with commit.

company = env["res.company"].browse(1)
company.point_of_sale_update_stock_quantities = "real"
# The feature is per company and can be switched off; the manual documents it on.
company.pos_picking_keep_draft = True

config = env["pos.config"].search([("company_id", "=", company.id)], limit=1)
if not config:
    raise ValueError("no pos.config in this database")

cash = env["pos.payment.method"].search(
    [("is_cash_count", "=", True), ("company_id", "=", company.id)], limit=1
)
if cash and cash not in config.payment_method_ids:
    config.payment_method_ids = [(4, cash.id)]

product = env["product.product"].search([("default_code", "=", "POS-SILLA")], limit=1)
if not product:
    product = env["product.product"].create(
        {
            "name": "Silla Ejecutiva (POS)",
            "default_code": "POS-SILLA",
            "type": "product",
            "available_in_pos": True,
            "list_price": 1500.0,
            "standard_price": 900.0,
            "taxes_id": [(5, 0, 0)],
            "supplier_taxes_id": [(5, 0, 0)],
        }
    )
product.write({"available_in_pos": True, "active": True})

# The manual starts from an empty dashboard: no session pending.
open_sessions = env["pos.session"].search([("state", "!=", "closed")])
for session in open_sessions:
    if session.state == "opening_control":
        session.set_cashbox_pos(0, None)
    if session.state == "opened":
        session.action_pos_session_closing_control()
    if session.state == "closing_control":
        session.action_pos_session_close()

# Leftovers from earlier capture runs: the manual filters the transfers by "Ready"
# and opens the first row, so there must be no POS picking pending beforehand.
pending_pos_pickings = env["stock.picking"].search(
    [("pos_session_id", "!=", False), ("state", "not in", ("done", "cancel"))]
)
for picking in pending_pos_pickings:
    picking.button_validate()

source = config.picking_type_id.default_location_src_id
# Always back to exactly 50: the manual states the stock before and after the sale
# (50 -> 49), so each capture run has to start from the same number. Runs after the
# cleanup above, which consumes stock when it validates the leftover transfers.
on_hand = product.with_context(location=source.id).qty_available
if on_hand != 50:
    env["stock.quant"]._update_available_quantity(product, source, 50 - on_hand)

admin = env.ref("base.user_admin")
for group in ("point_of_sale.group_pos_manager", "stock.group_stock_manager"):
    admin.write({"groups_id": [(4, env.ref(group).id)]})

print(
    "seed ok | product=%s | stock=%s | config=%s | cash=%s"
    % (
        product.display_name,
        product.with_context(location=source.id).qty_available,
        config.name,
        bool(cash),
    )
)
env.cr.commit()
