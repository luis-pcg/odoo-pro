#!/bin/bash
# replicate_input_type_domain_error.sh
#
# Crea una base de datos limpia con el flujo de la rama
# 19.0-feat-l10n_do_gamification_hr_news-01-lf (l10n_do_gamification_hr_news +
# account_payment_compensation_news, como en staging) y reproduce el error del
# cliente web:
#
#   InvalidDomainError: Invalid domain representation: false
#
# al abrir un "Tipo de novedad" y hacer clic en el campo "Tipo de entrada"
# (input_type_id). La causa: account_payment_compensation_news define
# input_type_id_domain como fields.Json y su compute asigna [] cuando
# is_compensation_new es False; fields.Json convierte [] (falsy) a NULL en
# cache y lo devuelve como False al cliente web, que hace new Domain(false).
#
# Uso:
#   ./replicate_input_type_domain_error.sh                 # crea DB, instala, reproduce
#   ./replicate_input_type_domain_error.sh --keep          # no borra la DB al terminar
#   ./replicate_input_type_domain_error.sh --db=mi_db      # nombre de DB personalizado
#   ./replicate_input_type_domain_error.sh --skip-install  # DB ya instalada, solo reproduce
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="l10n_do_gamification_hr_news,account_payment_compensation_news"

DB_NAME="test_input_type_domain"
KEEP_DB=false
SKIP_INSTALL=false
for arg in "$@"; do
  case "$arg" in
    --keep)         KEEP_DB=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    --db=*)         DB_NAME="${arg#--db=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

echo "======================================================"
echo " Replicar InvalidDomainError en input_type_id"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo " Módulos    : $MODULES"
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

echo "→ Reproduciendo el flujo del formulario (web_read / onchange)..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 2>/dev/null
" <<'PYEOF'
import json

NewsType = env['l10n.do.hr.news.type']

# Mismo payload que pide el cliente web al abrir el form
# (el widget many2one evalúa domain="input_type_id_domain" con este valor).
SPEC = {
    'name': {},
    'is_compensation_new': {},
    'input_type_id_domain': {},
    'input_type_id': {'fields': {'display_name': {}}},
}

failures = []

print('\n' + '=' * 64)
print(' CASO 1: editar tipo de novedad existente (flujo de la rama)')
print('=' * 64)
nt = env.ref('l10n_do_gamification_hr_news.news_type_gamification_reward',
             raise_if_not_found=False) or NewsType.search([], limit=1)
vals = nt.web_read(SPEC)[0]
dom = vals['input_type_id_domain']
print(f' Tipo de novedad     : {vals["name"]} (id={nt.id})')
print(f' is_compensation_new : {vals["is_compensation_new"]}')
print(f' input_type_id_domain: {dom!r}')
if dom is False:
    failures.append('web_read en registro existente')
    print(' >>> ERROR REPRODUCIDO: el cliente recibe false y hace')
    print(' >>> new Domain(false) -> InvalidDomainError')

print('\n' + '=' * 64)
print(' CASO 2: crear tipo de novedad nuevo (onchange inicial del form)')
print('=' * 64)
res = NewsType.onchange({}, [], SPEC)
dom_new = res['value'].get('input_type_id_domain', '<sin valor>')
print(f' onchange -> input_type_id_domain: {dom_new!r}')
if dom_new is False:
    failures.append('onchange en registro nuevo')
    print(' >>> ERROR REPRODUCIDO: mismo false en modo creación')

print('\n' + '=' * 64)
print(' CASO 3: marcar is_compensation_new (rama del compute con dominio)')
print('=' * 64)
res2 = NewsType.onchange({'is_compensation_new': True},
                         ['is_compensation_new'], SPEC)
dom_comp = res2['value'].get('input_type_id_domain', '<sin cambio>')
print(f' onchange -> input_type_id_domain: {dom_comp!r}')

print('\n' + '=' * 64)
if failures:
    print(' RESULTADO: BUG PRESENTE — casos que devuelven false: '
          + ', '.join(failures))
else:
    print(' RESULTADO: SIN ERROR — el dominio siempre llega como lista.')
print('=' * 64)
PYEOF

STATUS=$?

if ! $KEEP_DB && ! $SKIP_INSTALL; then
  echo "→ Eliminando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME" || true
else
  echo "→ DB conservada: $DB_NAME (usa --skip-install para re-ejecutar sin reinstalar)"
fi

exit $STATUS
