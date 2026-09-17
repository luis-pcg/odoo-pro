#!/bin/bash
# replicate_input_type_country_rule.sh
#
# Replica el AccessError de TISSAGE tras migrar a 19.0:
#
#   Estos registros estan restringidos.
#   Administrator (id=2) no tiene acceso 'leer' a:
#   - Tipo de entrada del recibo de nomina, Salario Real (...) (hr.payslip.input.type: 6)
#   Las siguientes reglas son responsables:
#   - HR Payslip Input Type: Multi Company
#
# Hipotesis a validar: los hr.payslip.input.type de l10n_do_hr_payroll NO fijan
# country_id en el data XML; el campo usa default=lambda: self.env.company.country_id.
# Si el modulo se instala cuando la compania todavia NO tiene pais Republica
# Dominicana, los registros quedan con el pais de ese momento (p.ej. US) y la
# regla global hr_payroll.ir_rule_hr_payslip_input_type_multi_company
#   ['|', ('country_id','=',False), ('country_id','in', user.env.companies.mapped('country_id').ids)]
# los oculta para siempre, aunque despues se ponga el pais RD.
#
# Escenario A (bug):  pais US al instalar -> input types con country US -> AccessError
# Escenario B (sano): pais RD al instalar -> input types con country RD -> sin error
#
# Uso:
#   ./replicate_input_type_country_rule.sh                # crea las 2 DBs y compara
#   ./replicate_input_type_country_rule.sh --recreate     # borra y recrea si existen
#   ./replicate_input_type_country_rule.sh --skip-install # DBs ya instaladas, solo diagnostica
#   ./replicate_input_type_country_rule.sh --only=A|B     # un solo escenario
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULE="l10n_do_hr_payroll"

DB_A="repro_input_type_country_us"
DB_B="repro_input_type_country_do"
RECREATE=false
SKIP_INSTALL=false
ONLY=""
for arg in "$@"; do
  case "$arg" in
    --recreate)     RECREATE=true ;;
    --skip-install) SKIP_INSTALL=true ;;
    --only=*)       ONLY="${arg#--only=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

wait_for_db() {
  docker exec "$CONTAINER" bash -lc "
    for i in \$(seq 1 30); do
      if PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c 'SELECT 1' >/dev/null 2>&1; then exit 0; fi
      sleep 2
    done
    echo 'ERROR: Postgres no respondio' >&2; exit 1
  "
}

db_exists() {
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"SELECT 1 FROM pg_database WHERE datname='$1'\"" \
    | grep -q 1
}

drop_db() {
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
      \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1'\" >/dev/null
    PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $1
  "
}

# $1 = db, $2 = codigo de pais a poner ANTES de instalar el modulo
build_db() {
  local db="$1" country="$2"
  if db_exists "$db"; then
    if $RECREATE; then
      echo "→ Borrando $db..."; drop_db "$db"
    else
      echo "ERROR: la DB $db ya existe. Usa --recreate o --skip-install." >&2; return 1
    fi
  fi

  echo "→ [$db] creando DB e instalando base..."
  docker exec "$CONTAINER" bash -lc \
    "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $db" || return 1
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $db $ODOO_DB_FLAGS -i base --stop-after-init \
      --without-demo=all --max-cron-threads=0 --workers=0 --log-level=warn
  " || return 1

  echo "→ [$db] pais de la compania = $country (ANTES de instalar $MODULE)"
  docker exec -i "$CONTAINER" bash -lc "
    odoo shell -c /etc/odoo/odoo.conf -d $db $ODOO_DB_FLAGS \
      --no-http --max-cron-threads=0 --workers=0 --log-level=warn
  " <<PYEOF || return 1
env.company.country_id = env.ref('base.${country}')
print('compania:', env.company.name, '->', env.company.country_id.name)
env.cr.commit()
PYEOF

  echo "→ [$db] instalando $MODULE (varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $db $ODOO_DB_FLAGS -i $MODULE --stop-after-init \
      --without-demo=all --max-cron-threads=0 --workers=0 --log-level=warn
  " || return 1
}

# $1 = db
diagnose() {
  local db="$1"
  docker exec -i "$CONTAINER" bash -lc "
    odoo shell -c /etc/odoo/odoo.conf -d $db $ODOO_DB_FLAGS \
      --no-http --max-cron-threads=0 --workers=0 --log-level=warn
  " <<'PYEOF'
import logging
logging.disable(logging.WARNING)
from odoo.exceptions import AccessError

def line(c='='): print(c * 78)

# El cliente puso el pais RD DESPUES (configuracion de la compania)
do = env.ref('base.do')
if env.company.country_id != do:
    env.company.country_id = do
    print('→ pais de la compania cambiado a Republica Dominicana (post-instalacion)')

ITypeSu = env['hr.payslip.input.type'].sudo()
types = ITypeSu.with_context(active_test=False).search([])
hist = {}
for t in types:
    hist.setdefault(t.country_id.name or 'False', []).append(t.id)

line()
print('DB          :', env.cr.dbname)
print('Compania    :', env.company.name, '/ pais:', env.company.country_id.name)
print('Input types :', len(types))
for k, v in hist.items():
    print('   country=%-22s %3d registros (ids %s..%s)' % (k, len(v), min(v), max(v)))

# regla responsable
rule = env.ref('hr_payroll.ir_rule_hr_payslip_input_type_multi_company')
print('Regla       :', rule.name, '| activa:', rule.active)
print('domain      :', rule.domain_force)

# lectura como Administrator (uid 2), SIN sudo -> es lo que hace el cliente web
admin_env = env(user=2, su=False)
IType = admin_env['hr.payslip.input.type']
visible = IType.with_context(active_test=False).search([])
blocked = [t for t in types if t.id not in set(visible.ids)]
print('Visibles para Administrator :', len(visible))
print('Bloqueados por la regla     :', len(blocked))

line('-')
ref_override = env.ref('l10n_do_hr_payroll.hr_payslip_input_type_override', raise_if_not_found=False)
if ref_override:
    print("l10n_do_hr_payroll.hr_payslip_input_type_override -> id %s, country %s"
          % (ref_override.id, ref_override.sudo().country_id.name))
    try:
        IType.browse(ref_override.id).read(['name', 'code'])
        print('READ como Administrator: OK (sin error)')
    except AccessError as e:
        print('READ como Administrator: AccessError ->')
        for l in str(e).splitlines():
            print('   ', l)

line('-')
# camino real del error en la UI: la estructura enlaza los input types ocultos
struct = env.ref('l10n_do_hr_payroll.hr_payroll_structure_base', raise_if_not_found=False)
if struct:
    su_ids = struct.sudo().input_line_type_ids.ids
    adm_ids = struct.with_env(admin_env).input_line_type_ids.ids
    print('Estructura  :', struct.sudo().name)
    print('   input_line_type_ids con sudo         :', len(su_ids))
    print('   input_line_type_ids como Administrator:', len(adm_ids))
    print('   ocultos enganchados a la estructura   :', len(set(su_ids) - set(adm_ids)))
    # _allowed_input_type_ids es related (related_sudo=True) -> devuelve los ocultos
    payslip_input = admin_env['hr.payslip.input']
    f = payslip_input._fields['_allowed_input_type_ids']
    print('   _allowed_input_type_ids related_sudo :', getattr(f, 'related_sudo', None))
    if set(su_ids) - set(adm_ids):
        try:
            IType.browse(sorted(set(su_ids) - set(adm_ids))[:1]).read(['display_name'])
            print('   lectura del oculto via estructura: OK')
        except AccessError as e:
            print('   lectura del oculto via estructura: AccessError ->', str(e).splitlines()[0])
line()
PYEOF
}

wait_for_db || exit 1

run_scenario() {
  local tag="$1" db="$2" country="$3"
  echo
  echo "######################################################################"
  echo "# ESCENARIO $tag — pais de la compania al instalar: $country   ($db)"
  echo "######################################################################"
  if ! $SKIP_INSTALL; then
    build_db "$db" "$country" || { echo "ERROR construyendo $db" >&2; return 1; }
  fi
  diagnose "$db"
}

[[ -z "$ONLY" || "$ONLY" == "A" ]] && run_scenario A "$DB_A" "us"
[[ -z "$ONLY" || "$ONLY" == "B" ]] && run_scenario B "$DB_B" "do"

echo
echo "Listo. DBs: $DB_A (bug) / $DB_B (control)"
