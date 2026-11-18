# Seed for the manual of account_payment_card_bin (BIN de tarjetas).
# Activa es_DO para el admin y agrega un BIN propio de ejemplo junto al
# catalogo precargado del modulo. Ejecutado dentro de `odoo shell`.

es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").write({"lang": "es_DO", "tour_enabled": False})

Bin = env["account.payment.card.bin"]
if not Bin.search([("name", "=", "552246")]):
    Bin.create(
        {
            "name": "552246",
            "card_name": "BHD Mastercard Black",
            "card_type": "credit",
            "card_brand_id": env.ref("account_payment_card_bin.mastercard").id,
            "l10n_do_bank": "bhd",
        }
    )

env.cr.commit()
print(
    "SEED OK | marcas: %s | bins: %s"
    % (env["account.card.brand"].search_count([]), Bin.search_count([]))
)
