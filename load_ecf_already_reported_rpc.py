"""Carga por XML-RPC facturas cuyo e-CF YA fue emitido/aceptado por DGII.

No requiere tocar modulos ni entrar al servidor: solo llamadas RPC estandar.
Se ejecuta desde cualquier maquina con python3 (xmlrpc.client es stdlib):

    ODOO_URL=http://localhost:8092 ODOO_DB=mi_db ODOO_USER=admin ODOO_PASSWORD=admin \
        python3 load_ecf_already_reported_rpc.py

Editar PAYLOADS al final, o importar `load_ecf_rpc` desde otro script.

Idea (identica a load_ecf_already_reported.py, ver ahi el detalle):
l10n_do_ecf_invoicing solo firma/envia cuando `l10n_do_ecf_send_state ==
"to_send"`, tanto al publicar (`_post`) como al cobrar
(`_compute_payment_state`). Creando la factura ya con
`l10n_do_ecf_send_state = "delivered_accepted"` ningun camino la toma: no se
genera XML, no se llama al webservice y el cron de pendientes tampoco la ve.

Diferencias con la version de `odoo shell`:
  * usa `action_post` (por RPC no se pueden llamar metodos privados). Si la
    compania tiene `ncf_validation_target` en "internal"/"both",
    l10n_do_ncf_validation consultara el NCF en el webservice de DGII al
    publicar; el script avisa. Esa consulta es de solo lectura (no emite), y
    para un e-CF ya aceptado deberia pasar.
  * cada llamada RPC es su propia transaccion, asi que no hace falta limpiar la
    cache de secuencias del sequence.mixin.
"""

import os
import sys
import xmlrpc.client

TERMINAL_SEND_STATE = "delivered_accepted"

CONFIG = {
    "url": os.environ.get("ODOO_URL", "http://localhost:8069"),
    "db": os.environ.get("ODOO_DB", "odoo"),
    "user": os.environ.get("ODOO_USER", "admin"),
    "password": os.environ.get("ODOO_PASSWORD", "admin"),
}


class LoadError(Exception):
    pass


class OdooRPC:
    def __init__(self, url, db, user, password):
        self.db = db
        self.password = password
        common = xmlrpc.client.ServerProxy("%s/xmlrpc/2/common" % url, allow_none=True)
        self.uid = common.authenticate(db, user, password, {})
        if not self.uid:
            raise LoadError(
                "Autenticacion fallida en %s (db=%s, user=%s)" % (url, db, user)
            )
        self.models = xmlrpc.client.ServerProxy(
            "%s/xmlrpc/2/object" % url, allow_none=True
        )
        self.context = {}

    def call(self, model, method, *args, **kwargs):
        kw = dict(kwargs)
        kw["context"] = dict(self.context, **(kw.get("context") or {}))
        return self.models.execute_kw(
            self.db, self.uid, self.password, model, method, list(args), kw
        )

    def search_read(self, model, domain, fields, **kw):
        return self.call(model, "search_read", domain, fields, **kw)

    def create(self, model, vals, **kw):
        # execute_kw envuelve los args, asi que `create` recibe una lista de vals
        # y devuelve una lista de ids: normalizamos a un solo id.
        res = self.call(model, "create", [vals], **kw)
        return res[0] if isinstance(res, list) else res

    def read1(self, model, res_id, fields):
        res = self.call(model, "read", [res_id], fields)
        if not res:
            raise LoadError("%s id=%s no existe" % (model, res_id))
        return res[0]


# ---------------------------------------------------------------------------
# Resolucion de datos
# ---------------------------------------------------------------------------
def _company(rpc, payload):
    if payload.get("company_id"):
        return rpc.read1(
            "res.company",
            payload["company_id"],
            ["name", "vat", "country_id", "parent_id"],
        )
    if payload.get("company_vat"):
        found = rpc.search_read(
            "res.company",
            [("vat", "=", payload["company_vat"])],
            ["name", "vat", "country_id", "parent_id"],
            limit=1,
        )
        if not found:
            raise LoadError(
                "Compania con RNC %s no encontrada" % payload["company_vat"]
            )
        return found[0]
    user = rpc.read1("res.users", rpc.uid, ["company_id"])
    return rpc.read1(
        "res.company", user["company_id"][0], ["name", "vat", "country_id", "parent_id"]
    )


def _document_type(rpc, company, ncf):
    ncf = (ncf or "").strip().upper()
    if len(ncf) not in (11, 13) or ncf[0] not in ("B", "E") or not ncf[3:].isdigit():
        raise LoadError(
            "NCF %r invalido (11 caracteres para B, 13 para E, resto digitos)" % ncf
        )
    found = rpc.search_read(
        "l10n_latam.document.type",
        [
            ("doc_code_prefix", "=", ncf[:3]),
            ("country_id", "=", company["country_id"][0]),
        ],
        ["name", "doc_code_prefix"],
        limit=1,
    )
    if not found:
        raise LoadError("No existe tipo de documento con prefijo %s" % ncf[:3])
    return ncf, found[0]


def _journal(rpc, company, doc_type, payload, move_type):
    if payload.get("journal_id"):
        return rpc.read1(
            "account.journal",
            payload["journal_id"],
            ["name", "l10n_do_document_type_ids"],
        )
    jtype = "purchase" if move_type in ("in_invoice", "in_refund") else "sale"
    journals = rpc.search_read(
        "account.journal",
        [
            ("type", "=", jtype),
            ("company_id", "=", company["id"]),
            ("l10n_latam_use_documents", "=", True),
        ],
        ["name", "l10n_do_document_type_ids"],
    )
    if not journals:
        raise LoadError(
            "No hay diario %s con documentos fiscales en %s" % (jtype, company["name"])
        )
    for journal in journals:
        pools = rpc.call(
            "l10n_do.account.journal.document_type",
            "read",
            journal["l10n_do_document_type_ids"],
            ["l10n_latam_document_type_id"],
        )
        if any(p["l10n_latam_document_type_id"][0] == doc_type["id"] for p in pools):
            return journal
    return journals[0]


def _partner(rpc, company, payload):
    data = payload.get("partner") or {}
    found = []
    if data.get("id"):
        found = rpc.call(
            "res.partner", "read", [data["id"]], ["name", "l10n_do_dgii_tax_payer_type"]
        )
    elif data.get("vat"):
        found = rpc.search_read(
            "res.partner",
            [("vat", "=", data["vat"])],
            ["name", "l10n_do_dgii_tax_payer_type"],
            limit=1,
        )
    elif data.get("name"):
        found = rpc.search_read(
            "res.partner",
            [("name", "=", data["name"])],
            ["name", "l10n_do_dgii_tax_payer_type"],
            limit=1,
        )
    if not found:
        if not data.get("create"):
            raise LoadError(
                "Cliente no encontrado (%s). Usa partner['create'] = True." % data
            )
        pid = rpc.create(
            "res.partner",
            {
                "name": data.get("name") or data.get("vat"),
                "vat": data.get("vat"),
                "l10n_do_dgii_tax_payer_type": data.get("payer_type") or "taxpayer",
                "country_id": company["country_id"][0],
            },
        )
        return rpc.read1("res.partner", pid, ["name", "l10n_do_dgii_tax_payer_type"])
    partner = found[0]
    if not partner["l10n_do_dgii_tax_payer_type"]:
        if not data.get("payer_type"):
            raise LoadError(
                "El cliente %s no tiene tipo de contribuyente DGII (obligatorio para "
                "documentos fiscales)" % partner["name"]
            )
        rpc.call(
            "res.partner",
            "write",
            [partner["id"]],
            {"l10n_do_dgii_tax_payer_type": data["payer_type"]},
        )
    return partner


def _taxes(rpc, company, line, move_type):
    if line.get("tax_ids") is not None:
        return list(line["tax_ids"])
    ids = []
    for name in line.get("tax_names") or []:
        # `=` en vez de ilike: account.tax._search reescribe like/ilike sobre name.
        found = rpc.search_read(
            "account.tax",
            [("name", "=", name), ("company_id", "=", company["id"])],
            ["id"],
            limit=1,
        )
        if not found:
            raise LoadError("Impuesto %r no encontrado en %s" % (name, company["name"]))
        ids.append(found[0]["id"])
    if line.get("tax_percent") is not None:
        type_tax_use = (
            "purchase" if move_type in ("in_invoice", "in_refund") else "sale"
        )
        found = rpc.search_read(
            "account.tax",
            [
                ("company_id", "=", company["id"]),
                ("type_tax_use", "=", type_tax_use),
                ("amount_type", "=", "percent"),
                ("amount", "=", float(line["tax_percent"])),
            ],
            ["id"],
            limit=1,
        )
        if not found:
            raise LoadError(
                "No hay impuesto de %s%% (%s) en %s"
                % (line["tax_percent"], type_tax_use, company["name"])
            )
        ids.append(found[0]["id"])
    return ids


# ---------------------------------------------------------------------------
# Guardas
# ---------------------------------------------------------------------------
SALE_TYPES = ["out_invoice", "out_refund", "out_receipt"]
PURCHASE_TYPES = ["in_invoice", "in_refund", "in_receipt"]


def _sequence_guard(rpc, company, doc_type, ncf, move_type, allow_sequence_jump):
    parent = company["parent_id"][0] if company["parent_id"] else company["id"]
    children = rpc.search_read("res.company", [("parent_id", "=", parent)], ["id"])
    company_ids = [parent] + [c["id"] for c in children]
    move_types = PURCHASE_TYPES if move_type in PURCHASE_TYPES else SALE_TYPES
    last = rpc.search_read(
        "account.move",
        [
            ("l10n_latam_document_type_id", "=", doc_type["id"]),
            ("company_id", "in", company_ids),
            ("move_type", "in", move_types),
            ("name", "not in", ["/", "", False]),
        ],
        ["name", "sequence_number"],
        limit=1,
        order="sequence_number desc",
    )
    current_max = last[0]["sequence_number"] if last else 0
    number = int(ncf[3:])
    if number > current_max + 1:
        msg = (
            "El NCF %s adelanta la secuencia: el maximo actual de %s es %s, asi que las "
            "facturas nuevas pasarian de %s a %s y los numeros %s..%s quedarian inutilizables. "
            "Carga primero los NCF faltantes o usa allow_sequence_jump=True."
            % (
                ncf,
                doc_type["doc_code_prefix"],
                current_max,
                current_max,
                number + 1,
                current_max + 1,
                number - 1,
            )
        )
        if not allow_sequence_jump:
            raise LoadError(msg)
        print("  AVISO: %s" % msg)
    return current_max, number


def _pool_guard(rpc, company, journal, doc_type, number, allow_out_of_pool):
    sequence_manager = rpc.read1(
        "res.company", company["id"], ["l10n_do_sequence_manager"]
    )
    if not sequence_manager["l10n_do_sequence_manager"]:
        return None
    pools = rpc.call(
        "l10n_do.account.journal.document_type",
        "read",
        journal["l10n_do_document_type_ids"],
        ["l10n_latam_document_type_id", "sequence_start", "sequence_end", "state"],
    )
    pool = next(
        (p for p in pools if p["l10n_latam_document_type_id"][0] == doc_type["id"]),
        None,
    )
    if not pool:
        return None
    if not (pool["sequence_start"] <= number <= pool["sequence_end"]):
        msg = (
            "El NCF queda fuera del pool vigente [%s, %s] de %s: el pool podria volver a "
            "emitir ese numero y chocar con el indice unico al publicar. Ajusta el pool o usa "
            "allow_out_of_pool=True."
            % (pool["sequence_start"], pool["sequence_end"], doc_type["name"])
        )
        if not allow_out_of_pool:
            raise LoadError(msg)
        print("  AVISO: %s" % msg)
    return pool


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def load_ecf_rpc(rpc, payload, allow_sequence_jump=False, allow_out_of_pool=False):
    """Crea y publica por RPC una factura con e-CF ya reportado. Devuelve un dict."""
    company = _company(rpc, payload)
    rpc.context = dict(rpc.context, allowed_company_ids=[company["id"]])

    move_type = payload.get("move_type") or "out_invoice"
    ncf, doc_type = _document_type(rpc, company, payload["ncf"])
    journal = _journal(rpc, company, doc_type, payload, move_type)
    partner = _partner(rpc, company, payload)

    dup = rpc.search_read(
        "account.move",
        [
            ("name", "=", ncf),
            ("company_id", "=", company["id"]),
            ("state", "!=", "cancel"),
        ],
        ["name", "state"],
    )
    if dup:
        raise LoadError("El NCF %s ya existe (id=%s)" % (ncf, [d["id"] for d in dup]))

    current_max, number = _sequence_guard(
        rpc, company, doc_type, ncf, move_type, allow_sequence_jump
    )
    _pool_guard(rpc, company, journal, doc_type, number, allow_out_of_pool)

    validation = rpc.read1("res.company", company["id"], ["ncf_validation_target"])
    if validation.get("ncf_validation_target") in ("internal", "both"):
        print(
            "  AVISO: la compania tiene ncf_validation_target=%s, asi que al publicar se "
            "consultara el NCF en el webservice de DGII (solo lectura)."
            % validation["ncf_validation_target"]
        )

    ecf = payload.get("ecf") or {}
    vals = {
        "move_type": move_type,
        "journal_id": journal["id"],
        "partner_id": partner["id"],
        "invoice_date": payload["invoice_date"],
        "date": payload.get("date") or payload["invoice_date"],
        "l10n_latam_document_type_id": doc_type["id"],
        "name": ncf,
        # Estado terminal ANTES de publicar: ni _post ni _compute_payment_state firman.
        "l10n_do_ecf_send_state": TERMINAL_SEND_STATE,
        "invoice_line_ids": [],
    }
    for key, field in (
        ("ref", "ref"),
        ("income_type", "l10n_do_income_type"),
        ("origin_ncf", "l10n_do_origin_ncf"),
        ("ecf_modification_code", "l10n_do_ecf_modification_code"),
    ):
        if payload.get(key):
            vals[field] = payload[key]
    if payload.get("currency"):
        found = rpc.search_read(
            "res.currency", [("name", "=", payload["currency"])], ["id"], limit=1
        )
        if not found:
            raise LoadError("Moneda %s no encontrada" % payload["currency"])
        vals["currency_id"] = found[0]["id"]
    if ecf.get("security_code"):
        vals["l10n_do_ecf_security_code"] = ecf["security_code"]
    if ecf.get("sign_date"):
        vals["l10n_do_ecf_sign_date"] = ecf["sign_date"]
    if ecf.get("trackid"):
        vals["l10n_do_ecf_trackid"] = ecf["trackid"]
    if ecf.get("xml_b64"):
        vals["l10n_do_ecf_edi_file"] = ecf["xml_b64"]
        vals["l10n_do_ecf_edi_file_name"] = "%s.xml" % ncf

    for line in payload["lines"]:
        vals["invoice_line_ids"].append(
            (
                0,
                0,
                {
                    "name": line.get("description") or "/",
                    "quantity": line.get("quantity", 1.0),
                    "price_unit": line["price_unit"],
                    "discount": line.get("discount", 0.0),
                    "tax_ids": [(6, 0, _taxes(rpc, company, line, move_type))],
                    **(
                        {"product_id": line["product_id"]}
                        if line.get("product_id")
                        else {}
                    ),
                    **(
                        {"account_id": line["account_id"]}
                        if line.get("account_id")
                        else {}
                    ),
                },
            )
        )

    move_id = rpc.create("account.move", vals)

    # Cada llamada RPC commitea, asi que si algo falla despues del create hay que
    # borrar el borrador a mano: si no, queda ocupando el NCF.
    try:
        if payload.get("amount_tax") is not None:
            _fix_tax_amount(rpc, move_id, float(payload["amount_tax"]),
                            payload.get("tax_group_name"))

        if payload.get("amount_total") is not None:
            total = rpc.read1("account.move", move_id, ["amount_total"])["amount_total"]
            if round(total, 2) != round(float(payload["amount_total"]), 2):
                raise LoadError(
                    "El total calculado (%s) no coincide con el reportado a DGII (%s)"
                    % (total, payload["amount_total"])
                )

        rpc.call("account.move", "action_post", [move_id])
    except Exception:
        try:
            rpc.call("account.move", "button_draft", [move_id])
            rpc.call("account.move", "unlink", [move_id])
            print("  Borrador %s eliminado tras el fallo." % ncf)
        except Exception as cleanup_error:
            print(
                "  AVISO: quedo el borrador id=%s con NCF %s (no se pudo borrar: %s)"
                % (move_id, ncf, cleanup_error)
            )
        raise

    data = rpc.read1(
        "account.move",
        move_id,
        [
            "name",
            "state",
            "l10n_do_ecf_send_state",
            "l10n_do_ecf_edi_file",
            "amount_tax",
            "amount_total",
            "l10n_do_electronic_stamp",
        ],
    )
    if data["name"] != ncf:
        raise LoadError("Odoo reemplazo el NCF %s por %s" % (ncf, data["name"]))
    if data["state"] != "posted":
        raise LoadError("La factura quedo en estado %s" % data["state"])
    if data["l10n_do_ecf_send_state"] != TERMINAL_SEND_STATE:
        raise LoadError("Estado e-CF inesperado: %s" % data["l10n_do_ecf_send_state"])

    # El sello/QR solo se calcula con la factura publicada: reescribir el codigo
    # de seguridad ya publicada dispara el recomputo.
    if ecf.get("security_code"):
        rpc.call(
            "account.move",
            "write",
            [move_id],
            {"l10n_do_ecf_security_code": ecf["security_code"]},
        )

    rpc.call(
        "account.move",
        "message_post",
        [move_id],
        body="e-CF <b>%s</b> cargado por RPC: ya estaba emitido y aceptado en DGII, "
        "por lo que Odoo no lo firmo ni lo envio de nuevo. Maximo de secuencia %s "
        "antes de la carga: %s." % (ncf, doc_type["doc_code_prefix"], current_max),
    )

    data = rpc.read1(
        "account.move",
        move_id,
        [
            "name",
            "state",
            "l10n_do_ecf_send_state",
            "l10n_do_ecf_edi_file",
            "amount_tax",
            "amount_total",
            "l10n_do_electronic_stamp",
        ],
    )
    data["previous_max_sequence"] = current_max
    return data


def _fix_tax_amount(rpc, move_id, target_tax, group_name=None):
    """Cuadra el impuesto al centavo reportado a DGII.

    Escribe `tax_totals`, que tiene un inverse en account.move (el mismo camino
    que el widget de totales de la factura: "Edit Tax amounts if you encounter
    rounding issues"): ajusta la primera linea del grupo y resincroniza la linea
    de cobro. Tocar las lineas a mano NO sirve: al publicar, la linea de termino
    de pago se recalcula y el asiento revienta con "The entry is not balanced".
    """
    move = rpc.read1("account.move", move_id, ["name", "amount_tax", "tax_totals"])
    diff = round(round(target_tax, 2) - move["amount_tax"], 2)
    if not diff:
        return 0.0

    totals = move["tax_totals"] or {}
    groups = [
        group
        for subtotal in totals.get("subtotals") or []
        for group in subtotal.get("tax_groups") or []
    ]
    if not groups:
        raise LoadError(
            "La factura %s no tiene grupos de impuestos: no se puede cuadrar el "
            "importe reportado a DGII" % move["name"]
        )

    if group_name:
        matching = [g for g in groups if g.get("group_name") == group_name]
        if not matching:
            raise LoadError(
                "La factura %s no tiene el grupo de impuestos %r (hay: %s)"
                % (move["name"], group_name,
                   ", ".join(str(g.get("group_name")) for g in groups))
            )
        group = matching[0]
    else:
        # Sin pista, ajusta el grupo de mayor importe (el ITBIS en la practica).
        group = max(groups, key=lambda g: abs(g.get("tax_amount_currency") or 0.0))

    group["tax_amount_currency"] = round((group.get("tax_amount_currency") or 0.0) + diff, 2)
    rpc.call("account.move", "write", [move_id], {"tax_totals": totals})

    after = rpc.read1("account.move", move_id, ["amount_tax"])["amount_tax"]
    if round(after, 2) != round(target_tax, 2):
        raise LoadError(
            "No se pudo cuadrar el impuesto de %s: quedo en %s y DGII reporta %s"
            % (move["name"], after, target_tax)
        )
    print("  ITBIS ajustado en %s para cuadrar con DGII" % diff)
    return diff


def connect(config=None):
    cfg = dict(CONFIG, **(config or {}))
    return OdooRPC(cfg["url"], cfg["db"], cfg["user"], cfg["password"])


# ---------------------------------------------------------------------------
# EDITAR AQUI
# ---------------------------------------------------------------------------
PAYLOADS = [
    {
        # e-CF ya reportado a DGII:
        #   54  130674671  E310000001609  08/06/2026 12:00:00 A.M.
        #   facturado 9,508.18 | ITBIS 1,711.54 | total 11,219.72
        "ncf": "E310000001609",
        "invoice_date": "2026-06-08",  # 08/06/2026 (dd/mm/yyyy de DGII)
        "partner": {"vat": "130674671", "name": "CLIENTE RNC 130674671", "create": True},
        "lines": [{"description": "Servicios facturados (e-CF ya reportado en DGII)",
                   "quantity": 1, "price_unit": 9508.18, "tax_percent": 18}],
        # El 18% da 1,711.47: el ITBIS se cuadra al centavo reportado a DGII.
        "amount_tax": 1711.54,
        "amount_total": 11219.72,
        # Codigo de seguridad y fecha/hora de firma del e-CF emitido: con ellos
        # el sello (QR) del PDF apunta al e-CF real en DGII.
        "ecf": {"security_code": "7Yx2Kp", "sign_date": "2026-06-08 00:00:00"},
    },
]


def main():
    rpc = connect()
    print("Conectado a %s (db=%s) uid=%s" % (CONFIG["url"], CONFIG["db"], rpc.uid))
    failed = 0
    for payload in sorted(PAYLOADS, key=lambda p: p["ncf"]):
        try:
            res = load_ecf_rpc(rpc, payload)
            print(
                "OK  %s  id=%s  total=%s  itbis=%s  estado=%s  xml=%s"
                % (
                    res["name"],
                    res["id"],
                    res["amount_total"],
                    res["amount_tax"],
                    res["l10n_do_ecf_send_state"],
                    bool(res["l10n_do_ecf_edi_file"]),
                )
            )
        except (LoadError, xmlrpc.client.Fault) as error:
            failed += 1
            print("ERROR %s -> %s" % (payload["ncf"], error))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
