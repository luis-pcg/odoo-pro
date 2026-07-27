#!/bin/bash
# replicate_withholding_rate_normalization.sh
#
# Valida la migración upgrades/19.0.1.0.2 de l10n_do_account_withholding_tax:
# normalizar las retenciones de ITBIS que quedaron guardadas como porcentaje del
# impuesto (-100 / -75 / -30) a la convención de core l10n_do, que es porcentaje
# de la base (-18 / -13.5 / -5.4).
#
# Dos casos en una sola corrida:
#   CASO A — impuestos que YA estaban en la convención de core → no se tocan
#            ret_100_tax_security  -18.0  → -18.0
#            ret_75_tax_nonformal  -13.5  → -13.5
#            ret_30_tax_moral       -5.4  →  -5.4
#   CASO B — impuestos que un upgrade previo pasó a % del impuesto → se corrigen
#            ret_100_tax_nonprofit -100.0 → -18.0
#            ret_100_tax_person    -100.0 → -18.0
#            ret_30_tax_freelance   -30.0 →  -5.4
#   Control — retenciones de ISR: nunca se tocan (su grupo no tiene impuesto positivo)
#            ret_10_income_person       -10.0 → -10.0
#            ret_27_income_remittance   -27.0 → -27.0
#
# Además:
#   - idempotencia: segunda corrida de la migración no cambia nada
#   - equivalencia funcional: un impuesto del caso A y uno del caso B retienen
#     lo mismo (100% del ITBIS) al registrar el pago
#
# Uso:
#   ./replicate_withholding_rate_normalization.sh              # conserva la DB
#   ./replicate_withholding_rate_normalization.sh --drop-db    # borra la DB al final

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER}_v19"
DB_CONTAINER="odoo-db"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"

BASE_DB="test_wh_repro"          # DB con l10n_do_account_withholding_tax instalado
TEST_DB="test_wh_migration"
MODULE="l10n_do_account_withholding_tax"
PREV_VERSION="19.0.1.0.1"        # versión desde la que se simula el upgrade
DROP_DB=false

for arg in "$@"; do
  [[ "$arg" == "--drop-db" ]] && DROP_DB=true
done

FAILURES=0

psql_db() { docker exec -i "$DB_CONTAINER" psql -U "$DB_USER" -d "$TEST_DB" "$@"; }

run_odoo() {
  docker exec "$CONTAINER" odoo \
    -d "$TEST_DB" \
    --db_host="$DB_HOST" --db_port="$DB_PORT" \
    --db_user="$DB_USER" --db_password="$DB_PASS" \
    --http-port=8076 --no-http --stop-after-init --log-level=warn "$@"
}

echo "======================================================"
echo " Migración de retenciones ITBIS — % del impuesto → % de la base"
echo " Base DB : $BASE_DB"
echo " Test DB : $TEST_DB"
echo "======================================================"

# ─── 1. Clonar DB ────────────────────────────────────────────────────────────
echo ""
echo "[1/6] Clonando $BASE_DB → $TEST_DB"
docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -q -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
    WHERE datname IN ('$BASE_DB','$TEST_DB') AND pid <> pg_backend_pid();" > /dev/null
docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$TEST_DB" > /dev/null 2>&1
docker exec "$DB_CONTAINER" createdb -U "$DB_USER" -T "$BASE_DB" "$TEST_DB" || {
  echo "ERROR: no se pudo clonar $BASE_DB (¿existe?)" >&2; exit 1; }

# ─── 2. Sembrar los dos casos ────────────────────────────────────────────────
echo "[2/6] Sembrando caso A (18%) y caso B (100%)"
psql_db -q <<'SQL'
CREATE TEMP TABLE wh_seed(xmlid text, seeded numeric) ON COMMIT PRESERVE ROWS;
INSERT INTO wh_seed VALUES
    -- CASO A: ya en la convención de core, deben quedarse igual
    ('ret_100_tax_security',      -18.0),
    ('ret_75_tax_nonformal',      -13.5),
    ('ret_30_tax_moral',           -5.4),
    -- CASO B: guardados como % del impuesto, deben volver a % de la base
    ('ret_100_tax_nonprofit',    -100.0),
    ('ret_100_tax_person',       -100.0),
    ('ret_30_tax_freelance',      -30.0),
    -- Control ISR: nunca se tocan
    ('ret_10_income_person',      -10.0),
    ('ret_27_income_remittance',  -27.0);

-- Todas marcadas como retención en el pago, que es lo que hace el paso 1 de la
-- migración en una DB que viene de 17.0.
UPDATE account_tax t
   SET amount                       = s.seeded,
       is_withholding_tax_on_payment = TRUE,
       tax_exigibility               = 'on_invoice',
       price_include_override        = 'tax_excluded'
  FROM wh_seed s
  JOIN ir_model_data d
    ON d.model = 'account.tax' AND d.module = 'account'
   AND d.name ~ ('_' || s.xmlid || '$')
 WHERE t.id = d.res_id;
SQL

echo "       Estado sembrado:"
psql_db -t -A -F$'\t' -c "
SELECT regexp_replace(d.name, '^[0-9]+_', ''), t.amount
  FROM ir_model_data d
  JOIN account_tax t ON t.id = d.res_id
 WHERE d.model = 'account.tax' AND d.module = 'account'
   AND t.is_withholding_tax_on_payment = TRUE
 ORDER BY 1;" | sed 's/^/         /'

# ─── 3. Forzar el upgrade del módulo ─────────────────────────────────────────
echo "[3/6] Fijando $MODULE en $PREV_VERSION y corriendo el upgrade"
psql_db -q -c "UPDATE ir_module_module SET latest_version = '$PREV_VERSION' WHERE name = '$MODULE';"
run_odoo -u "$MODULE,l10n_do_accounting" 2>&1 | grep -Ei "CRITICAL|Traceback" | head -5

# ─── 4. Validar los dos casos ────────────────────────────────────────────────
echo "[4/6] Validando resultados"
RESULTS=$(psql_db -t -A -F$'\t' <<'SQL'
WITH expected(caso, xmlid, seeded, esperado) AS (
    VALUES ('A  18% se queda en 18%',  'ret_100_tax_security',      -18.0,  -18.0),
           ('A  75% se queda en 13.5', 'ret_75_tax_nonformal',      -13.5,  -13.5),
           ('A  30% se queda en 5.4',  'ret_30_tax_moral',           -5.4,   -5.4),
           ('B  100 → 18',             'ret_100_tax_nonprofit',    -100.0,  -18.0),
           ('B  100 → 18',             'ret_100_tax_person',       -100.0,  -18.0),
           ('B  30 → 5.4',             'ret_30_tax_freelance',      -30.0,   -5.4),
           ('C  ISR intacto',          'ret_10_income_person',      -10.0,  -10.0),
           ('C  ISR intacto',          'ret_27_income_remittance',  -27.0,  -27.0)
)
SELECT CASE WHEN ROUND(t.amount::numeric, 4) = ROUND(e.esperado::numeric, 4)
            THEN 'PASS' ELSE 'FAIL' END,
       e.caso, e.xmlid, e.seeded, e.esperado, t.amount
  FROM expected e
  JOIN ir_model_data d
    ON d.model = 'account.tax' AND d.module = 'account'
   AND d.name ~ ('_' || e.xmlid || '$')
  JOIN account_tax t ON t.id = d.res_id
 ORDER BY e.caso, e.xmlid;
SQL
)
printf '       %-6s %-24s %-26s %10s %10s %10s\n' STATUS CASO IMPUESTO SEMBRADO ESPERADO REAL
while IFS=$'\t' read -r status caso xmlid seeded esperado real; do
  [[ -z "$status" ]] && continue
  printf '       %-6s %-24s %-26s %10s %10s %10s\n' "$status" "$caso" "$xmlid" "$seeded" "$esperado" "$real"
  [[ "$status" == "FAIL" ]] && FAILURES=$((FAILURES + 1))
done <<< "$RESULTS"

# ─── 5. Idempotencia ─────────────────────────────────────────────────────────
echo "[5/6] Idempotencia: segunda corrida de la migración"
BEFORE=$(psql_db -t -A -c "SELECT COALESCE(SUM(amount), 0) FROM account_tax WHERE is_withholding_tax_on_payment = TRUE;")
psql_db -q -c "UPDATE ir_module_module SET latest_version = '$PREV_VERSION' WHERE name = '$MODULE';"
run_odoo -u "$MODULE" 2>&1 | grep -Ei "CRITICAL|Traceback" | head -5
AFTER=$(psql_db -t -A -c "SELECT COALESCE(SUM(amount), 0) FROM account_tax WHERE is_withholding_tax_on_payment = TRUE;")
if [[ "$BEFORE" == "$AFTER" ]]; then
  echo "       PASS   suma de tasas sin cambios ($BEFORE)"
else
  echo "       FAIL   suma de tasas cambió: $BEFORE → $AFTER"
  FAILURES=$((FAILURES + 1))
fi

# ─── 6. Equivalencia funcional en el registro de pago ────────────────────────
echo "[6/6] Registro de pago: caso A y caso B deben retener lo mismo"
FUNC=$(docker exec -i "$CONTAINER" odoo shell \
  -d "$TEST_DB" \
  --db_host="$DB_HOST" --db_port="$DB_PORT" \
  --db_user="$DB_USER" --db_password="$DB_PASS" \
  --no-http --log-level=error <<'PY' 2>&1
from odoo import fields

partner = env['res.partner'].create({
    'name': 'WH Migration Vendor', 'vat': '131793916',
    'l10n_do_dgii_tax_payer_type': 'taxpayer', 'country_id': env.ref('base.do').id})
itbis = env.ref('account.%s_tax_18_purch' % env.company.id)

def ref(xmlid):
    return env.ref('account.%s_%s' % (env.company.id, xmlid))

for index, (caso, xmlid) in enumerate([('A', 'ret_100_tax_security'),
                                       ('B', 'ret_100_tax_person')]):
    wh = ref(xmlid)
    bill = env['account.move'].create({
        'move_type': 'in_invoice', 'partner_id': partner.id,
        'invoice_date': fields.Date.today(),
        'l10n_latam_document_number': 'B010000000%d' % (index + 1),
        'invoice_line_ids': [(0, 0, {
            'name': 'srv', 'quantity': 1, 'price_unit': 1000.0,
            'tax_ids': [(6, 0, [itbis.id, wh.id])]})]})
    bill.action_post()
    wiz = env['account.payment.register'].with_context(
        active_model='account.move', active_ids=bill.ids).create({})
    line = wiz.withholding_line_ids.filtered(lambda line: line.tax_id == wh)
    print('FUNC\t%s\t%s\t%s\t%s\t%s' % (
        caso, xmlid, wh.amount, line.base_amount, line.amount))

env.cr.rollback()
PY
)
FUNC_LINES=0
while IFS=$'\t' read -r tag caso xmlid amount base withheld; do
  [[ "$tag" != "FUNC" ]] && continue
  FUNC_LINES=$((FUNC_LINES + 1))
  # base = ITBIS de una factura de 1.000 → 180; retención esperada = 100% del ITBIS
  if [[ "$base" == "180.0" && "$withheld" == "180.0" ]]; then
    printf '       PASS   caso %s  %-22s amount=%-7s base=%-7s retenido=%s\n' \
      "$caso" "$xmlid" "$amount" "$base" "$withheld"
  else
    printf '       FAIL   caso %s  %-22s amount=%-7s base=%-7s retenido=%s (esperado 180.0 / 180.0)\n' \
      "$caso" "$xmlid" "$amount" "$base" "$withheld"
    FAILURES=$((FAILURES + 1))
  fi
done <<< "$FUNC"
# Cobertura: si un caso no llegó a imprimir, el shell murió antes — no es un pase.
if [[ "$FUNC_LINES" -ne 2 ]]; then
  echo "       FAIL   se esperaban 2 casos funcionales, llegaron $FUNC_LINES. Salida del shell:"
  echo "$FUNC" | grep -v $'^FUNC\t' | tail -8 | sed 's/^/              /'
  FAILURES=$((FAILURES + 1))
fi

# ─── Cierre ──────────────────────────────────────────────────────────────────
echo ""
if [[ "$DROP_DB" == "true" ]]; then
  docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -q -c \
    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
      WHERE datname = '$TEST_DB' AND pid <> pg_backend_pid();" > /dev/null
  docker exec "$DB_CONTAINER" dropdb -U "$DB_USER" --if-exists "$TEST_DB"
  echo "DB $TEST_DB borrada."
else
  echo "DB $TEST_DB conservada."
fi

echo "======================================================"
if [[ "$FAILURES" -eq 0 ]]; then
  echo " RESULTADO: TODO PASÓ"
else
  echo " RESULTADO: $FAILURES validación(es) FALLARON"
fi
echo "======================================================"
exit $(( FAILURES > 0 ? 1 : 0 ))
