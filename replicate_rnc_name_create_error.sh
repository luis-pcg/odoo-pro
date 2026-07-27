#!/bin/bash
# replicate_rnc_name_create_error.sh
#
# Reproduce el RPC_ERROR reportado al crear un contacto desde una orden de venta
# (quick-create del many2one partner_id):
#
#   AttributeError: 'Registry' object has no attribute 'in_test_mode'
#     File ".../l10n_do_rnc_validation/models/res_partner.py", line 189, in name_create
#       if self.env.registry.in_test_mode():
#
# Causa: Odoo 19 eliminó Registry.in_test_mode() (el reemplazo interno es
# odoo.modules.module.current_test). El override de name_create en
# l10n_do_rnc_validation lo llamaba en su primera línea, así que TODA llamada a
# name_create sobre res.partner explota. name_create es exactamente lo que
# invoca el widget many2one cuando el usuario escribe un nombre y elige
# 'Crear "..."', de ahí que solo falle desde la orden de venta (u otro m2o) y no
# desde el formulario completo de contactos, que pasa por create().
#
# Segundo error latente en el mismo método: partner.name_get(), API eliminada en
# Odoo 17. Aparecía en cuanto se saltaba el AttributeError anterior.
#
# El script prueba los 4 caminos de name_create con el código actual y, con
# --broken, re-inyecta la versión pre-fix para demostrar el fallo original.
#
# Uso:
#   ./replicate_rnc_name_create_error.sh                 # crea DB, instala, prueba el fix
#   ./replicate_rnc_name_create_error.sh --broken        # además demuestra el crash pre-fix
#   ./replicate_rnc_name_create_error.sh --keep          # no borra la DB al terminar
#   ./replicate_rnc_name_create_error.sh --db=mi_db      # nombre de DB personalizado
#   ./replicate_rnc_name_create_error.sh --skip-install  # DB ya instalada, solo reproduce
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="l10n_do_rnc_validation,sale"

DB_NAME="test_rnc_name_create"
KEEP_DB=false
SKIP_INSTALL=false
SHOW_BROKEN=false
for arg in "$@"; do
  case "$arg" in
    --keep)         KEEP_DB=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    --broken)       SHOW_BROKEN=true ;;
    --db=*)         DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Replicar AttributeError in_test_mode en name_create"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo " Módulos    : $MODULES"
echo " Pre-fix    : $SHOW_BROKEN"
echo "======================================================"

wait_for_db() {
  docker exec "$CONTAINER" bash -lc "
    for i in \$(seq 1 30); do
      if PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
        echo 'Postgres OK (intento '\$i')'; exit 0
      fi
      sleep 2
    done
    echo 'ERROR: Postgres no respondió tras 30 intentos' >&2; exit 1
  "
}

if ! $SKIP_INSTALL; then
  echo "→ Esperando a Postgres..."
  wait_for_db || exit 1

  echo "→ Recreando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS dropdb   -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME
    PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
  " || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULES (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --stop-after-init --without-demo=False \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los módulos' >&2; exit 1; }
fi

echo "→ Reproduciendo el quick-create de contacto (name_create)..."
docker exec -i -e SHOW_BROKEN="$SHOW_BROKEN" "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 2>/dev/null
" <<'PYEOF'
import os
import sys
import traceback
from unittest.mock import MagicMock, patch

_PATCH_REQUESTS = "odoo.addons.l10n_do_rnc_validation.models.res_partner.requests.get"
_PATCH_RNC_DGII = "odoo.addons.l10n_do_rnc_validation.models.res_partner.rnc.check_dgii"

_FAKE_RNC_API = "999999901"      # lo resuelve la API mockeada
_FAKE_RNC_UNKNOWN = "999999902"  # ni API ni DGII lo resuelven
_FAKE_RNC_EXISTING = "999999903" # ya asignado a un contacto

Partner = env["res.partner"]
env.company.l10_do_can_validate_rnc = True

def api_ok(name="TEST COMPANY SRL"):
    resp = MagicMock()
    resp.json.return_value = {"status": "success", "data": [{
        "business_name": name, "tradename": "TEST CO", "phone": "8091234567",
        "street": "Av. Principal", "street_number": "10", "sector": "CENTRO",
        "rnc": _FAKE_RNC_API,
    }]}
    return resp

def api_empty():
    resp = MagicMock()
    resp.json.return_value = {"status": "success", "data": []}
    return resp

print("\n" + "=" * 64)
print(" ENTORNO")
print("=" * 64)
env.cr.execute("select latest_version from ir_module_module where name='l10n_do_rnc_validation'")
print(f" Versión módulo en DB       : {env.cr.fetchone()[0]}")
print(f" Registry.in_test_mode      : {'existe' if hasattr(env.registry, 'in_test_mode') else 'NO existe (eliminado en v19)'}")
print(f" res.partner.name_get       : {'existe' if hasattr(Partner, 'name_get') else 'NO existe (eliminado en v17)'}")

failures = []

def run(label, fn):
    print("\n" + "=" * 64)
    print(f" {label}")
    print("=" * 64)
    try:
        partner_id, display_name = fn()
        partner = Partner.browse(partner_id)
        print(f" OK -> id={partner_id} display_name={display_name!r} name={partner.name!r} vat={partner.vat!r}")
        return partner_id
    except Exception:
        failures.append(label)
        print(" >>> ERROR REPRODUCIDO:")
        traceback.print_exc(file=sys.stdout)
        return None
    finally:
        env.cr.rollback()

run("CASO 1: 'Crear \"Contacto Prueba\"' (nombre no numérico)",
    lambda: Partner.name_create("Contacto Prueba"))

def caso2():
    with patch(_PATCH_REQUESTS, return_value=api_ok()):
        return Partner.name_create(_FAKE_RNC_API)

run("CASO 2: quick-create con RNC que la API resuelve", caso2)

def caso3():
    with patch(_PATCH_REQUESTS, return_value=api_empty()), patch(_PATCH_RNC_DGII, return_value=None):
        return Partner.name_create(_FAKE_RNC_UNKNOWN)

run("CASO 3: quick-create con RNC desconocido (nombre = el número)", caso3)

def caso4():
    env.company.l10_do_can_validate_rnc = False
    existing = Partner.create({
        "name": "Existing DO Co", "vat": _FAKE_RNC_EXISTING,
        "country_id": env.ref("base.do").id,
    })
    env.company.l10_do_can_validate_rnc = True
    res = Partner.name_create(_FAKE_RNC_EXISTING)
    assert res[0] == existing.id, f"esperaba el contacto existente {existing.id}, obtuve {res[0]}"
    return res

run("CASO 4: quick-create con RNC ya registrado (reusa el contacto)", caso4)

# CASO 5: versión pre-fix inyectada a mano, para demostrar el crash original.
if os.environ.get("SHOW_BROKEN") == "true":
    def broken_name_create(self, name):
        if self.env.registry.in_test_mode():          # eliminado en v19
            return super(type(self), self).name_create(name)
        if self._rec_name and isinstance(name, str) and name.isdigit():
            partner = self.search([("vat", "=", name)])
            if partner:
                return partner.name_get()[0]          # eliminado en v17
            return self.create({"vat": name}).name_get()[0]
        return super(type(self), self).name_create(name)

    print("\n" + "=" * 64)
    print(" CASO 5: código PRE-FIX (19.0.1.0.3) — se espera AttributeError")
    print("=" * 64)
    with patch.object(type(Partner), "name_create", broken_name_create):
        try:
            Partner.name_create("Contacto Prueba")
            print(" >>> INESPERADO: la versión pre-fix no falló")
        except AttributeError:
            print(" Traza original reproducida:")
            traceback.print_exc(file=sys.stdout)
    env.cr.rollback()

print("\n" + "=" * 64)
if failures:
    print(" RESULTADO: BUG PRESENTE — casos que fallan: " + ", ".join(failures))
else:
    print(" RESULTADO: SIN ERROR — name_create funciona en los 4 caminos.")
print("=" * 64)
PYEOF

STATUS=$?

if ! $KEEP_DB && ! $SKIP_INSTALL; then
  echo "→ Eliminando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME'\" >/dev/null 2>&1
    PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME
  " || true
else
  echo "→ DB conservada: $DB_NAME (usa --skip-install para re-ejecutar sin reinstalar)"
fi

exit $STATUS
