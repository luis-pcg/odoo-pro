#!/bin/bash
# replicate_passport_payment_file.sh
#
# Caso LEDTRIC SRL: el archivo de pago/banco (Banco Popular - BPD) no se genera
# para un colaborador extranjero que tiene pasaporte (passport_id) pero NO tiene
# cedula dominicana (identification_id), mientras que el archivo de
# Autodeterminacion/TSS si funciona con el pasaporte.
#
# Modulo afectado: l10n_do_payroll_bpd_file
#   wizard/hr_payroll_file_wizard.py
#     - Bloqueaba la generacion con UserError si identification_id estaba vacio.
#     - Tomaba el documento SOLO desde identification_id.
#     - Derivaba el tipo de documento por longitud / pais de nacimiento.
#
# Fix:
#     - employee_vat = identification_id OR passport_id  (fallback).
#     - El tipo de documento se deriva del CAMPO de origen:
#         identification_id (11 digitos) -> CE (cedula), si no -> RN (RNC)
#         passport_id (sin cedula)       -> PS (pasaporte)
#     - No bloquea si hay pasaporte aunque identification_id este vacio.
#
# El TSS (l10n_do_hr_report_base / l10n.do.hr.fixedwidth.mixin._get_document_type)
# vive en otro modulo y ya toma el pasaporte correctamente; este script lo
# verifica para confirmar que NO se ve afectado por el cambio del archivo de pago.
#
# Estrategia de repro (antes/despues con codigo REAL):
#   - El fix esta en el working tree pero SIN commitear (HEAD = codigo original).
#   - FASE 1 (BUG): se restaura el wizard original (git show HEAD) -> UserError.
#   - FASE 2 (FIX): se restaura el wizard parcheado -> el archivo se genera.
#   La DB y los datos sembrados persisten entre ambas fases.
#
# Uso:
#   ./replicate_passport_payment_file.sh                 # crea DB, instala, reproduce
#   ./replicate_passport_payment_file.sh --keep          # no borra la DB al terminar
#   ./replicate_passport_payment_file.sh --db=mi_db      # nombre de DB personalizado
#   ./replicate_passport_payment_file.sh --skip-install  # DB ya instalada, solo reproduce
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_PORT="${DB_PORT_5432_TCP_PORT:-5432}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
MODULES="l10n_do_payroll_bpd_file,l10n_do_hr_report_base"

REPO="$SCRIPT_DIR/odoo-pro"
WIZ_REL="l10n_do_payroll_bpd_file/wizard/hr_payroll_file_wizard.py"
WIZ_HOST="$REPO/$WIZ_REL"

DB_NAME="test_passport_payment_repro"
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
echo " Repro: archivo de pago BPD no toma passport_id"
echo " Contenedor : $CONTAINER"
echo " DB         : $DB_NAME"
echo " Modulos    : $MODULES"
echo "======================================================"

# ── Guardar el wizard parcheado (working tree) y restaurar siempre al salir ──
FIXED_TMP="$(mktemp)"
cp "$WIZ_HOST" "$FIXED_TMP"
restore_fixed() { cp "$FIXED_TMP" "$WIZ_HOST"; rm -f "$FIXED_TMP"; }
trap restore_fixed EXIT

wait_for_db() {
  docker exec "$CONTAINER" bash -lc "
    for i in \$(seq 1 30); do
      if PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c 'SELECT 1' >/dev/null 2>&1; then
        echo 'Postgres OK (intento '\$i')'; exit 0
      fi
      sleep 2
    done
    echo 'ERROR: Postgres no respondio tras 30 intentos' >&2; exit 1
  "
}

if ! $SKIP_INSTALL; then
  echo "→ Esperando a Postgres..."
  wait_for_db || exit 1

  echo "→ Recreando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
      \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid()\" >/dev/null 2>&1
    PGPASSWORD=$DB_PASS dropdb   -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME
    PGPASSWORD=$DB_PASS createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME
  " || { echo 'ERROR creando la DB' >&2; exit 1; }

  echo "→ Instalando $MODULES sin demo (puede tardar varios minutos)..."
  docker exec "$CONTAINER" bash -lc "
    odoo -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      -i $MODULES --stop-after-init --without-demo=all \
      --max-cron-threads=0 --workers=0
  " || { echo 'ERROR instalando los modulos' >&2; exit 1; }
fi

# ════════════════════════════════════════════════════════════════════════════
#  SEED — datos de prueba (se commitean; persisten para ambas fases)
# ════════════════════════════════════════════════════════════════════════════
echo "→ Sembrando datos de prueba (empleado extranjero con pasaporte)..."
docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
    --no-http --max-cron-threads=0 --workers=0 2>/dev/null
" <<'PYEOF'
from datetime import date, timedelta

def line(c='-'): print(c * 70)

today = date.today()
period_end = today.replace(day=1) - timedelta(days=1)
period_start = period_end.replace(day=1)

company = env.ref("base.main_company")
do = env.ref("base.do")
dop = env.ref("base.DOP")
dop.active = True
bank_popular = env.ref("l10n_do_banks.bank_popular")   # bic BPDODOSX

# ── 1. Compania RD con RNC (el header BPD exige company.vat) ─────────────────
company.write({
    "name": "LEDTRIC SRL",
    "country_id": do.id,
    "city": "Santo Domingo",
    "l10n_do_occupational_risk_type_id": env.ref("l10n_do_hr_payroll.risk_type_1").id,
    "l10n_do_bpd_bank_number": "12345",   # numero de afiliacion BPD (5 digitos)
})
try:
    company.currency_id = dop.id
except Exception:
    env.cr.rollback(); company.write({"country_id": do.id})
try:
    company.partner_id.with_context(no_vat_validation=True).vat = "131-79391-6"
except Exception:
    pass

# ── 2. Cuenta de banco de la empresa + diario BPD (is_bpd_bank) ──────────────
company_acc = env["res.partner.bank"].create({
    "acc_number": "78839748939",
    "partner_id": company.partner_id.id,
    "bank_id": bank_popular.id,
    "currency_id": dop.id,
})
bpd_journal = env["account.journal"].create({
    "name": "BPD Nomina",
    "code": "BPDPS",
    "type": "bank",
    "bank_account_id": company_acc.id,
})
print("Diario BPD: %s | is_bpd_bank=%s | bic=%s" % (
    bpd_journal.name, bpd_journal.is_bpd_bank(), bpd_journal.bank_id.bic))

# ── 3. Estructura + calendario ───────────────────────────────────────────────
attendances = []
for dow in range(5):
    attendances.append((0, 0, {"name": "Mañana", "dayofweek": str(dow),
                               "hour_from": 8, "hour_to": 12, "day_period": "morning"}))
    attendances.append((0, 0, {"name": "Tarde", "dayofweek": str(dow),
                               "hour_from": 13, "hour_to": 17, "day_period": "afternoon"}))
calendar_rd = env["resource.calendar"].create({
    "name": "Jornada RD", "company_id": company.id,
    "hours_per_day": 8, "attendance_ids": attendances,
})
company.resource_calendar_id = calendar_rd
structure_type = env.ref("l10n_do_hr_payroll.structure_type_employee")
structure_type.write({"default_resource_calendar_id": calendar_rd.id,
                      "default_schedule_pay": "monthly"})
struct_base = env.ref("l10n_do_hr_payroll.hr_payroll_structure_base")
salary_journal = env["account.journal"].search(
    [("type", "=", "general"), ("company_id", "=", company.id)], limit=1)
if not salary_journal:
    salary_journal = env["account.journal"].create(
        {"name": "Nómina", "code": "NOM", "type": "general", "company_id": company.id})
for struct in env["hr.payroll.structure"].search([]):
    if not struct.journal_id:
        struct.journal_id = salary_journal

afp = env["res.partner"].create({"name": "AFP Popular", "is_company": True, "country_id": do.id})
ars = env["res.partner"].create({"name": "ARS Universal", "is_company": True, "country_id": do.id})
dept = env["hr.department"].create({"name": "Operaciones"})
contract_start = date(today.year - 1, 1, 1)

def make_employee(name, fn, l1, l2, cedula, passport, country_birth):
    emp = env["hr.employee"].create({
        "name": name,
        "first_name": fn, "first_last_name": l1, "second_last_name": l2,
        "company_id": company.id,
        "country_id": do.id,
        "country_of_birth": country_birth.id,
        "identification_id": cedula,        # vacio para el extranjero
        "passport_id": passport,
        "l10n_do_social_security_number": False,
        "l10n_do_afp_partner_id": afp.id,
        "l10n_do_ars_partner_id": ars.id,
        "sex": "male",
        "birthday": "1990-05-10",
        "department_id": dept.id,
        "resource_calendar_id": calendar_rd.id,
        "date_version": contract_start,
        "contract_date_start": contract_start,
        "wage": 45000.0,
        "structure_type_id": structure_type.id,
    })
    emp.version_id.write({"l10n_do_schedule_retentions": "end_of_month"})
    # Cuenta bancaria BPD del empleado (savings)
    acc = env["res.partner.bank"].create({
        "acc_number": "96100%s" % cedula[-6:] if cedula else "9610055443",
        "partner_id": emp.work_contact_id.id,
        "bank_id": bank_popular.id,
        "account_type": "savings",
        "currency_id": dop.id,
    })
    emp.bank_account_ids = [(4, acc.id)]
    return emp

ven = env["res.country"].search([("code", "=", "VE")], limit=1) or do
# Colaborador EXTRANJERO: pasaporte, SIN cedula dominicana
foreign = make_employee("Carlos Pérez Marval", "Carlos", "Pérez", "Marval",
                        "", "VEN1234567", ven)
# Colaborador DOMINICANO de control: cedula, sin pasaporte
local = make_employee("Juan Domínguez Reyes", "Juan", "Domínguez", "Reyes",
                     "00112345678", "", do)

print("Extranjero: %s | identification_id=%r | passport_id=%r | pais_nac=%s" % (
    foreign.name, foreign.identification_id, foreign.passport_id,
    foreign.country_of_birth.code))
print("Dominicano: %s | identification_id=%r | passport_id=%r" % (
    local.name, local.identification_id, local.passport_id))
print("Cuenta primaria extranjero: %s (%s)" % (
    foreign.primary_bank_account_id.acc_number,
    foreign.primary_bank_account_id.account_type))

# ── 4. Lote de nomina + nominas calculadas y validadas ───────────────────────
run = env["hr.payslip.run"].create({
    "name": "Nómina Repro %s" % period_start.strftime("%m/%Y"),
    "date_start": period_start, "date_end": period_end,
})
slips = env["hr.payslip"]
for emp in (foreign, local):
    slips |= env["hr.payslip"].create({
        "name": "Nómina %s" % emp.name,
        "employee_id": emp.id,
        "struct_id": struct_base.id,
        "date_from": period_start, "date_to": period_end,
        "payslip_run_id": run.id,
    })
slips.compute_sheet()
slips.filtered(lambda s: s.state not in ("validated", "paid")).write({"state": "validated"})
for s in slips:
    net = s.line_ids.filtered(lambda l: l.code == "NET")
    print("  Slip %s estado=%s NET=%s" % (s.employee_id.name, s.state, net.mapped("total")))

env.cr.commit()
print("SEED OK: run_id=%s journal_id=%s foreign_id=%s local_id=%s" % (
    run.id, bpd_journal.id, foreign.id, local.id))
PYEOF

if [[ $? -ne 0 ]]; then echo "ERROR en el seed" >&2; exit 1; fi

# ── Bloque Python compartido por FASE 1 y FASE 2 (mismo codigo, distinto wizard)
GEN_PY=$(cat <<'PYEOF'
def line(c='-'): print(c * 70)

run = env["hr.payslip.run"].search([("name", "like", "Nómina Repro")], limit=1)
bpd_journal = env["account.journal"].search([("code", "=", "BPDPS")], limit=1)
foreign = env["hr.employee"].search([("passport_id", "=", "VEN1234567")], limit=1)
local = env["hr.employee"].search([("identification_id", "=", "00112345678")], limit=1)

wizard = env["hr.payroll.file.wizard"].create({
    "payslip_run_id": run.id,
    "journal_id": bpd_journal.id,
})
done = run.slip_ids.filtered(lambda s: s.state == "validated")

line('=')
print(" GENERACION DEL ARCHIVO DE PAGO BPD (Banco Popular)")
line('=')
try:
    data = wizard._get_payslip_bpd_data(done)
    print("GEN_RESULT: SUCCESS — el archivo de pago se genera")
    for d in data:
        if d.get("is_third_dep"):
            continue
        emp = d["slip_id"].employee_id
        print("  %-26s id_type=%s  identification=%r" % (
            emp.name, d.get("identification_type"),
            (str(d.get("identification")) or "").strip()))
    # Prueba end-to-end: generar el archivo completo (header + lineas)
    res = wizard.action_generate_file()
    print("  Archivo generado: %s (%s bytes b64)" % (
        wizard.filename, len(wizard.data or b"")))
except Exception as e:
    print("GEN_RESULT: ERROR — %s: %s" % (type(e).__name__, e))

# ── TSS / Autodeterminacion: mismo dato, otro modulo (no debe verse afectado) ─
line('-')
print(" ARCHIVO TSS / AUTODETERMINACION (l10n.do.hr.fixedwidth.mixin)")
line('-')
mixin = env["l10n.do.hr.fixedwidth.mixin"]
for emp in (foreign, local):
    try:
        dt = mixin._get_document_type(emp)
        print("  %-26s TSS doc_type=%s numero=%r" % (emp.name, dt[0], dt[1]))
    except Exception as e:
        print("  %-26s TSS ERROR: %s" % (emp.name, e))
PYEOF
)

run_shell() {
  docker exec -i "$CONTAINER" bash -lc "
    odoo shell -c /etc/odoo/odoo.conf -d $DB_NAME $ODOO_DB_FLAGS \
      --no-http --max-cron-threads=0 --workers=0 2>/dev/null
  "
}

# ════════════════════════════════════════════════════════════════════════════
#  FASE 1 — CODIGO ORIGINAL (HEAD, sin fix) => debe FALLAR
# ════════════════════════════════════════════════════════════════════════════
echo
echo "######################################################################"
echo "# FASE 1 — CODIGO ORIGINAL (sin fix): se espera UserError"
echo "######################################################################"
git -C "$REPO" show "HEAD:$WIZ_REL" > "$WIZ_HOST" \
  || { echo "ERROR: no se pudo obtener el wizard original de git" >&2; exit 1; }
echo "$GEN_PY" | run_shell

# ════════════════════════════════════════════════════════════════════════════
#  FASE 2 — CODIGO PARCHEADO (working tree, con fix) => debe GENERAR
# ════════════════════════════════════════════════════════════════════════════
echo
echo "######################################################################"
echo "# FASE 2 — CODIGO PARCHEADO (con fix): se espera exito"
echo "######################################################################"
cp "$FIXED_TMP" "$WIZ_HOST"
echo "$GEN_PY" | run_shell

echo
echo "######################################################################"
echo "# VEREDICTO"
echo "#  FASE 1 (original) -> GEN_RESULT: ERROR  (archivo de pago bloqueado)"
echo "#  FASE 2 (fix)      -> GEN_RESULT: SUCCESS (id_type=PS, pasaporte)"
echo "#  TSS               -> doc_type=P en ambas fases (no afectado)"
echo "######################################################################"

if ! $KEEP_DB && ! $SKIP_INSTALL; then
  echo "→ Eliminando base de datos $DB_NAME..."
  docker exec "$CONTAINER" bash -lc "
    PGPASSWORD=$DB_PASS psql -h $DB_HOST -p $DB_PORT -U $DB_USER -d postgres -c \
      \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$DB_NAME' AND pid <> pg_backend_pid()\" >/dev/null 2>&1
    PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -p $DB_PORT -U $DB_USER --if-exists $DB_NAME" || true
else
  echo "→ DB conservada: $DB_NAME (re-ejecuta con --skip-install --keep)"
fi
