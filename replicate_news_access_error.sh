#!/bin/bash
# replicate_news_access_error.sh
#
# Crea una base de datos limpia, instala el módulo l10n_do_hr_payroll_news y
# reproduce el error de acceso al campo "structure_type_id" en hr.employee
# cuando un usuario SIN el grupo "Nómina / Oficial"
# (hr_payroll.group_hr_payroll_user) abre las "novedades" (l10n.do.hr.news).
#
# Uso:
#   ./replicate_news_access_error.sh                 # crea DB, instala, reproduce
#   ./replicate_news_access_error.sh --keep          # no borra la DB al terminar
#   ./replicate_news_access_error.sh --db=mi_db      # nombre de DB personalizado
#   ./replicate_news_access_error.sh --skip-install  # DB ya instalada, solo reproduce
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="l10n_do_hr_payroll_news"

DB_NAME="test_news_repro"
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
echo " Replicar error de acceso — $MODULE"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo "======================================================"

# ── Helper: ejecuta dentro del contenedor con retry de conexión a Postgres ──
# Docker Desktop en macOS agota puertos efímeros bajo carga ("Cannot assign
# requested address"); reintentamos hasta que Postgres responda.
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

  echo "→ Instalando $MODULE (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULE --stop-after-init --without-demo=False \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando el módulo' >&2; exit 1; }
fi

echo "→ Sembrando datos y reproduciendo el error con un usuario restringido..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 2>/dev/null
" <<'PYEOF'
import traceback

# 1. Usuario SIN el grupo Nómina/Oficial (group_hr_payroll_user).
#    Solo tiene el grupo de novedades, igual que el empleado que reportó el bug.
user = env['res.users'].create({
    'name': 'Usuario Novedades',
    'login': 'usuario_novedades_repro',
    'email': 'usuario_novedades_repro@example.com',
    'group_ids': [(6, 0, [
        env.ref('base.group_user').id,
        env.ref('l10n_do_hr_news.group_news_user').id,
    ])],
})

# 2. Tipo de estructura salarial con esquema quincenal/semi-mensual.
st = env['hr.payroll.structure.type'].create(
    {'name': 'Repro Semi-Monthly', 'default_schedule_pay': 'semi-monthly'})

# 3. Empleado con ese structure_type_id (campo restringido a Nómina/Oficial).
emp = env['hr.employee'].create(
    {'name': 'Empleado Repro', 'structure_type_id': st.id})

# 4. Novedad propia del usuario (user_id) para pasar la regla "Personal News"
#    de group_news_user y llegar al cómputo que lee structure_type_id.
nt = env['l10n.do.hr.news.type'].create({'name': 'Tipo Repro'})
news = env['l10n.do.hr.news'].create({
    'name': 'Novedad Repro',
    'employee_id': emp.id,
    'news_type_id': nt.id,
    'user_id': user.id,
})
env.cr.commit()

print('\n' + '=' * 60)
print(' Leyendo "novedades" como:', user.name, '(login=%s)' % user.login)
print(' Grupos del usuario:')
for g in user.group_ids.sorted('name'):
    print('   -', g.full_name)
print('=' * 60)

news_u = news.with_user(user)
news_u.invalidate_recordset(['l10n_do_employee_semi_or_biweekly'])
try:
    valor = news_u.l10n_do_employee_semi_or_biweekly
    print('\n>>> SIN ERROR. l10n_do_employee_semi_or_biweekly =', valor)
    print('>>> El fix (sudo) está aplicado o el usuario tiene acceso.')
except Exception as e:
    print('\n>>> ERROR REPRODUCIDO:')
    print('>>>', type(e).__name__)
    print(traceback.format_exc())
PYEOF

STATUS=$?

if ! $KEEP_DB && ! $SKIP_INSTALL; then
  echo "→ Eliminando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME" || true
else
  echo "→ DB conservada: $DB_NAME (usa --skip-install para re-ejecutar sin reinstalar)"
fi

exit $STATUS
