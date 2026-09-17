#!/bin/bash
# verify_input_type_country_migration.sh
#
# Valida el fix de l10n_do_hr_payroll 19.0.1.1.0 (country_id en los input types +
# migrations/19.0.1.1.0/pre-migrate.py) en tres instancias distintas:
#
#   S1  pais equivocado al instalar, SIN duplicados  -> el data sella RD, nada se borra
#   S2  pais equivocado al instalar, CON duplicados  -> los xmlid pasan al registro en
#       uso, las referencias (regla salarial, ajuste salarial, tipo de novedad, m2m de
#       la estructura) se mueven y los huerfanos se borran
#   S3  instancia SANA (RD al instalar) con duplicados creados a mano -> no se toca nada
#
# Cada DB se instala con el codigo ANTERIOR (data sin country_id, version 19.0.1.0.12)
# y despues se actualiza con el codigo de la rama, que es el camino real del upgrade.
#
# Uso:
#   ./verify_input_type_country_migration.sh
#   ./verify_input_type_country_migration.sh --only=S2
#   ./verify_input_type_country_migration.sh --keep
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
ODOO_DB_FLAGS="--db_host=$DB_HOST --db_port=$DB_PORT --db_user=$DB_USER --db_password=$DB_PASS"

REPO="$SCRIPT_DIR/odoo-pro"
DATA_FILE="$REPO/l10n_do_hr_payroll/data/hr_payslip_input_type.xml"
MANIFEST="$REPO/l10n_do_hr_payroll/__manifest__.py"
BACKUP_DIR="$(mktemp -d)"
MODULES="l10n_do_hr_payroll,l10n_do_hr_payroll_news"

ONLY=""
KEEP=false
for arg in "$@"; do
  case "$arg" in
    --only=*) ONLY="${arg#--only=}" ;;
    --keep)   KEEP=true ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

cp "$DATA_FILE" "$BACKUP_DIR/data.xml"
cp "$MANIFEST" "$BACKUP_DIR/manifest.py"
restore_new_code() { cp "$BACKUP_DIR/data.xml" "$DATA_FILE"; cp "$BACKUP_DIR/manifest.py" "$MANIFEST"; }
trap restore_new_code EXIT

use_old_code() {
  git -C "$REPO" show origin/19.0:l10n_do_hr_payroll/data/hr_payslip_input_type.xml > "$DATA_FILE"
  sed -i '' 's/"version": "[^"]*"/"version": "19.0.1.0.12"/' "$MANIFEST"
}

psql_q() { docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -tAc \"$1\""; }
drop_db() {
  psql_q "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$1'" >/dev/null
  docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $1"
}
noise() { grep -viE "warning|security risk|Pygments" || true; }
odoo_run() { docker exec "$CONTAINER" bash -lc "odoo -c /etc/odoo/odoo.conf -d $1 $ODOO_DB_FLAGS $2 --stop-after-init --max-cron-threads=0 --workers=0 --log-level=warn" 2>&1 | noise | tail -6; }
odoo_shell() { docker exec -i "$CONTAINER" bash -lc "odoo shell -c /etc/odoo/odoo.conf -d $1 $ODOO_DB_FLAGS --no-http --max-cron-threads=0 --workers=0 --log-level=warn" 2>&1 | noise; }

# $1 db, $2 codigo de pais de la compania al instalar
install_old() {
  drop_db "$1" >/dev/null
  docker exec "$CONTAINER" bash -lc "PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $1" || return 1
  use_old_code
  odoo_run "$1" "-i base --without-demo=all" || return 1
  odoo_shell "$1" <<PYEOF
env.company.country_id = env.ref('base.$2')
env.cr.commit()
PYEOF
  odoo_run "$1" "-i $MODULES --without-demo=all"
  restore_new_code
}

seed_duplicates() {
  odoo_shell "$1" <<'PYEOF'
import logging; logging.disable(logging.WARNING)
IType = env['hr.payslip.input.type'].sudo()
imd = env['ir.model.data'].sudo().search([('module','=','l10n_do_hr_payroll'),('model','=','hr.payslip.input.type')])
do = env.ref('base.do')
env.company.country_id = do
pairs = {}
for d in imd:
    old = IType.browse(d.res_id)
    pairs[old.id] = IType.create({'name': old.name + ' (manual)', 'code': old.code,
                                  'country_id': do.id, 'available_in_attachments': True}).id
old_id = sorted(pairs)[0]
# referencias al registro viejo desde tres tablas distintas
rule = env['hr.salary.rule'].sudo().search([], limit=1).copy({'amount_other_input_id': old_id})
emp = env['hr.employee'].sudo().create({'name': 'Referencia'})
att = env['hr.salary.attachment'].sudo().create({
    'employee_ids': [(6, 0, emp.ids)], 'other_input_type_id': old_id,
    'monthly_amount': 100.0, 'date_start': '2026-01-01', 'description': 'ref'})
news = env['l10n.do.hr.news.type'].sudo().create({'name': 'Referencia', 'input_type_id': old_id}) \
    if 'l10n.do.hr.news.type' in env else None
env['ir.config_parameter'].sudo().set_param(
    'verify_itc.pairs', ','.join('%s:%s' % (o, n) for o, n in sorted(pairs.items())))
print('SEED duplicados=%s viejo=%s nuevo=%s regla=%s ajuste=%s novedad=%s'
      % (len(pairs), old_id, pairs[old_id], rule.id, att.id, news.id if news else '-'))
env.cr.commit()
PYEOF
}

check() {
  odoo_shell "$1" <<PYEOF
import logging; logging.disable(logging.WARNING)
from odoo.exceptions import AccessError
SCENARIO = "$2"
IType = env['hr.payslip.input.type'].sudo()
imd = env['ir.model.data'].sudo().search([('module','=','l10n_do_hr_payroll'),('model','=','hr.payslip.input.type')])
recs = IType.browse(imd.mapped('res_id'))
adm = env(user=2, su=False)['hr.payslip.input.type']
do = env.ref('base.do')
fails = []
# el pais de la compania se corrige despues de la instalacion, como hizo el cliente
if env.company.country_id != do:
    env.company.country_id = do
    print('  (pais de la compania corregido a Republica Dominicana)')

def want(label, cond, detail=''):
    print(('  OK   ' if cond else '  FALLA') + ' ' + label + (' | ' + detail if detail else ''))
    if not cond:
        fails.append(label)

print('--- %s | version %s' % (SCENARIO, env['ir.module.module'].sudo().search([('name','=','l10n_do_hr_payroll')]).latest_version))
want('todos los xmlid del modulo apuntan a un registro vivo', all(r.exists() for r in recs), '%s xmlids' % len(imd))
want('todos con pais Republica Dominicana', all(r.country_id == do for r in recs),
     str(sorted({r.country_id.name or 'False' for r in recs})))
visibles = adm.with_context(active_test=False).search([]).ids
want('visibles para Administrator', all(r.id in visibles for r in recs),
     '%s/%s' % (len([r for r in recs if r.id in visibles]), len(recs)))
ov = env.ref('l10n_do_hr_payroll.hr_payslip_input_type_override')
try:
    adm.browse(ov.id).read(['display_name']); want('lectura del override sin AccessError', True)
except AccessError:
    want('lectura del override sin AccessError', False)

# fuga por la cache de _allowed_input_type_ids (compute_sudo)
struct = env.ref('l10n_do_hr_payroll.hr_payroll_structure_base')
env.invalidate_all()
n_su = len(struct.sudo().input_line_type_ids)
leak = env(user=2, su=False)['hr.payroll.structure'].browse(struct.id).input_line_type_ids
try:
    leak.read(['display_name'])
    want('estructura sin fuga de ocultos', True, 'sudo %s / admin %s' % (n_su, len(leak)))
except AccessError:
    want('estructura sin fuga de ocultos', False, 'sudo %s / admin %s' % (n_su, len(leak)))

codes = [r.code for r in recs]
want('sin codigos duplicados entre los xmlid', len(codes) == len(set(codes)))

if SCENARIO == 'S2':
    manual = IType.with_context(active_test=False).search([('name','like','(manual)')])
    want('los huerfanos se borraron', not manual, '%s registros "(manual)" con nombre propio' % len(manual))
    rule = env['hr.salary.rule'].sudo().search([('amount_other_input_id','!=',False)], limit=1)
    want('la regla salarial apunta a un registro vivo', bool(rule.amount_other_input_id.exists()),
         'regla %s -> %s' % (rule.id, rule.amount_other_input_id.id))
    att = env['hr.salary.attachment'].sudo().search([('description','=','ref')], limit=1)
    want('el ajuste salarial apunta a un registro vivo', bool(att.other_input_type_id.exists()),
         'ajuste %s -> %s' % (att.id, att.other_input_type_id.id))
    if 'l10n.do.hr.news.type' in env:
        news = env['l10n.do.hr.news.type'].sudo().search([('name','=','Referencia')], limit=1)
        want('el tipo de novedad apunta a un registro vivo', bool(news.input_type_id.exists()),
             'novedad %s -> %s' % (news.id, news.input_type_id.id))
    seeded = env['ir.config_parameter'].sudo().get_param('verify_itc.pairs', '')
    pairs = dict(p.split(':') for p in seeded.split(',') if p)
    want('el xmlid quedo en el registro en uso',
         str(ov.id) in pairs.values() and str(ov.id) not in pairs,
         'override -> %s (sembrado %s -> %s)' % (ov.id, min(pairs), pairs.get(min(pairs))))

if SCENARIO == 'S3':
    manual = IType.with_context(active_test=False).search([('name','like','(manual)')])
    want('los duplicados de una instancia sana NO se tocan', len(manual) == len(imd),
         '%s duplicados intactos' % len(manual))
    want('el xmlid sigue en el registro del modulo', ov.id < 100, 'override -> %s' % ov.id)

print(('RESULTADO %s: PASA' % SCENARIO) if not fails else ('RESULTADO %s: FALLA -> %s' % (SCENARIO, fails)))
PYEOF
}

run_s1() {
  echo; echo "############ S1 pais equivocado, sin duplicados"
  install_old verify_itc_s1 us || return 1
  odoo_run verify_itc_s1 "-u l10n_do_hr_payroll"
  check verify_itc_s1 S1
}
run_s2() {
  echo; echo "############ S2 pais equivocado, con duplicados y referencias"
  install_old verify_itc_s2 us || return 1
  seed_duplicates verify_itc_s2
  odoo_run verify_itc_s2 "-u l10n_do_hr_payroll"
  check verify_itc_s2 S2
}
run_s3() {
  echo; echo "############ S3 instancia sana con duplicados"
  install_old verify_itc_s3 do || return 1
  seed_duplicates verify_itc_s3
  odoo_run verify_itc_s3 "-u l10n_do_hr_payroll"
  check verify_itc_s3 S3
}

[[ -z "$ONLY" || "$ONLY" == "S1" ]] && run_s1
[[ -z "$ONLY" || "$ONLY" == "S2" ]] && run_s2
[[ -z "$ONLY" || "$ONLY" == "S3" ]] && run_s3

if ! $KEEP; then
  for db in verify_itc_s1 verify_itc_s2 verify_itc_s3; do
    [[ -z "$ONLY" || "$db" == *"$(echo $ONLY | tr 'A-Z' 'a-z')" ]] && drop_db "$db" >/dev/null
  done
fi
echo; echo "Fin."
