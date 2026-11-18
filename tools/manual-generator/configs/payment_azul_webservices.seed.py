import base64
from unittest.mock import patch

from odoo.addons.payment import utils as payment_utils

env["res.lang"]._activate_lang("es_DO")
env["ir.module.module"].search([("state", "=", "installed")])._update_translations(["es_DO"])
es_do = env["res.lang"]._lang_get("es_DO")
env["website"].search([]).write({"language_ids": [(4, es_do.id)], "default_lang_id": es_do.id})
admin = env.ref("base.user_admin")
admin.write({"lang": "es_DO", "tz": "America/Santo_Domingo", "tour_enabled": False})

dop = env.ref("base.DOP")
dop.active = True
company = env.company
company.write({"country_id": env.ref("base.do").id})
if not env["res.currency.rate"].search([("currency_id", "=", dop.id)]):
    env["res.currency.rate"].create({"currency_id": dop.id, "rate": 60.0, "name": "2020-01-01", "company_id": company.id})
admin.partner_id.write({
    "name": "Mitchell Admin", "street": "Av. Winston Churchill 1099", "city": "Santo Domingo",
    "zip": "10148", "country_id": env.ref("base.do").id, "phone": "+1 809 555 0101", "email": "admin@example.com",
})

providers = env["payment.provider"]
if env["ir.module.module"]._get("payment_azul_webpages").state == "installed":
    webpages = env.ref("payment_azul_webpages.payment_provider_azul")
    webpages.write({"azul_merchant_account": "39038540035", "azul_signature_key": "CLAVE-DE-PRUEBA", "is_published": True})
    providers |= webpages
if env["ir.module.module"]._get("payment_azul_webservices").state == "installed":
    webservices = env.ref("payment_azul_webservices.payment_provider_azul")
    webservices.write({
        "azul_webservices_merchant_account": "39038540035",
        "azul_webservices_auth_1": "3dsecure",
        "azul_webservices_auth_2": "3dsecure",
        "azul_webservices_cert_pem": base64.b64encode(b"-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n").decode(),
        "azul_webservices_cert_pem_filename": "azul_certificado.crt",
        "azul_webservices_key_pem": base64.b64encode(b"-----BEGIN PRIVATE KEY-----\nZmFrZQ==\n-----END PRIVATE KEY-----\n").decode(),
        "azul_webservices_key_pem_filename": "azul_llave.key",
        "is_published": True,
    })
    providers |= webservices
providers._compute_available_currency_ids()
env["payment.provider"].search([("code", "not in", ("azul", "azul_webservices"))]).write({"is_published": False, "active": False})

product = env["product.template"].search([("name", "=", "Lentes de sol polarizados")], limit=1) or env["product.template"].create({
    "name": "Lentes de sol polarizados", "list_price": 2500.0, "type": "consu", "is_published": True, "sale_ok": True,
})
partner = env["res.partner"].search([("name", "=", "Ana Rodríguez")], limit=1) or env["res.partner"].create({
    "name": "Ana Rodríguez", "email": "ana.rodriguez@example.com", "country_id": env.ref("base.do").id,
    "city": "Santiago de los Caballeros", "street": "Calle del Sol 45",
})


def _new_tx(provider, reference, operation, **values):
    tx = env["payment.transaction"].search([("reference", "=", reference)])
    if tx:
        return tx
    order = env["sale.order"].create({
        "partner_id": partner.id,
        "order_line": [(0, 0, {"product_id": product.product_variant_id.id, "product_uom_qty": 1})],
    })
    return env["payment.transaction"].create(dict({
        "provider_id": provider.id,
        "payment_method_id": provider.primary_payment_method_ids[:1].id,
        "reference": reference,
        "amount": order.amount_total,
        "currency_id": order.currency_id.id,
        "partner_id": partner.id,
        "operation": operation,
        "sale_order_ids": [(6, 0, order.ids)],
    }, **values))


if "webpages" in locals():
    tx = _new_tx(webpages, "S00001-PAGINA-AZUL", "online_redirect")
    if tx.state == "draft":
        with patch.object(payment_utils, "generate_access_token", return_value="manual"):
            tx._get_processing_values()
        tx._record({
            "OrderNumber": tx.reference, "IsoCode": "00", "AuthorizationCode": "OK3850",
            "ResponseMessage": "APROBADA", "AzulOrderId": "44892837", "DataVaultToken": "",
        })
        env.cr.commit()
        env.ref("payment.processing_cron").method_direct_trigger()
        env.cr.commit()
if "webservices" in locals():
    tx = _new_tx(webservices, "S00002-AZUL-WS", "online_direct")
    if tx.state == "draft":
        approved = {"IsoCode": "00", "ResponseMessage": "APROBADA", "AuthorizationCode": "OK7721",
                    "AzulOrderId": "51200984", "RRN": "202610011530", "TransactionType": "Sale"}
        with patch.object(type(webservices), "_azul_make_request", autospec=True, return_value=approved):
            tx.with_context(card_data={"CardNumber": "4035874000424977", "CVC": "977", "Expiration": "202812",
                                       "SaveToDataVault": "0"})._send_payment_request()
env.cr.commit()
print("SEED OK", providers.mapped("code"))
