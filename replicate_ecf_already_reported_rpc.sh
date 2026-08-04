#!/bin/bash
# replicate_ecf_already_reported_rpc.sh
#
# Valida las DOS vias remotas para cargar facturas cuyo e-CF ya fue emitido y
# aceptado por DGII, sin reenviarlas:
#
#   A) load_ecf_already_reported_rpc.py  -> XML-RPC puro, sin tocar el servidor
#   B) load_ecf_scheduled_action.py      -> accion planificada (ir.cron) que se
#                                          ejecuta a mano con "Ejecutar manualmente"
#
# Clona la DB de referencia (v19_ecf_load, creada por
# replicate_ecf_already_reported.sh --setup) en una DB desechable, instala la
# accion planificada y corre las pruebas contra el Odoo HTTP del contenedor.
#
# Data real bajo prueba (e-CF ya reportado a DGII):
#   NCF E310000001609 | RNC cliente 130674671 | 08/06/2026 | facturado 9,508.18
#   ITBIS 1,711.54 (el 18% daria 1,711.47) | total 11,219.72
# Se siembra E310000001607 para simular la numeracion que ya venia.
#
# Pruebas:
#   R1  carga por RPC del NCF real E310000001609: publicada, sin XML, sin envio
#   R1c la factura queda con la data exacta reportada a DGII
#   R1b el sello/QR queda apuntando al e-CF real de DGII
#   R2  la siguiente factura normal continua la secuencia
#   R3  cobrar la factura cargada no dispara firma/envio
#   R4  NCF duplicado -> bloqueado
#   R5  NCF que adelanta la secuencia -> bloqueado
#   R6  NCF fuera del pool vigente -> bloqueado
#   R7  cargas consecutivas dejan la secuencia corrida
#   S1  la accion planificada, ejecutada a mano, carga el e-CF igual que el loader
#   S2  tras la accion planificada la numeracion futura sigue corrida
#   S3  la accion planificada bloquea el salto de secuencia y no deja nada a medias
#   S3b la misma accion invocada por RPC con la data en el contexto
#   S4  ninguna factura cargada genero XML e-CF (nada se firmo ni se envio)
#
# Uso:
#   ./replicate_ecf_already_reported_rpc.sh
#   ./replicate_ecf_already_reported_rpc.sh --db=otra_db_base --port=8092
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ -f "$SCRIPT_DIR/.env" ]] && source "$SCRIPT_DIR/.env"

CONTAINER="${ODOO_DEVELOPER:-lfernandez}_v19"
DB_HOST="${DB_PORT_5432_TCP_ADDR:-odoo-db}"
DB_USER="${DB_ENV_POSTGRES_USER:-odoo}"
DB_PASS="${DB_ENV_POSTGRES_PASSWORD:-odoo_password}"
PORT="${ODOO_PORT:-8069}"
BASE_DB="v19_ecf_load"
TEST_DB="v19_ecf_rpc"

for arg in "$@"; do
  case "$arg" in
    --db=*)   BASE_DB="${arg#--db=}" ;;
    --port=*) PORT="${arg#--port=}" ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 2 ;;
  esac
done

echo "======================================================"
echo " e-CF ya reportado — vias RPC y accion planificada"
echo " DB base    : $BASE_DB  ->  DB prueba: $TEST_DB"
echo " Odoo HTTP  : http://localhost:$PORT"
echo "======================================================"

echo "→ Clonando $BASE_DB en $TEST_DB..."
docker exec "$CONTAINER" bash -lc "
  PGPASSWORD=$DB_PASS psql -h $DB_HOST -U $DB_USER -d postgres -c \
    \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname IN ('$BASE_DB','$TEST_DB') AND pid <> pg_backend_pid()\" >/dev/null
  PGPASSWORD=$DB_PASS dropdb -h $DB_HOST -U $DB_USER --if-exists $TEST_DB
  PGPASSWORD=$DB_PASS createdb -h $DB_HOST -U $DB_USER -T $BASE_DB $TEST_DB
" || { echo 'ERROR clonando la DB' >&2; exit 1; }

echo "→ Instalando la accion planificada (ir.cron)..."
docker exec -i "$CONTAINER" bash -lc "cat > /tmp/load_ecf_scheduled_action.py" < "$SCRIPT_DIR/load_ecf_scheduled_action.py"
IDS=$(docker exec -i "$CONTAINER" bash -lc "
  odoo shell -c /etc/odoo/odoo.conf -d $TEST_DB --db_host=$DB_HOST --db_user=$DB_USER \
    --db_password=$DB_PASS --no-http --max-cron-threads=0 --workers=0 --log-level=error
" <<'PYEOF' 2>/dev/null | grep '^IDS=' | cut -d= -f2
code = open('/tmp/load_ecf_scheduled_action.py').read().split('INICIO CODIGO ACCION')[-1].split('\n', 1)[1]
cron = env['ir.cron'].with_context(active_test=False).search(
    [('cron_name', '=', 'Cargar e-CF ya reportado en DGII')], limit=1)
vals = {
    'name': 'Cargar e-CF ya reportado en DGII',
    'model_id': env.ref('account.model_account_move').id,
    'state': 'code',
    'code': code,
    'interval_number': 999,
    'interval_type': 'weeks',
    'nextcall': '2090-01-01 00:00:00',   # para que nunca corra sola
    'user_id': env.ref('base.user_admin').id,
    'active': True,
}
cron.write(vals) if cron else None
cron = cron or env['ir.cron'].create(vals)
env.cr.commit()
print('IDS=%s,%s' % (cron.id, cron.ir_actions_server_id.id))
PYEOF
)
CRON_ID="${IDS%%,*}"
ACTION_ID="${IDS##*,}"
[[ -z "${CRON_ID:-}" ]] && { echo 'ERROR: no se pudo crear la accion planificada' >&2; exit 1; }
echo "  ir.cron id=$CRON_ID (server action delegada id=$ACTION_ID)"

echo "→ Pruebas RPC..."
ODOO_URL="http://localhost:$PORT" ODOO_DB="$TEST_DB" ACTION_ID="$ACTION_ID" CRON_ID="$CRON_ID" \
  LOADER_DIR="$SCRIPT_DIR" python3 - <<'PYEOF'
import os
import sys

sys.path.insert(0, os.environ["LOADER_DIR"])
import load_ecf_already_reported_rpc as L  # noqa: E402

L.CONFIG.update(url=os.environ["ODOO_URL"], db=os.environ["ODOO_DB"],
                user=os.environ.get("ODOO_USER", "admin"),
                password=os.environ.get("ODOO_PASSWORD", "admin"))
ACTION_ID = int(os.environ["ACTION_ID"])
CRON_ID = int(os.environ["CRON_ID"])
rpc = L.connect()

RESULTS = []


def check(label, ok, detail=""):
    RESULTS.append((label, ok, detail))
    print("%s %-56s %s" % ("PASS" if ok else "FAIL", label, detail))


company = L._company(rpc, {})
rpc.context = {"allowed_company_ids": [company["id"]]}
E31 = rpc.search_read("l10n_latam.document.type",
                      [("doc_code_prefix", "=", "E31"),
                       ("country_id", "=", company["country_id"][0])], ["id"], limit=1)[0]
journal = rpc.search_read("account.journal",
                          [("type", "=", "sale"), ("company_id", "=", company["id"]),
                           ("l10n_latam_use_documents", "=", True)],
                          ["name", "l10n_do_document_type_ids"], limit=1)[0]
itbis = rpc.search_read("account.tax",
                        [("company_id", "=", company["id"]), ("type_tax_use", "=", "sale"),
                         ("amount_type", "=", "percent"), ("amount", "=", 18.0)], ["id"], limit=1)[0]
# ───────────────── DATA REAL DEL e-CF YA REPORTADO A DGII ─────────────────
NCF_NUMBER = 1609
RNC_CLIENTE = "130674671"
FECHA = "2026-06-08"          # 08/06/2026 12:00:00 A.M. del reporte de DGII
BASE = 9508.18                # monto facturado
ITBIS = 1711.54               # ITBIS exacto reportado (18% daria 1711.47)
TOTAL = 11219.72              # BASE + ITBIS
SECURITY_CODE = "7Yx2Kp"      # codigo de seguridad del e-CF emitido
# ─────────────────────────────────────────────────────────────────────────────

found = rpc.search_read("res.partner", [("vat", "=", RNC_CLIENTE)], ["name"], limit=1)
if found:
    partner = found[0]
else:
    partner = {"id": rpc.create("res.partner", {
        "name": "CLIENTE RNC %s" % RNC_CLIENTE, "company_type": "company",
        "vat": RNC_CLIENTE, "l10n_do_dgii_tax_payer_type": "taxpayer",
        "country_id": company["country_id"][0], "customer_rank": 1,
    }), "name": "CLIENTE RNC %s" % RNC_CLIENTE}
print("  cliente: %s (RNC %s)" % (partner["name"], RNC_CLIENTE))


def ncf_of(number):
    return "E31%s" % str(number).zfill(10)


def payload(number, **extra):
    """Payload con la data real del e-CF reportado a DGII."""
    data = {
        "ncf": ncf_of(number),
        "invoice_date": FECHA,
        "company_id": company["id"],
        "journal_id": journal["id"],
        "partner": {"vat": RNC_CLIENTE},
        "lines": [{"description": "Servicios facturados (e-CF ya reportado en DGII)",
                   "quantity": 1, "price_unit": BASE, "tax_ids": [itbis["id"]]}],
        "amount_tax": ITBIS,
        "amount_total": TOTAL,
        "ecf": {"security_code": SECURITY_CODE, "sign_date": "%s 00:00:00" % FECHA,
                "trackid": "TRACK-DGII-0001"},
    }
    data.update(extra)
    return data


def normal_invoice():
    """Factura e-CF emitida por Odoo. Se publica con l10n_do_active_test para no
    firmar/enviar; la logica de secuencia es la misma que en produccion."""
    mid = rpc.create("account.move", {
        "move_type": "out_invoice",
        "journal_id": journal["id"],
        "partner_id": partner["id"],
        "invoice_date": FECHA,
        "date": FECHA,
        "l10n_latam_document_type_id": E31["id"],
        "invoice_line_ids": [(0, 0, {"name": "Producto normal", "quantity": 1, "price_unit": 1000,
                                     "tax_ids": [(6, 0, [itbis["id"]])]})],
    })
    rpc.call("account.move", "action_post", [mid], context={"l10n_do_active_test": True})
    return rpc.read1("account.move", mid, ["name", "state"])


# ── Siembra: numeracion previa a la del e-CF real ────────────────────────────
L.load_ecf_rpc(rpc, payload(NCF_NUMBER - 2), allow_sequence_jump=True)
base_inv = normal_invoice()
check("R0 baseline: la anterior al NCF real se emite normal",
      base_inv["name"] == ncf_of(NCF_NUMBER - 1), base_inv["name"])

# ── R1 carga por RPC del NCF real ────────────────────────────────────────────
res = L.load_ecf_rpc(rpc, payload(NCF_NUMBER))
check("R1 carga por RPC sin firmar ni enviar",
      res["name"] == ncf_of(NCF_NUMBER) and res["state"] == "posted"
      and res["l10n_do_ecf_send_state"] == "delivered_accepted"
      and not res["l10n_do_ecf_edi_file"] and round(res["amount_tax"], 2) == ITBIS,
      "ncf=%s ecf=%s xml=%s itbis=%s" % (res["name"], res["l10n_do_ecf_send_state"],
                                         bool(res["l10n_do_ecf_edi_file"]), res["amount_tax"]))
check("R1b sello/QR con el codigo de seguridad real de DGII",
      ncf_of(NCF_NUMBER) in (res["l10n_do_electronic_stamp"] or "")
      and SECURITY_CODE in (res["l10n_do_electronic_stamp"] or ""),
      (res["l10n_do_electronic_stamp"] or "")[:60])

exact = rpc.read1("account.move", res["id"],
                  ["amount_untaxed", "amount_tax", "amount_total", "invoice_date",
                   "commercial_partner_id"])
check("R1c la factura queda con la data exacta reportada a DGII",
      round(exact["amount_untaxed"], 2) == BASE and round(exact["amount_tax"], 2) == ITBIS
      and round(exact["amount_total"], 2) == TOTAL and exact["invoice_date"] == FECHA,
      "base=%s itbis=%s total=%s fecha=%s cliente=%s" % (
          exact["amount_untaxed"], exact["amount_tax"], exact["amount_total"],
          exact["invoice_date"], exact["commercial_partner_id"][1]))

# ── R2 la emision futura sigue corrida ───────────────────────────────────────
nxt = normal_invoice()
check("R2 la siguiente factura normal continua la secuencia",
      nxt["name"] == ncf_of(NCF_NUMBER + 1), nxt["name"])

# ── R3 cobrar la factura cargada no firma ni envia ───────────────────────────
wid = rpc.create("account.payment.register", {},
                 context={"active_model": "account.move", "active_ids": [res["id"]]})
rpc.call("account.payment.register", "action_create_payments", [wid])
after = rpc.read1("account.move", res["id"],
                  ["payment_state", "l10n_do_ecf_send_state", "l10n_do_ecf_edi_file"])
check("R3 cobrar la factura cargada no firma ni envia",
      after["payment_state"] in ("paid", "in_payment")
      and after["l10n_do_ecf_send_state"] == "delivered_accepted"
      and not after["l10n_do_ecf_edi_file"],
      "payment_state=%s ecf=%s" % (after["payment_state"], after["l10n_do_ecf_send_state"]))

# ── R4/R5/R6 guardas ─────────────────────────────────────────────────────────
for label, kwargs, data in (
    ("R4 NCF duplicado bloqueado", {}, payload(NCF_NUMBER)),
    ("R5 NCF que adelanta la secuencia bloqueado", {}, payload(NCF_NUMBER + 50)),
    ("R6 NCF fuera del pool vigente bloqueado", {"allow_sequence_jump": True}, payload(6000)),
):
    try:
        L.load_ecf_rpc(rpc, data, **kwargs)
        check(label, False, "no lanzo LoadError")
    except L.LoadError as error:
        check(label, True, str(error)[:60] + "...")

# ── R7 cargas consecutivas ───────────────────────────────────────────────────
L.load_ecf_rpc(rpc, payload(NCF_NUMBER + 2))
L.load_ecf_rpc(rpc, payload(NCF_NUMBER + 3))
nxt2 = normal_invoice()
check("R7 cargas consecutivas dejan la secuencia corrida",
      nxt2["name"] == ncf_of(NCF_NUMBER + 4), nxt2["name"])

# ── S1/S2 accion planificada ejecutada a mano ─────────────────────────
def cron_set_payloads(items):
    """Equivale a editar PAYLOADS en el codigo de la accion y guardar.

    Reemplaza el bloque completo (PAYLOADS puede ocupar varias lineas), acotado
    por la linea SALE_TYPES que va justo despues.
    """
    code = rpc.read1("ir.cron", CRON_ID, ["code"])["code"]
    # "\nPAYLOADS = " y no "PAYLOADS = ": la asignacion tiene que estar a inicio
    # de linea, no dentro de un comentario que la mencione.
    head, sep, tail = code.partition("\nPAYLOADS = ")
    if not sep:
        raise AssertionError("El codigo de la accion no define PAYLOADS")
    rest = tail[tail.index("\nSALE_TYPES = "):]
    rpc.call("ir.cron", "write", [CRON_ID],
             {"code": "%s\nPAYLOADS = %r%s" % (head, items, rest)})


def cron_run_manually():
    """Boton 'Ejecutar manualmente'. Devuelve el mensaje de error si fallo."""
    res = rpc.call("ir.cron", "method_direct_trigger", [CRON_ID])
    if isinstance(res, dict) and res.get("tag") == "display_exception":
        # El cron envuelve la excepcion en un RuntimeError sin mensaje: el texto
        # del UserError queda al final del traceback en params.data.debug.
        data = (res.get("params") or {}).get("data") or {}
        return data.get("message") or data.get("debug") or "error"
    return None


cron_set_payloads([payload(NCF_NUMBER + 5)])
error = cron_run_manually()
found = rpc.search_read("account.move", [("name", "=", ncf_of(NCF_NUMBER + 5))],
                        ["state", "l10n_do_ecf_send_state", "l10n_do_ecf_edi_file",
                         "amount_tax", "l10n_do_electronic_stamp"])
srv = found[0] if found else {}
check("S1 la accion planificada carga el e-CF sin enviarlo",
      not error and bool(found) and srv["state"] == "posted"
      and srv["l10n_do_ecf_send_state"] == "delivered_accepted"
      and not srv["l10n_do_ecf_edi_file"] and round(srv["amount_tax"], 2) == ITBIS
      and SECURITY_CODE in (srv["l10n_do_electronic_stamp"] or ""),
      "error=%s ecf=%s xml=%s itbis=%s" % (error, srv.get("l10n_do_ecf_send_state"),
                                           bool(srv.get("l10n_do_ecf_edi_file")),
                                           srv.get("amount_tax")))

nxt3 = normal_invoice()
check("S2 tras la accion planificada la numeracion sigue corrida",
      nxt3["name"] == ncf_of(NCF_NUMBER + 6), nxt3["name"])

# ── S3 la accion planificada bloquea el salto y no deja nada a medias ─────────
cron_set_payloads([payload(NCF_NUMBER + 90)])
error = cron_run_manually()
leftover = rpc.search_read("account.move", [("name", "=", ncf_of(NCF_NUMBER + 90))], ["state"])
check("S3 la accion planificada bloquea el salto de secuencia",
      bool(error) and "adelanta la secuencia" in error and not leftover,
      "%s | residuo=%s" % ((error or "")[:55], leftover))
cron_set_payloads([])

# ── S3b la misma accion invocada por RPC con la data en el contexto ────────
rpc.call("ir.actions.server", "run", [ACTION_ID],
         context={"ecf_payloads": [payload(NCF_NUMBER + 7)]})
by_rpc = rpc.search_read("account.move", [("name", "=", ncf_of(NCF_NUMBER + 7))],
                         ["state", "l10n_do_ecf_send_state", "l10n_do_ecf_edi_file"])
check("S3b la accion tambien acepta la data por contexto (RPC)",
      bool(by_rpc) and by_rpc[0]["state"] == "posted"
      and by_rpc[0]["l10n_do_ecf_send_state"] == "delivered_accepted"
      and not by_rpc[0]["l10n_do_ecf_edi_file"],
      by_rpc[0]["l10n_do_ecf_send_state"] if by_rpc else "no se creo")

# ── S4 nada se firmo: no hay XML e-CF en ninguna factura ─────────────────────
signed = rpc.search_read("account.move",
                         [("l10n_do_ecf_edi_file", "!=", False),
                          ("l10n_latam_document_type_id", "=", E31["id"])], ["name"])
check("S4 ninguna factura cargada genero XML e-CF", not signed,
      "con XML: %s" % [s["name"] for s in signed])

print("")
print("=" * 78)
failed = [r for r in RESULTS if not r[1]]
print("RESULTADO: %s/%s pruebas OK" % (len(RESULTS) - len(failed), len(RESULTS)))
for label, ok, detail in failed:
    print("  FAIL %s -> %s" % (label, detail))
print("=" * 78)
sys.exit(1 if failed else 0)
PYEOF
STATUS=$?
echo "→ Fin (la DB $TEST_DB queda para inspeccion; se recrea en cada corrida)."
exit $STATUS
