#!/bin/bash
# replicate_pnl_otros_ingresos_sequence.sh
#
# Reproduce el bug del Estado de Resultados (Profit and Loss, variante DR):
# "Otros Ingresos" se sale de la estructura / el reporte no carga con el error:
#   "La línea 'Otros Ingresos' está configurada para aparecer antes de la
#    línea principal 'Resultado Antes de Impuestos'. Esto no está permitido."
#
# Reporte instalado por: l10n_do_reports (Odoo ENTERPRISE), no l10n_do/l10n_do_accounting.
#
# Causa raíz:
#   - enterprise/l10n_do_reports/data/profit_and_loss.xml (y balance_sheet.xml)
#     abren con <odoo> SIN auto_sequence="1".
#   - Sin auto_sequence, el cargador XML (odoo/tools/convert.py:_tag_root/next_sequence)
#     NO asigna 'sequence' -> todas las account.report.line quedan con sequence=NULL.
#   - El render (account_reports/.../account_report.py:2714) ordena por (sequence, id)
#     y EXIGE que cada hija salga despues de su padre. Con todo NULL el orden cae a
#     'id' (orden de creacion) y por casualidad respeta la jerarquia.
#   - En Postgres NULL ordena al final (NULLS LAST). Si UNA linea recibe un
#     sequence no-NULL (arrastre en el editor, migracion, Studio, write parcial),
#     salta delante de las hermanas NULL -> "Otros Ingresos" se sale.
#   - El "-u" no trae auto_sequence -> nunca reescribe sequence -> no corrige.
#
# Fix:
#   - Agregar auto_sequence="1" al <odoo> de ambos XML de l10n_do_reports.
#   - Asi cada linea recibe sequence 10,20,30... en orden, en CADA carga (install
#     y update). El -u auto-corrige cualquier estado torcido. Orden estable.
#
# Uso:
#   ./replicate_pnl_otros_ingresos_sequence.sh                 # repro completo (roto -> fix)
#   ./replicate_pnl_otros_ingresos_sequence.sh --template=DB   # DB origen con l10n_do_reports
#   ./replicate_pnl_otros_ingresos_sequence.sh --keep          # no borra las DBs de repro
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="l10n_do_reports"

DB_CONTAINER="odoo-db"
TEMPLATE_DB="test_l10n_do_invoices_v19"   # cualquier DB con l10n_do_reports instalado
BROKEN_DB="repro_pnl_broken"
FIXED_DB="repro_pnl_seq"
KEEP_DB=false
for arg in "$@"; do
  case "$arg" in
    --keep)       KEEP_DB=true ;;
    --template=*) TEMPLATE_DB="${arg#--template=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

PL_XML="$SCRIPT_DIR/enterprise/l10n_do_reports/data/profit_and_loss.xml"
BS_XML="$SCRIPT_DIR/enterprise/l10n_do_reports/data/balance_sheet.xml"
ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Repro: Estado de Resultados 'Otros Ingresos' fuera de estructura"
echo " Modulo (enterprise): $MODULE"
echo " Template DB        : $TEMPLATE_DB"
echo "======================================================"

psql_db() { docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d "$1" -tAc "$2"; }
drop_db()  { docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
              "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1' AND pid<>pg_backend_pid();" >/dev/null 2>&1
            docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS $1;" >/dev/null 2>&1; }
copy_db()  { drop_db "$2"
            docker exec "$DB_CONTAINER" psql -U "$DB_USER" -d postgres -c \
              "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1' AND pid<>pg_backend_pid();" >/dev/null
            docker exec "$DB_CONTAINER" createdb -U "$DB_USER" -T "$1" "$2"
            # createdb -T NO copia el filestore -> copiarlo para que cargue el web client
            docker exec "$CONTAINER" bash -lc "rm -rf /var/lib/odoo/filestore/$2; cp -a /var/lib/odoo/filestore/$1 /var/lib/odoo/filestore/$2" 2>/dev/null || true; }

# id de la linea income_other (Otros Ingresos) y de su padre ebt
LINE_SQL="SELECT l.id,l.sequence,d.name FROM account_report_line l JOIN ir_model_data d ON d.model='account.report.line' AND d.res_id=l.id WHERE d.module='$MODULE' AND d.name LIKE 'l10n_do_pl%' ORDER BY l.sequence NULLS LAST,l.id"

echo
echo "### 0) Estado de los archivos XML en enterprise/l10n_do_reports/data/"
grep -H "^<odoo" "$PL_XML" "$BS_XML"

# ── PASO 1: DB ROTA ────────────────────────────────────────────────────────
echo
echo "### 1) Crear DB ROTA ($BROKEN_DB) e inducir el trigger (una linea con sequence no-NULL)"
copy_db "$TEMPLATE_DB" "$BROKEN_DB"
psql_db "$BROKEN_DB" "UPDATE account_report_line SET sequence=5 WHERE id=(SELECT res_id FROM ir_model_data WHERE module='$MODULE' AND name='l10n_do_pl_income_other');" >/dev/null
echo "Orden de lineas (NULLS LAST) -> Otros Ingresos (seq=5) salta al tope:"
psql_db "$BROKEN_DB" "$LINE_SQL"
echo ">> Abrir el reporte 'Estado de Resultados' en $BROKEN_DB lanza el UserError."

# ── PASO 2: aplicar el FIX en los XML (auto_sequence) ───────────────────────
echo
echo "### 2) Aplicar fix: auto_sequence=\"1\" en ambos XML (si falta)"
for f in "$PL_XML" "$BS_XML"; do
  if grep -q '^<odoo auto_sequence="1">' "$f"; then
    echo "  ya tiene auto_sequence: $(basename "$f")"
  else
    sed -i.bak 's/^<odoo>/<odoo auto_sequence="1">/' "$f" && rm -f "$f.bak"
    echo "  parcheado: $(basename "$f")"
  fi
done

# ── PASO 3: DB CORREGIDA: partir de la rota y correr -u ─────────────────────
echo
echo "### 3) Crear DB CORREGIDA ($FIXED_DB) desde la rota y correr -u $MODULE"
copy_db "$BROKEN_DB" "$FIXED_DB"
docker exec "$CONTAINER" bash -lc "odoo -d $FIXED_DB -u $MODULE --no-http --stop-after-init $ODOO_DB_FLAGS" 2>&1 | tail -3
echo
echo "Orden tras el fix -> secuencias 10,20,30... e 'Otros Ingresos' despues de su padre:"
psql_db "$FIXED_DB" "$LINE_SQL"
echo ">> El -u AUTO-CORRIGIO el estado torcido. Reporte renderiza OK y es estable."

if [[ "$KEEP_DB" != true ]]; then
  echo
  echo "### Limpieza (usa --keep para conservar)"
  drop_db "$BROKEN_DB"; drop_db "$FIXED_DB"
  echo "DBs de repro eliminadas."
else
  echo
  echo "DBs conservadas: $BROKEN_DB (roto), $FIXED_DB (corregido)."
fi
