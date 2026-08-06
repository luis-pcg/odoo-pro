# Seed for the functional smoke manual of payment_azul_webservices (Odoo 17).
# The module data file pre-creates the provider record
# (payment_azul_webservices.payment_provider_azul); with --without-demo=all it has
# no credentials/state. Here we put it in TEST state with fake credentials and 3DS
# enabled, and create deterministic navigation actions so Playwright can open the
# provider list and the Azul provider form (credentials + 3DS config tab).
# Executed inside `odoo shell`; the global `env` is available. Ends with commit.

import base64

FAKE_CERT = base64.b64encode(b"-----BEGIN CERTIFICATE-----\nZmFrZQ==\n-----END CERTIFICATE-----\n")
FAKE_KEY = base64.b64encode(b"-----BEGIN PRIVATE KEY-----\nZmFrZQ==\n-----END PRIVATE KEY-----\n")

provider = env.ref("payment_azul_webservices.payment_provider_azul")
provider.write(
    {
        "state": "test",
        "azul_webservices_merchant_account": "39038540035",
        "azul_webservices_auth_1": "3dsecure",
        "azul_webservices_auth_2": "3dsecure",
        "azul_webservices_cert_pem": FAKE_CERT,
        "azul_webservices_cert_pem_filename": "cert.pem",
        "azul_webservices_key_pem": FAKE_KEY,
        "azul_webservices_key_pem_filename": "key.pem",
        "azul_webservices_enable_3ds": True,
    }
)


def demo_action(xmlid_name, name, view_mode, domain, res_id=False):
    full = "payment_azul_webservices.%s" % xmlid_name
    if env.ref(full, raise_if_not_found=False):
        return
    vals = {
        "name": name,
        "res_model": "payment.provider",
        "view_mode": view_mode,
        "domain": domain,
    }
    if res_id:
        vals["res_id"] = res_id
    act = env["ir.actions.act_window"].create(vals)
    env["ir.model.data"].create(
        {
            "module": "payment_azul_webservices",
            "name": xmlid_name,
            "model": "ir.actions.act_window",
            "res_id": act.id,
            "noupdate": True,
        }
    )


demo_action(
    "manual_providers_action",
    "Proveedor de pago Azul",
    "list,form",
    "[('code', '=', 'azul_webservices')]",
)
demo_action(
    "manual_azul_form_action",
    "Azul Webservices (configuracion)",
    "form,list",
    "[('id', '=', %d)]" % provider.id,
    res_id=provider.id,
)

env.cr.commit()
print(
    "SEED OK: provider=%s state=%s 3ds=%s merchant=%s"
    % (
        provider.name,
        provider.state,
        provider.azul_webservices_enable_3ds,
        provider.azul_webservices_merchant_account,
    )
)
