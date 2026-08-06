#!/usr/bin/env python3
"""
Setup script: payment_azul_webservices + eCommerce (Odoo 17)

Crea la DB de prueba con `payment_azul_webservices` y `website_sale`
instalados CON demo data (productos publicados en /shop), y deja el
proveedor Azul configurado en estado *test*:

* Credenciales sandbox: MID 39038540035, Auth1/Auth2 `3dsecure`.
* Certificado/llave PEM tomados de `certs/` (progressa.local.crt +
  progressa-dev-unencrypted.key) para que pyazul pueda construir el
  contexto SSL.
* 3D Secure habilitado, proveedor publicado en el website y con diario
  bancario asignado.
* `web.base.url` fijado a http://localhost:8090 (callbacks 3DS en dev).

Uso:
    python3 setup_test_azul_ecommerce.py            # crea/reusa DB y siembra
    python3 setup_test_azul_ecommerce.py --reset    # drop & recreate DB

Requisitos:
    - Contenedor Odoo corriendo (lfernandez_v17), UI en http://localhost:8090
    - pyazul==3.2.1 dentro del contenedor (ya viene en la imagen)

Al terminar: http://localhost:8090/shop (checkout con Azul en modo test),
backend con admin/admin. Para aislar la DB en el login, descomentar
`dbfilter = ^test_v17e_azul$` en conf/odoo.conf y reiniciar el contenedor.
"""

import argparse
import base64
import pathlib
import subprocess
import sys

CONTAINER = "lfernandez_v17"
DB_NAME = "test_v17e_azul"
DB_ARGS = [
    "--db_host", "odoo-db",
    "--db_port", "5432",
    "--db_user", "odoo",
    "--db_password", "odoo_password",
]
MODULES = ",".join([
    "payment_azul_webservices",  # proveedor Azul (arrastra payment)
    "website_sale",              # eCommerce (website + sale)
])

REPO = pathlib.Path(__file__).resolve().parent
CERT_PATH = REPO / "certs" / "progressa.local.crt"
KEY_PATH = REPO / "certs" / "progressa-dev-unencrypted.key"

SEED_SCRIPT = r'''
provider = env.ref("payment_azul_webservices.payment_provider_azul")
company = env.ref("base.main_company")

journal = env["account.journal"].search(
    [("type", "=", "bank"), ("company_id", "=", company.id)], limit=1)

vals = {
    "state": "test",
    "company_id": company.id,
    "azul_webservices_merchant_account": "39038540035",
    "azul_webservices_auth_1": "3dsecure",
    "azul_webservices_auth_2": "3dsecure",
    "azul_webservices_cert_pem": "__CERT_B64__",
    "azul_webservices_cert_pem_filename": "progressa.local.crt",
    "azul_webservices_key_pem": "__KEY_B64__",
    "azul_webservices_key_pem_filename": "progressa-dev-unencrypted.key",
    "azul_webservices_enable_3ds": True,
}
if "is_published" in provider._fields:
    vals["is_published"] = True
if journal and not provider.journal_id:
    vals["journal_id"] = journal.id
provider.write(vals)

# Callbacks 3DS en dev: URL base estable apuntando al puerto publicado.
env["ir.config_parameter"].sudo().set_param("web.base.url", "http://localhost:8090")
env["ir.config_parameter"].sudo().set_param("web.base.url.freeze", "True")

website = env["website"].search([], limit=1)
published_products = env["product.template"].search_count(
    [("is_published", "=", True)])

env.cr.commit()
print("SEED OK")
print("  provider: %s | state=%s | published=%s | journal=%s" % (
    provider.name, provider.state,
    provider.is_published if "is_published" in provider._fields else "n/a",
    provider.journal_id.name or "-"))
print("  merchant=%s 3ds=%s cert=%s" % (
    provider.azul_webservices_merchant_account,
    provider.azul_webservices_enable_3ds,
    provider.azul_webservices_cert_pem_filename))
print("  website: %s | productos publicados en /shop: %d" % (
    website.name, published_products))
'''


def run(cmd, **kw):
    print(f"[cmd] {' '.join(cmd[:6])} ...")
    return subprocess.run(cmd, **kw)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="drop & recreate DB")
    args = parser.parse_args()

    if args.reset:
        run(["docker", "exec", CONTAINER, "bash", "-c",
             f"PGPASSWORD=odoo_password psql -h odoo-db -U odoo postgres -c "
             f"\"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
             f"WHERE datname='{DB_NAME}' AND pid <> pg_backend_pid();\" >/dev/null 2>&1; "
             f"PGPASSWORD=odoo_password dropdb -h odoo-db -U odoo --if-exists {DB_NAME}"])

    # 1. Crear DB e instalar módulos CON demo data (productos para /shop)
    result = run(["docker", "exec", CONTAINER, "odoo", "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn",
                  "--stop-after-init", "--no-http",
                  "-i", MODULES])
    if result.returncode != 0:
        print("[error] instalación falló"); sys.exit(1)

    # 2. Configurar proveedor Azul vía odoo shell
    cert_b64 = base64.b64encode(CERT_PATH.read_bytes()).decode()
    key_b64 = base64.b64encode(KEY_PATH.read_bytes()).decode()
    seed = SEED_SCRIPT.replace("__CERT_B64__", cert_b64).replace("__KEY_B64__", key_b64)
    result = run(["docker", "exec", "-i", CONTAINER, "odoo", "shell",
                  "-d", DB_NAME, *DB_ARGS,
                  "--http-port", "8072", "--log-level", "warn", "--no-http"],
                 input=seed.encode())
    if result.returncode != 0:
        print("[error] seed falló"); sys.exit(1)

    print(f"\n[done] DB '{DB_NAME}' lista.")
    print("  Tienda:  http://localhost:8090/shop")
    print("  Backend: http://localhost:8090/web (admin/admin)")


if __name__ == "__main__":
    main()
