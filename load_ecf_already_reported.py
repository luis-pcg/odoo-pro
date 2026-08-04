"""Carga en Odoo una factura cuyo e-CF YA fue emitido/aceptado por DGII.

La factura se crea con su NCF real y se publica SIN firmar ni enviar el XML a
DGII. Uso:

    docker exec -i lfernandez_v19 bash -lc \
      "odoo shell -c /etc/odoo/odoo.conf -d MI_DB --no-http --max-cron-threads=0" \
      < load_ecf_already_reported.py

Editar PAYLOADS al final del archivo (o importar `load_ecf` desde otro script).

Por que no se envia a DGII
--------------------------
l10n_do_ecf_invoicing firma y envia el e-CF en dos lugares, y ambos filtran por
`l10n_do_ecf_send_state == "to_send"`:

  * `_post()`                 -> al publicar la factura
  * `_compute_payment_state()`-> al registrar el primer pago

Por eso la factura se crea directamente con `l10n_do_ecf_send_state =
"delivered_accepted"` (estado terminal): ninguno de los dos caminos la toma, no
se genera XML, no se llama al webservice y el cron de pendientes tampoco la ve
(ese cron busca `signed_pending`).

Efecto sobre la secuencia
-------------------------
En RD el proximo NCF se deduce del MAXIMO `sequence_number` ya usado para el
mismo tipo de documento / grupo de companias / direccion (venta vs compra), no
de un contador aparte: ver `_get_last_sequence_domain` en
l10n_do_accounting/models/account_move.py y `_get_last_sequence` del
sequence.mixin de Odoo (ORDER BY sequence_number DESC LIMIT 1).

Consecuencias:

  * NCF == maximo + 1  -> la secuencia sigue igual de corrida. Caso normal.
  * NCF < maximo        -> rellena un hueco. La numeracion futura no cambia.
  * NCF > maximo + 1    -> la proxima factura salta a NCF + 1 y los numeros
                           intermedios quedan inutilizables por Odoo.

Por eso el tercer caso esta BLOQUEADO salvo que pases
`allow_sequence_jump=True` a proposito.
"""

import base64
import logging

from odoo.exceptions import UserError

_logger = logging.getLogger("load_ecf_already_reported")

TERMINAL_SEND_STATE = "delivered_accepted"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _resolve_company(env, payload):
    company = None
    if payload.get("company_id"):
        company = env["res.company"].browse(payload["company_id"]).exists()
    elif payload.get("company_vat"):
        company = env["res.company"].search([("vat", "=", payload["company_vat"])], limit=1)
    else:
        company = env.company
    if not company:
        raise UserError("Compania no encontrada: %s" % payload)
    return company


def _resolve_document_type(env, company, ncf):
    ncf = (ncf or "").strip().upper()
    if len(ncf) not in (11, 13) or ncf[0] not in ("B", "E"):
        raise UserError("NCF %r invalido: se esperan 11 (B) o 13 (E) caracteres." % ncf)
    if not ncf[3:].isdigit():
        raise UserError("NCF %r invalido: los caracteres 4..n deben ser digitos." % ncf)

    doc_type = env["l10n_latam.document.type"].search(
        [("doc_code_prefix", "=", ncf[:3]), ("country_id", "=", company.country_id.id)],
        limit=1,
    )
    if not doc_type:
        raise UserError("No existe tipo de documento con prefijo %s." % ncf[:3])
    return ncf, doc_type


def _resolve_journal(env, company, doc_type, payload, move_type):
    if payload.get("journal_id"):
        journal = env["account.journal"].browse(payload["journal_id"]).exists()
        if not journal:
            raise UserError("Diario %s no existe." % payload["journal_id"])
        return journal

    jtype = "purchase" if move_type in ("in_invoice", "in_refund") else "sale"
    journals = env["account.journal"].search(
        [
            ("type", "=", jtype),
            ("company_id", "=", company.id),
            ("l10n_latam_use_documents", "=", True),
        ]
    )
    # Prefiere el diario que ya tiene ese tipo de documento configurado.
    for journal in journals:
        doc_types = journal.l10n_do_document_type_ids.mapped("l10n_latam_document_type_id")
        if doc_type in doc_types:
            return journal
    if not journals:
        raise UserError("No hay diario %s con documentos fiscales en %s." % (jtype, company.name))
    return journals[0]


def _resolve_partner(env, company, payload):
    data = payload.get("partner") or {}
    partner = None
    if data.get("id"):
        partner = env["res.partner"].browse(data["id"]).exists()
    elif data.get("vat"):
        partner = env["res.partner"].search(
            [("vat", "=", data["vat"]), ("company_id", "in", (False, company.id))], limit=1
        )
    elif data.get("name"):
        partner = env["res.partner"].search([("name", "=", data["name"])], limit=1)

    if not partner:
        if not data.get("create"):
            raise UserError(
                "Cliente no encontrado (%s). Pasa partner['create'] = True para crearlo." % data
            )
        partner = env["res.partner"].create(
            {
                "name": data.get("name") or data.get("vat"),
                "vat": data.get("vat"),
                "l10n_do_dgii_tax_payer_type": data.get("payer_type") or "taxpayer",
                "country_id": company.country_id.id,
            }
        )

    if not partner.l10n_do_dgii_tax_payer_type:
        payer_type = data.get("payer_type")
        if not payer_type:
            raise UserError(
                "El cliente %s no tiene tipo de contribuyente DGII y es obligatorio "
                "para publicar un documento fiscal." % partner.display_name
            )
        partner.l10n_do_dgii_tax_payer_type = payer_type
    return partner


def _resolve_taxes(env, company, line, move_type):
    if line.get("tax_ids") is not None:
        return env["account.tax"].browse(line["tax_ids"])

    type_tax_use = "purchase" if move_type in ("in_invoice", "in_refund") else "sale"
    taxes = env["account.tax"]

    for name in line.get("tax_names") or []:
        # `=` evita el reescrito de like/ilike que account.tax._search aplica a name.
        tax = env["account.tax"].search(
            [("name", "=", name), ("company_id", "=", company.id)], limit=1
        )
        if not tax:
            raise UserError("Impuesto %r no encontrado en %s." % (name, company.name))
        taxes |= tax

    if line.get("tax_percent") is not None:
        tax = env["account.tax"].search(
            [
                ("company_id", "=", company.id),
                ("type_tax_use", "=", type_tax_use),
                ("amount_type", "=", "percent"),
                ("amount", "=", float(line["tax_percent"])),
            ],
            limit=1,
        )
        if not tax:
            raise UserError(
                "No hay impuesto de %s%% (%s) en %s."
                % (line["tax_percent"], type_tax_use, company.name)
            )
        taxes |= tax

    return taxes


def _sequence_guard(env, company, doc_type, ncf, move_type, allow_sequence_jump):
    """Rechaza el NCF si adelantaria la numeracion futura (salto de secuencia)."""
    Move = env["account.move"].sudo()
    parent = company.parent_id or company
    company_ids = (parent | env["res.company"].sudo().search([("parent_id", "=", parent.id)])).ids
    move_types = (
        Move.get_purchase_types(include_receipts=True)
        if move_type in ("in_invoice", "in_refund", "in_receipt")
        else Move.get_sale_types(include_receipts=True)
    )
    last = Move.search(
        [
            ("l10n_latam_document_type_id", "=", doc_type.id),
            ("company_id", "in", company_ids),
            ("move_type", "in", move_types),
            ("name", "not in", ("/", "", False)),
        ],
        order="sequence_number desc",
        limit=1,
    )
    current_max = last.sequence_number or 0
    number = int(ncf[3:])

    if number > current_max + 1:
        msg = (
            "El NCF %s adelanta la secuencia: el maximo actual de %s es %s, asi que "
            "las facturas nuevas pasarian de %s a %s y los numeros %s..%s quedarian "
            "inutilizables. Carga primero los NCF faltantes, o pasa "
            "allow_sequence_jump=True si el salto es intencional."
            % (
                ncf,
                doc_type.doc_code_prefix,
                current_max,
                current_max,
                number + 1,
                current_max + 1,
                number - 1,
            )
        )
        if not allow_sequence_jump:
            raise UserError(msg)
        _logger.warning(msg)
    return current_max, number


def _pool_guard(env, company, journal, doc_type, ncf, number, allow_out_of_pool):
    """Con gestor de secuencias activo, el NCF debe caer dentro del pool vigente.

    Fuera del rango el movimiento es invisible para `_get_last_sequence_domain`
    (l10n_do_document_pools lo acota a [sequence_start, sequence_end]), asi que
    el pool podria volver a emitir ese mismo numero y chocar con el indice unico
    account_move_unique_l10n_do_name_sales al publicar.
    """
    if not company.l10n_do_sequence_manager:
        return None
    pool = journal.l10n_do_document_type_ids.filtered(
        lambda d: d.l10n_latam_document_type_id == doc_type
    )[:1]
    if not pool:
        return None
    if not (pool.sequence_start <= number <= pool.sequence_end):
        msg = (
            "El NCF %s queda fuera del pool vigente [%s, %s] de %s. El pool podria "
            "volver a emitir ese numero y chocar con el indice unico al publicar. "
            "Ajusta el pool (o crea el que corresponde al rango) o pasa "
            "allow_out_of_pool=True si sabes lo que haces."
            % (ncf, pool.sequence_start, pool.sequence_end, doc_type.name)
        )
        if not allow_out_of_pool:
            raise UserError(msg)
        _logger.warning(msg)
    return pool


def _fix_tax_amount(move, target_tax, group_name=None):
    """Cuadra el impuesto al centavo reportado a DGII (el e-CF emitido es la verdad).

    Usa el inverse de `tax_totals`, el mismo camino que el widget de totales de la
    factura ("Edit Tax amounts if you encounter rounding issues"): ajusta la
    primera linea del grupo de impuesto y resincroniza la linea de cobro, asi el
    asiento queda cuadrado. Escribir las lineas a mano NO sirve: al publicar, la
    linea de termino de pago se recalcula y el asiento revienta con "The entry is
    not balanced".
    """
    diff = round(target_tax - move.amount_tax, 2)
    if not diff:
        return 0.0

    totals = move.tax_totals
    groups = [
        group
        for subtotal in totals.get("subtotals") or []
        for group in subtotal.get("tax_groups") or []
    ]
    if not groups:
        raise UserError(
            "La factura %s no tiene grupos de impuestos: no se puede cuadrar el "
            "importe reportado a DGII." % move.name
        )

    if group_name:
        matching = [g for g in groups if g.get("group_name") == group_name]
        if not matching:
            raise UserError(
                "La factura %s no tiene el grupo de impuestos %r (hay: %s)."
                % (move.name, group_name, ", ".join(str(g.get("group_name")) for g in groups))
            )
        group = matching[0]
    else:
        # Sin pista, ajusta el grupo de mayor importe (el ITBIS en la practica).
        group = max(groups, key=lambda g: abs(g.get("tax_amount_currency") or 0.0))

    group["tax_amount_currency"] = round((group.get("tax_amount_currency") or 0.0) + diff, 2)
    move.write({"tax_totals": totals})

    if round(move.amount_tax, 2) != round(target_tax, 2):
        raise UserError(
            "No se pudo cuadrar el impuesto de %s: quedo en %s y DGII reporta %s."
            % (move.name, move.amount_tax, target_tax)
        )
    return diff


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------
def load_ecf(env, payload, allow_sequence_jump=False, allow_out_of_pool=False):
    """Crea y publica una factura con e-CF ya reportado a DGII, sin reenviarlo.

    payload = {
        "ncf": "E310000001609",
        "invoice_date": "2026-06-08",
        "move_type": "out_invoice",              # opcional
        "company_vat": "131793898",              # o "company_id"
        "journal_id": 3,                         # opcional
        "partner": {"vat": "131234567", "name": "Cliente SRL",
                    "payer_type": "taxpayer", "create": True},
        "lines": [{"description": "Servicios", "quantity": 1,
                   "price_unit": 9508.18, "tax_percent": 18}],
        "amount_tax": 1711.54,                   # opcional, cuadra al centavo
        "tax_group_name": "ITBIS",               # opcional, grupo a cuadrar
        "amount_total": 11219.72,                # opcional, verificacion
        "currency": "USD", "currency_rate": 60.5,# opcional
        "income_type": "01",                     # opcional
        "ref": "Carga e-CF reportado",           # opcional
        "origin_ncf": "E310000000001",           # notas de credito/debito
        "ecf_modification_code": "01",           # notas de credito/debito
        "ecf": {"security_code": "7Yx2Kp",
                "sign_date": "2026-06-08 00:00:00",
                "trackid": "...", "xml_b64": "..."},
    }
    """
    company = _resolve_company(env, payload)
    env = env(context=dict(env.context, allowed_company_ids=[company.id]))
    company = env["res.company"].browse(company.id)

    move_type = payload.get("move_type") or "out_invoice"
    ncf, doc_type = _resolve_document_type(env, company, payload["ncf"])
    journal = _resolve_journal(env, company, doc_type, payload, move_type)
    partner = _resolve_partner(env, company, payload)

    dup = (
        env["account.move"]
        .sudo()
        .search([("name", "=", ncf), ("company_id", "=", company.id), ("state", "!=", "cancel")])
    )
    if dup:
        raise UserError("El NCF %s ya existe en el asiento %s." % (ncf, dup.ids))

    current_max, number = _sequence_guard(
        env, company, doc_type, ncf, move_type, allow_sequence_jump
    )
    _pool_guard(env, company, journal, doc_type, ncf, number, allow_out_of_pool)

    ecf = payload.get("ecf") or {}
    vals = {
        "move_type": move_type,
        "journal_id": journal.id,
        "partner_id": partner.id,
        "invoice_date": payload["invoice_date"],
        "date": payload.get("date") or payload["invoice_date"],
        "l10n_latam_document_type_id": doc_type.id,
        "name": ncf,
        # Estado terminal ANTES de publicar: `_post` y `_compute_payment_state`
        # de l10n_do_ecf_invoicing solo firman/envian cuando esta en "to_send".
        "l10n_do_ecf_send_state": TERMINAL_SEND_STATE,
        "invoice_line_ids": [],
    }
    if payload.get("ref"):
        vals["ref"] = payload["ref"]
    if payload.get("income_type"):
        vals["l10n_do_income_type"] = payload["income_type"]
    if payload.get("origin_ncf"):
        vals["l10n_do_origin_ncf"] = payload["origin_ncf"]
    if payload.get("ecf_modification_code"):
        vals["l10n_do_ecf_modification_code"] = payload["ecf_modification_code"]
    if payload.get("currency"):
        currency = env["res.currency"].search([("name", "=", payload["currency"])], limit=1)
        if not currency:
            raise UserError("Moneda %s no encontrada." % payload["currency"])
        vals["currency_id"] = currency.id
    if ecf.get("security_code"):
        vals["l10n_do_ecf_security_code"] = ecf["security_code"]
    if ecf.get("sign_date"):
        vals["l10n_do_ecf_sign_date"] = ecf["sign_date"]
    if ecf.get("trackid"):
        vals["l10n_do_ecf_trackid"] = ecf["trackid"]
    if ecf.get("xml_b64"):
        vals["l10n_do_ecf_edi_file"] = ecf["xml_b64"]
        vals["l10n_do_ecf_edi_file_name"] = "%s.xml" % ncf
    elif ecf.get("xml_path"):
        with open(ecf["xml_path"], "rb") as fh:
            vals["l10n_do_ecf_edi_file"] = base64.b64encode(fh.read())
        vals["l10n_do_ecf_edi_file_name"] = "%s.xml" % ncf

    for line in payload["lines"]:
        taxes = _resolve_taxes(env, company, line, move_type)
        line_vals = {
            "name": line.get("description") or "/",
            "quantity": line.get("quantity", 1.0),
            "price_unit": line["price_unit"],
            "discount": line.get("discount", 0.0),
            "tax_ids": [(6, 0, taxes.ids)],
        }
        if line.get("product_id"):
            line_vals["product_id"] = line["product_id"]
        if line.get("account_id"):
            line_vals["account_id"] = line["account_id"]
        vals["invoice_line_ids"].append((0, 0, line_vals))

    move = env["account.move"].create(vals)

    # /!\ Odoo cachea el ultimo numero asignado por transaccion (cr.cache
    # 'sequence.mixin') y solo lo invalida en `write` del campo `name`, no en
    # `create`. Sin este clear, la siguiente factura numerada automaticamente en
    # la MISMA transaccion reutilizaria el numero cacheado y chocaria con este NCF
    # (duplicate key account_move_unique_name). Ver _locked_increment /
    # _get_sequence_cache en account/models/sequence_mixin.py.
    move._get_sequence_cache().clear()

    if payload.get("amount_tax") is not None:
        diff = _fix_tax_amount(
            move, float(payload["amount_tax"]), payload.get("tax_group_name")
        )
        if diff:
            _logger.info("ITBIS de %s ajustado en %s para cuadrar con DGII", ncf, diff)

    if payload.get("amount_total") is not None:
        expected = round(float(payload["amount_total"]), 2)
        if round(move.amount_total, 2) != expected:
            raise UserError(
                "El total calculado (%s) no coincide con el reportado a DGII (%s). "
                "Revisa lineas/impuestos." % (move.amount_total, expected)
            )

    # `_post` en vez de `action_post`: evita el hook de l10n_do_ncf_validation
    # (consulta el NCF en el webservice de DGII) que no aporta nada aqui.
    move._post(soft=False)

    if move.name != ncf:
        raise UserError("Odoo reemplazo el NCF %s por %s." % (ncf, move.name))
    if move.l10n_do_ecf_send_state != TERMINAL_SEND_STATE:
        raise UserError("Estado e-CF inesperado: %s" % move.l10n_do_ecf_send_state)

    # Idem tras publicar: deja la cache limpia para quien siga en la transaccion.
    move._get_sequence_cache().clear()

    # El sello (QR) se recalcula solo con la factura ya publicada.
    move._compute_l10n_do_electronic_stamp()

    move.message_post(
        body="e-CF <b>%s</b> cargado manualmente: ya estaba emitido y aceptado en DGII, "
        "por lo que Odoo no lo firmo ni lo envio de nuevo.<br/>"
        "Maximo de secuencia %s antes de la carga: %s." % (ncf, doc_type.doc_code_prefix, current_max)
    )
    return move


def load_many(env, payloads, **kwargs):
    """Carga varios e-CF ordenados por numero para no provocar saltos."""
    moves = env["account.move"]
    for payload in sorted(payloads, key=lambda p: p["ncf"]):
        move = load_ecf(env, payload, **kwargs)
        moves |= move
        print(
            "OK  %s  id=%s  total=%s  itbis=%s  estado=%s  xml=%s"
            % (
                move.name,
                move.id,
                move.amount_total,
                move.amount_tax,
                move.l10n_do_ecf_send_state,
                bool(move.l10n_do_ecf_edi_file),
            )
        )
    return moves


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
        "lines": [
            {
                "description": "Servicios facturados (e-CF ya reportado en DGII)",
                "quantity": 1,
                "price_unit": 9508.18,
                "tax_percent": 18,
            }
        ],
        # El 18% da 1,711.47: el ITBIS se cuadra al centavo reportado a DGII.
        "amount_tax": 1711.54,
        "amount_total": 11219.72,
        # Codigo de seguridad y fecha/hora de firma del e-CF emitido: con ellos
        # el sello (QR) del PDF apunta al e-CF real en DGII.
        "ecf": {"security_code": "7Yx2Kp", "sign_date": "2026-06-08 00:00:00"},
    },
]

# `odoo shell` con stdin no interactivo hace exec() de este archivo con `env` ya
# definido; si se importa como modulo no se ejecuta nada.
if "env" in globals():
    load_many(env, PAYLOADS)  # noqa: F821
    env.cr.commit()  # noqa: F821
    print("Commit hecho.")
