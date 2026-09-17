#!/usr/bin/env bash
# Reproduce: AttributeError: 'NoneType' object has no attribute 'groupdict'
#            account_reports/models/account_report.py::_aggregation_apply_bounds
#
# Causa: una account.report.expression con engine='aggregation' cuyo subformula no es
# ninguno de los aceptados (vacio | ignore_zero_division | cross_report* | round(...) |
# if_above/if_below/if_between(CUR(x))). El re.match devuelve None y el codigo no valida.
#
# Caso tipico: en la UI se cambia el engine de la expresion (domain -> aggregation) y el
# subformula viejo ('-sum') se queda pegado.
#
# Uso: ./replicate_bs_aggregation_bounds.sh [db]     (por defecto repro_bs_agg)
set -euo pipefail

DB="${1:-repro_bs_agg}"
CONTAINER="${CONTAINER:-lfernandez_v19}"
DB_HOST="${DB_HOST:-odoo-db}"
DB_USER="${DB_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
ODOO_DB_FLAGS="--db_host=$DB_HOST --db_user=$DB_USER --db_password=$DB_PASS"

if ! docker exec "$DB_HOST" psql -U "$DB_USER" -lqt | cut -d'|' -f1 | grep -qw "$DB"; then
    echo "=== creando $DB con l10n_do_reports ==="
    docker exec "$CONTAINER" odoo -d "$DB" -i l10n_do_reports --without-demo=all \
        --stop-after-init --no-http $ODOO_DB_FLAGS 2>&1 | tail -3
fi

echo "=== reproduciendo en $DB ==="
docker exec -i "$CONTAINER" odoo shell -d "$DB" --no-http --log-level=warn $ODOO_DB_FLAGS <<'PY' 2>&1 | grep -v "invalid addons directory"
import traceback
report = env.ref('l10n_do_reports.l10n_do_bs')

def render(tag):
    env.invalidate_all()
    try:
        lines = report._get_lines(report.get_options({}))
        print(f"[{tag}] OK  lines={len(lines)}")
    except Exception as e:
        print(f"[{tag}] FAIL {type(e).__name__}: {e}")
        traceback.print_exc()

render("baseline (datos estandar)")

# La UI no limpia subformula al cambiar el engine de domain a aggregation
expr = env.ref('l10n_do_reports.l10n_do_bs_equity_3_balance_aggregate')
expr.write({
    'engine': 'aggregation',
    'formula': 'l10n_do_bs_equity_3.balance_account_codes',
    'subformula': '-sum',
})
render("aggregation + '-sum'")

for sf in ('sum', 'if_above(0)', 'if_above(dop(0))', 'if_above(DOP(0)'):
    expr.subformula = sf
    render(f"aggregation + {sf!r}")

env.cr.rollback()
print("rollback hecho; la DB queda intacta")
PY
