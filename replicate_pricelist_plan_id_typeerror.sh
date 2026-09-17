#!/bin/bash
# replicate_pricelist_plan_id_typeerror.sh
#
# Reproduce el error reportado en adm-19.iterativo.do (tarea #74280):
#
#   TypeError: PricelistItem._compute_base_price() got an unexpected keyword
#   argument 'plan_id'
#
# Causa: sale_subscription (enterprise) extiende
#   product.pricelist.item._compute_base_price(..., *, plan_id=None, **kwargs)
# y SIEMPRE reenvia plan_id al super(). product_foreign_cost_price declaraba
# el mismo metodo SIN **kwargs, asi que al quedar debajo de sale_subscription
# en el MRO reventaba cualquier calculo de precio que no fuera 'fixed'.
#
# El script corre el mismo escenario dos veces:
#   [A] con la firma ANTERIOR (sin **kwargs) -> debe fallar
#   [B] con el codigo actual del working tree -> debe pasar
#
# Uso:
#   ./replicate_pricelist_plan_id_typeerror.sh
#   ./replicate_pricelist_plan_id_typeerror.sh --db=otra_db
#   ./replicate_pricelist_plan_id_typeerror.sh --keep   # no recrea la DB
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_CONTAINER="odoo-db"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

DB="repro_plan_id"
KEEP=false
for arg in "$@"; do
  case "$arg" in
    --db=*) DB="${arg#--db=}" ;;
    --keep) KEEP=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"
TARGET="$SCRIPT_DIR/odoo-pro/product_foreign_cost_price/models/product_pricelist.py"
BACKUP="$(mktemp -t pfcp_backup)"
PAYLOAD="$(mktemp -t pfcp_payload)"

cleanup() {
  if [[ -s "$BACKUP" ]]; then
    cp "$BACKUP" "$TARGET"
  fi
  rm -f "$BACKUP" "$PAYLOAD"
}
trap cleanup EXIT

echo "======================================================"
echo " Repro: _compute_base_price() unexpected kwarg 'plan_id'"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB"
echo "======================================================"

if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: contenedor '$CONTAINER' no esta corriendo. Corre: docker-compose up -d" >&2
  exit 1
fi

db_exists() {
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT 1 FROM pg_database WHERE datname = '$DB'" 2>/dev/null | grep -q 1
}

if db_exists && [[ "$KEEP" == "false" ]]; then
  echo "[1/3] Borrando DB previa '$DB'..."
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -tAc \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB' AND pid <> pg_backend_pid()" >/dev/null 2>&1
  docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$DB" >/dev/null 2>&1
fi

if ! db_exists; then
  echo "[1/3] Instalando sale_subscription + product_foreign_cost_price en '$DB' (sin demo)..."
  docker exec "$CONTAINER" odoo -d "$DB" $ODOO_DB_FLAGS \
    --http-port=8070 --no-http --log-level=warn --stop-after-init \
    --without-demo=all -i sale_subscription,product_foreign_cost_price \
    > /tmp/${DB}_install.log 2>&1
  if [[ $? -ne 0 ]]; then
    echo "ERROR instalando. Ultimas lineas:" >&2; tail -30 /tmp/${DB}_install.log >&2; exit 1
  fi
else
  echo "[1/3] Reusando DB existente '$DB' (--keep)."
fi

cat > "$PAYLOAD" <<'PYEOF'
import traceback

from odoo import Command

MRO = [
    c.__module__ for c in type(env["product.pricelist.item"]).__mro__
    if "_compute_base_price" in c.__dict__
]
print("MRO _compute_base_price: %s" % MRO)

company = env.company
partner = env["res.partner"].create({"name": "REPRO Cliente Pilar"})

plan = env["sale.subscription.plan"].create({
    "name": "REPRO Mensual",
    "billing_period_value": 1,
    "billing_period_unit": "month",
})

# Producto NO recurrente: reproduce el caso de Sharling (producto inmobiliario).
lote = env["product.product"].create({
    "name": "Desarrollo Coral Lote H-201",
    "type": "consu",
    "list_price": 1500000.0,
})

# Producto recurrente: aqui plan_id SI viaja con valor en los kwargs.
suscripcion = env["product.product"].create({
    "name": "REPRO Servicio Recurrente",
    "type": "service",
    "list_price": 5000.0,
    "recurring_invoice": True,
})

# Lista de precios con regla 'formula' (compute_price != 'fixed' es lo que
# obliga a pasar por _compute_base_price).
pricelist = env["product.pricelist"].create({
    "name": "REPRO Pilar",
    "currency_id": company.currency_id.id,
    "item_ids": [Command.create({
        "applied_on": "3_global",
        "compute_price": "formula",
        "base": "list_price",
        "price_discount": 10.0,
    })],
})

# Lista de precios usando la base propia del modulo (Purchase Price) para
# verificar que la rama currency_standard_price tambien sobrevive.
# La moneda de compra debe diferir de la de la compania, si no la rama de
# conversion no se ejecuta y el escenario no prueba nada.
moneda_compra = env.ref("base.USD")
if moneda_compra == company.currency_id:
    moneda_compra = env.ref("base.EUR")
moneda_compra.active = True
lote.product_tmpl_id.with_company(company).write({
    "currency_standard_price": 1000.0,
    "purchase_currency_id": moneda_compra.id,
})
pricelist_fcp = env["product.pricelist"].create({
    "name": "REPRO Pilar Costo Compra",
    "currency_id": company.currency_id.id,
    "currency_rate_ids": [Command.create({"currency_id": moneda_compra.id, "rate": 60.0})],
    "item_ids": [Command.create({
        "applied_on": "3_global",
        "compute_price": "formula",
        "base": "currency_standard_price",
        "price_discount": 0.0,
    })],
})


def escenario(titulo, product, pl, plan_rec=None):
    # Savepoint en vez de rollback: un rollback completo invalidaria los
    # registros sembrados arriba y los escenarios siguientes reventarian
    # con MissingError en lugar del TypeError que queremos observar.
    try:
        with env.cr.savepoint():
            vals = {"partner_id": partner.id, "pricelist_id": pl.id}
            if plan_rec:
                vals["plan_id"] = plan_rec.id
            order = env["sale.order"].create(vals)
            line = env["sale.order.line"].create({
                "order_id": order.id,
                "product_id": product.id,
                "product_uom_qty": 1,
            })
            precio = line.price_unit
            raise Rollback(precio)
    except Rollback as ok:
        env.invalidate_all()
        print("  %-52s OK    price_unit=%s" % (titulo, ok.args[0]))
        return True
    except TypeError as exc:
        env.invalidate_all()
        print("  %-52s FALLA TypeError: %s" % (titulo, exc))
        return False


class Rollback(Exception):
    pass


print("--- escenarios ---")
resultados = [
    escenario("no recurrente + regla formula", lote, pricelist),
    escenario("no recurrente + base Purchase Price (tasa 60)", lote, pricelist_fcp),
    escenario("recurrente + plan (plan_id con valor)", suscripcion, pricelist, plan),
]
print("VEREDICTO: %s" % ("TODO OK" if all(resultados) else "HAY FALLAS"))
env.cr.rollback()
PYEOF

run_case() {
  local etiqueta="$1"
  echo
  echo "------------------------------------------------------"
  echo " $etiqueta"
  echo "------------------------------------------------------"
  docker exec -i "$CONTAINER" odoo shell -d "$DB" $ODOO_DB_FLAGS \
    --http-port=8070 --no-http --log-level=warn < "$PAYLOAD" 2>&1 \
    | grep -E "^(MRO|--- escenarios|  |VEREDICTO)" 
}

cp "$TARGET" "$BACKUP"

echo "[2/3] Caso A: firma ANTERIOR (sin **kwargs)"
python3 - "$TARGET" <<'PATCHEOF'
import re, sys
path = sys.argv[1]
src = open(path).read()
src = src.replace(
    "def _compute_base_price(self, product, quantity, uom, date, currency, **kwargs):",
    "def _compute_base_price(self, product, quantity, uom, date, currency):",
)
src = src.replace(
    "            return super()._compute_base_price(\n"
    "                product, quantity, uom, date, currency, **kwargs\n"
    "            )",
    "            return super()._compute_base_price(product, quantity, uom, date, currency)",
)
open(path, "w").write(src)
PATCHEOF
grep -n "def _compute_base_price" "$TARGET"
run_case "CASO A - codigo pre-fix (se espera TypeError)"

cp "$BACKUP" "$TARGET"
echo
echo "[3/3] Caso B: codigo actual del working tree"
grep -n "def _compute_base_price" "$TARGET"
run_case "CASO B - codigo actual (se espera OK)"

echo
echo "Listo. Archivo restaurado:"
git -C "$SCRIPT_DIR/odoo-pro" status --short product_foreign_cost_price/
