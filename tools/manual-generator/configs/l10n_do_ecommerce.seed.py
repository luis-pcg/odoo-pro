# Seed for the manual of l10n_do_ecommerce (localizacion dominicana del checkout).
#
# Builds, from a CLEAN DB:
#   * INDEXA SRL, Dominican company with the DO chart of accounts (currency DOP)
#   * the b2b address fields enabled on the website, which is what makes the
#     company name / RNC / TaxPayer Type block render at all
#   * two published products, one of them above the 250,000 DOP fiscal
#     threshold, and an open cart for the admin partner holding the expensive
#     one, so /shop/address renders with the tax ID already required
#   * the admin partner left WITHOUT a country, so the first screenshot shows
#     the country <-> TaxPayer Type sync doing its job on page load
#
# Runs inside `odoo shell` (`env` is available). Ends with a commit.

company = env.ref("base.main_company")
do = env.ref("base.do")

# -- 0. Espanol --------------------------------------------------------------
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create({"lang_ids": [(6, 0, [es.id])], "overwrite": True}).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

env["ir.module.module"].search(
    [
        ("name", "in", ["l10n_do_ecommerce", "l10n_do_accounting", "l10n_do", "portal", "website_sale"]),
        ("state", "=", "installed"),
    ]
)._update_translations(filter_lang="es_DO", overwrite=True)

# -- 1. Compania RD + plan contable dominicano -------------------------------
company.write(
    {
        "name": "INDEXA SRL",
        "country_id": do.id,
        "vat": "131793916",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
    }
)
company.partner_id.lang = "es_DO"
env["account.chart.template"].try_loading("do", company=company, install_demo=False)

# -- 2. Website: campos b2b encendidos ---------------------------------------
# Sin esta vista el nucleo no dibuja ni el nombre de compania ni el RNC, y por
# lo tanto tampoco el selector de tipo de contribuyente que se cuelga de ellos.
website = env["website"].search([], limit=1)
website.company_id = company
env.ref("website_sale.address_b2b").active = True

# -- 3. Productos ------------------------------------------------------------
Product = env["product.template"]
Product.search([("name", "in", ["Servidor de aplicaciones", "Soporte mensual"])]).unlink()
caro = Product.create(
    {
        "name": "Servidor de aplicaciones",
        "type": "service",
        "list_price": 295000.0,
        "taxes_id": False,
        "is_published": True,
        "website_id": website.id,
    }
)
Product.create(
    {
        "name": "Soporte mensual",
        "type": "service",
        "list_price": 4500.0,
        "taxes_id": False,
        "is_published": True,
        "website_id": website.id,
    }
)

# -- 4. Carrito abierto del administrador, por encima del umbral -------------
# El nucleo recupera el carrito abandonado de un usuario identificado en la
# primera peticion, asi que basta con dejarlo creado para que /shop/address lo
# encuentre.
# Direccion completa y dominicana: el checkout necesita una para dibujar la
# tarjeta de direccion de facturacion, y el tipo de contribuyente se calcula a
# partir del pais.
admin_partner = env.ref("base.user_admin").partner_id
admin_partner.write(
    {
        "email": "admin@indexa.do",
        "phone": "8095551234",
        "street": "Av. Winston Churchill 1099",
        "city": "Santo Domingo",
        "zip": "10101",
        "country_id": do.id,
    }
)

env["sale.order"].search([("partner_id", "=", admin_partner.id), ("state", "=", "draft")]).unlink()
cart = env["sale.order"].create(
    {
        "partner_id": admin_partner.id,
        "website_id": website.id,
        "order_line": [(0, 0, {"product_id": caro.product_variant_id.id, "product_uom_qty": 1})],
    }
)

env.cr.commit()
print(
    "SEED OK: %s, carrito %s por %s %s, b2b=%s"
    % (
        company.name,
        cart.name,
        cart.amount_total,
        cart.currency_id.name,
        env.ref("website_sale.address_b2b").active,
    )
)

# -- 5. El sitio web en espanol ----------------------------------------------
# Las etiquetas del selector salen de _get_l10n_do_dgii_payer_types_selection()
# en l10n_do_accounting, traducidas via su es_DO.po. El frontend usa el idioma
# del sitio, no el del usuario, asi que sin esto el checkout sale en ingles.
website.write({"language_ids": [(6, 0, [es.id])], "default_lang_id": es.id})
env.cr.commit()
print("SEED OK: sitio en %s" % website.default_lang_id.code)
