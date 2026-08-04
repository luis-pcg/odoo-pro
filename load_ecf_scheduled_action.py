# Accion PLANIFICADA (ir.cron) para cargar una factura cuyo e-CF YA fue emitido
# y aceptado por DGII, sin reenviarlo. Se ejecuta A MANO con el boton
# "Ejecutar manualmente"; nunca corre sola.
#
# INSTALAR (una sola vez, con el modo desarrollador activo):
#   Ajustes > Tecnico > Automatizacion > Acciones planificadas > Nuevo
#     Nombre                  : Cargar e-CF ya reportado en DGII
#     Modelo                  : Asiento contable (account.move)
#     Ejecutar cada           : 999 semanas
#     Proxima fecha ejecucion : 2090-01-01 00:00:00   <- para que nunca corra sola
#     Codigo                  : todo lo que hay debajo de INICIO CODIGO ACCION
#
#   O por shell:
#     env['ir.cron'].create({
#         'name': 'Cargar e-CF ya reportado en DGII',
#         'model_id': env.ref('account.model_account_move').id,
#         'state': 'code',
#         'code': open('/ruta/load_ecf_scheduled_action.py').read()
#                     .split('INICIO CODIGO ACCION')[-1].split('\n', 1)[1],
#         'interval_number': 999,
#         'interval_type': 'weeks',
#         'nextcall': '2090-01-01 00:00:00',
#         'user_id': env.ref('base.user_admin').id,
#     })
#
# USAR:
#   1. Abrir la accion planificada y revisar/ajustar PAYLOADS (ya viene cargado
#      con el e-CF E310000001609) y guardar.
#   2. Pulsar "Ejecutar manualmente". Cada factura queda publicada con su NCF
#      real, en estado e-CF "delivered_accepted", sin XML y sin envio a DGII.
#   3. Vaciar PAYLOADS y guardar, para que quede lista para la proxima carga.
#
#   Si algo no cuadra, la accion aborta con el error a la vista y NO deja nada a
#   medias: el cron corre en su propia transaccion y hace rollback completo.
#   El resumen de lo cargado queda en Ajustes > Tecnico > Registro (ir.logging) y
#   en el chatter de cada factura.
#
#   Tambien se puede invocar por RPC sin editar el codigo (el cron delega en una
#   ir.actions.server, y esa si acepta contexto):
#     server_action_id = cron.ir_actions_server_id.id
#     models.execute_kw(db, uid, pwd, 'ir.actions.server', 'run',
#                       [[server_action_id]], {'context': {'ecf_payloads': [ {...} ]}})
#
# OJO: al ser una accion planificada, "Ejecutar manualmente" funciona incluso si
# el cron esta archivado (Odoo usa include_not_ready=True), asi que archivarla es
# una forma valida de asegurar que jamas corra sola.
#
# Por que no se envia a DGII y como afecta la secuencia: ver
# load_ecf_already_reported.py y docs/carga_ecf_ya_reportado_dgii.md.
#
# ------------------------------ INICIO CODIGO ACCION -------------------------
# Pegar desde aqui en el campo "Codigo Python" de la accion planificada.

# ───────────────────────── e-CF A CARGAR (EDITAR) ─────────────────────────
# Una entrada por factura; se cargan en orden ascendente de NCF.
# Tras ejecutar, vaciar la lista para no recargar por error (de todos modos la
# guarda de NCF duplicado lo impide).
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
        # Con codigo de seguridad y fecha de firma, el sello (QR) del PDF apunta
        # al e-CF real en DGII.
        "ecf": {"security_code": "7Yx2Kp", "sign_date": "2026-06-08 00:00:00"},
    },
]

SALE_TYPES = ["out_invoice", "out_refund", "out_receipt"]
PURCHASE_TYPES = ["in_invoice", "in_refund", "in_receipt"]

ctx = env.context
# PAYLOADS manda (accion planificada ejecutada a mano). ecf_payloads en el
# contexto es el camino para invocarla por RPC sin editar el codigo.
payloads = PAYLOADS or ctx.get("ecf_payloads") or (
    [ctx["ecf_payload"]] if ctx.get("ecf_payload") else []
)
# Interruptores de las guardas de secuencia. Dejalos en False salvo que sepas
# exactamente por que estas saltando numeros (ver cabecera del archivo).
ALLOW_SEQUENCE_JUMP = False
ALLOW_OUT_OF_POOL = False

allow_jump = ALLOW_SEQUENCE_JUMP or bool(ctx.get("ecf_allow_sequence_jump"))
allow_out_of_pool = ALLOW_OUT_OF_POOL or bool(ctx.get("ecf_allow_out_of_pool"))
if not payloads:
    raise UserError(
        "No hay datos que cargar: rellena PAYLOADS en el codigo de la accion "
        "planificada (o pasa ecf_payloads en el contexto si la invocas por RPC)."
    )

loaded = []

for payload in sorted(payloads, key=lambda p: p["ncf"]):
    company = env.company
    if payload.get("company_id"):
        company = env["res.company"].browse(payload["company_id"])
    elif payload.get("company_vat"):
        company = env["res.company"].search(
            [("vat", "=", payload["company_vat"])], limit=1
        )
    if not company:
        raise UserError("Compania no encontrada para %s" % payload["ncf"])

    move_type = payload.get("move_type") or "out_invoice"
    ncf = str(payload["ncf"]).strip().upper()
    if len(ncf) not in (11, 13) or ncf[0] not in ("B", "E") or not ncf[3:].isdigit():
        raise UserError("NCF %s invalido (11 caracteres para B, 13 para E)" % ncf)
    number = int(ncf[3:])

    doc_type = env["l10n_latam.document.type"].search(
        [("doc_code_prefix", "=", ncf[:3]), ("country_id", "=", company.country_id.id)],
        limit=1,
    )
    if not doc_type:
        raise UserError("No existe tipo de documento con prefijo %s" % ncf[:3])

    if payload.get("journal_id"):
        journal = env["account.journal"].browse(payload["journal_id"])
    else:
        jtype = "purchase" if move_type in ("in_invoice", "in_refund") else "sale"
        journals = env["account.journal"].search(
            [
                ("type", "=", jtype),
                ("company_id", "=", company.id),
                ("l10n_latam_use_documents", "=", True),
            ]
        )
        journal = journals.filtered(
            lambda j: (
                doc_type
                in j.l10n_do_document_type_ids.mapped("l10n_latam_document_type_id")
            )
        )[:1]
        journal = journal or journals[:1]
    if not journal:
        raise UserError("No hay diario con documentos fiscales para %s" % ncf)

    pdata = payload.get("partner") or {}
    if pdata.get("id"):
        partner = env["res.partner"].browse(pdata["id"])
    elif pdata.get("vat"):
        partner = env["res.partner"].search([("vat", "=", pdata["vat"])], limit=1)
    else:
        partner = env["res.partner"].search([("name", "=", pdata.get("name"))], limit=1)
    if not partner:
        if not pdata.get("create"):
            raise UserError(
                "Cliente no encontrado para %s (usa partner['create'])" % ncf
            )
        partner = env["res.partner"].create(
            {
                "name": pdata.get("name") or pdata.get("vat"),
                "vat": pdata.get("vat"),
                "l10n_do_dgii_tax_payer_type": pdata.get("payer_type") or "taxpayer",
                "country_id": company.country_id.id,
            }
        )
    if not partner.l10n_do_dgii_tax_payer_type:
        if not pdata.get("payer_type"):
            raise UserError(
                "El cliente %s requiere tipo de contribuyente DGII"
                % partner.display_name
            )
        # write() y no asignacion de atributo: safe_eval prohibe STORE_ATTR.
        partner.write({"l10n_do_dgii_tax_payer_type": pdata["payer_type"]})

    # Guarda 1: NCF duplicado.
    dup = (
        env["account.move"]
        .sudo()
        .search(
            [
                ("name", "=", ncf),
                ("company_id", "=", company.id),
                ("state", "!=", "cancel"),
            ]
        )
    )
    if dup:
        raise UserError("El NCF %s ya existe en el asiento %s" % (ncf, dup.ids))

    # Guarda 2: no adelantar la numeracion futura.
    parent = company.parent_id or company
    company_ids = (
        parent | env["res.company"].sudo().search([("parent_id", "=", parent.id)])
    ).ids
    move_types = PURCHASE_TYPES if move_type in PURCHASE_TYPES else SALE_TYPES
    last = (
        env["account.move"]
        .sudo()
        .search(
            [
                ("l10n_latam_document_type_id", "=", doc_type.id),
                ("company_id", "in", company_ids),
                ("move_type", "in", move_types),
                ("name", "not in", ["/", "", False]),
            ],
            order="sequence_number desc",
            limit=1,
        )
    )
    current_max = last.sequence_number or 0
    if number > current_max + 1 and not allow_jump:
        raise UserError(
            "El NCF %s adelanta la secuencia: el maximo actual de %s es %s, asi que las "
            "facturas nuevas pasarian de %s a %s y los numeros %s..%s quedarian inutilizables. "
            "Carga primero los NCF faltantes o pon ALLOW_SEQUENCE_JUMP = True."
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

    # Guarda 3: con gestor de secuencias, el NCF debe caer dentro del pool vigente.
    if company.l10n_do_sequence_manager:
        pool = journal.l10n_do_document_type_ids.filtered(
            lambda d: d.l10n_latam_document_type_id == doc_type
        )[:1]
        if (
            pool
            and not (pool.sequence_start <= number <= pool.sequence_end)
            and not allow_out_of_pool
        ):
            raise UserError(
                "El NCF %s queda fuera del pool vigente [%s, %s]: el pool podria volver a emitir "
                "ese numero y chocar con el indice unico al publicar. Ajusta el pool o pon "
                "ALLOW_OUT_OF_POOL = True."
                % (ncf, pool.sequence_start, pool.sequence_end)
            )

    ecf = payload.get("ecf") or {}
    vals = {
        "move_type": move_type,
        "journal_id": journal.id,
        "partner_id": partner.id,
        "invoice_date": payload["invoice_date"],
        "date": payload.get("date") or payload["invoice_date"],
        "l10n_latam_document_type_id": doc_type.id,
        "name": ncf,
        # Estado terminal ANTES de publicar: ni _post ni _compute_payment_state de
        # l10n_do_ecf_invoicing firman/envian nada que no este en "to_send".
        "l10n_do_ecf_send_state": "delivered_accepted",
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
        currency = env["res.currency"].search(
            [("name", "=", payload["currency"])], limit=1
        )
        if not currency:
            raise UserError("Moneda %s no encontrada" % payload["currency"])
        vals["currency_id"] = currency.id
    if ecf.get("security_code"):
        vals["l10n_do_ecf_security_code"] = ecf["security_code"]
    if ecf.get("sign_date"):
        vals["l10n_do_ecf_sign_date"] = ecf["sign_date"]
    if ecf.get("trackid"):
        vals["l10n_do_ecf_trackid"] = ecf["trackid"]
    if ecf.get("xml_b64"):
        vals["l10n_do_ecf_edi_file"] = ecf["xml_b64"]
        vals["l10n_do_ecf_edi_file_name"] = ncf + ".xml"

    for line in payload["lines"]:
        tax_ids = list(line.get("tax_ids") or [])
        for tax_name in line.get("tax_names") or []:
            tax = env["account.tax"].search(
                [("name", "=", tax_name), ("company_id", "=", company.id)], limit=1
            )
            if not tax:
                raise UserError("Impuesto %s no encontrado" % tax_name)
            tax_ids.append(tax.id)
        if line.get("tax_percent") is not None:
            use = "purchase" if move_type in ("in_invoice", "in_refund") else "sale"
            tax = env["account.tax"].search(
                [
                    ("company_id", "=", company.id),
                    ("type_tax_use", "=", use),
                    ("amount_type", "=", "percent"),
                    ("amount", "=", float(line["tax_percent"])),
                ],
                limit=1,
            )
            if not tax:
                raise UserError(
                    "No hay impuesto de %s%% (%s)" % (line["tax_percent"], use)
                )
            tax_ids.append(tax.id)
        line_vals = {
            "name": line.get("description") or "/",
            "quantity": line.get("quantity", 1.0),
            "price_unit": line["price_unit"],
            "discount": line.get("discount", 0.0),
            "tax_ids": [Command.set(tax_ids)],
        }
        if line.get("product_id"):
            line_vals["product_id"] = line["product_id"]
        if line.get("account_id"):
            line_vals["account_id"] = line["account_id"]
        vals["invoice_line_ids"].append(Command.create(line_vals))

    move = env["account.move"].with_company(company).create(vals)

    # /!\ Odoo cachea el ultimo numero asignado por transaccion y solo invalida esa
    # cache en `write` del campo name, no en `create`. Sin este clear, la siguiente
    # factura numerada automaticamente en la MISMA transaccion reutilizaria el
    # numero y chocaria con este NCF.
    move._get_sequence_cache().clear()

    # Cuadra el impuesto al centavo reportado a DGII (el e-CF emitido es la
    # verdad). Se escribe `tax_totals`, que tiene un inverse en account.move (el
    # mismo camino que el widget de totales de la factura): ajusta la linea del
    # grupo y resincroniza la de cobro. Tocar las lineas a mano descuadra el
    # asiento al publicar ("The entry is not balanced").
    if payload.get("amount_tax") is not None:
        target_tax = round(float(payload["amount_tax"]), 2)
        diff = round(target_tax - move.amount_tax, 2)
        if diff:
            totals = move.tax_totals
            groups = []
            for subtotal in totals.get("subtotals") or []:
                for group in subtotal.get("tax_groups") or []:
                    groups.append(group)
            if not groups:
                raise UserError("La factura %s no tiene grupos de impuestos" % ncf)
            chosen = groups[0]
            for group in groups:
                if payload.get("tax_group_name"):
                    if group.get("group_name") == payload["tax_group_name"]:
                        chosen = group
                elif abs(group.get("tax_amount_currency") or 0.0) > abs(
                    chosen.get("tax_amount_currency") or 0.0
                ):
                    chosen = group
            chosen["tax_amount_currency"] = round(
                (chosen.get("tax_amount_currency") or 0.0) + diff, 2
            )
            move.write({"tax_totals": totals})
            if round(move.amount_tax, 2) != target_tax:
                raise UserError(
                    "No se pudo cuadrar el impuesto de %s: quedo en %s y DGII reporta %s"
                    % (ncf, move.amount_tax, target_tax)
                )

    if payload.get("amount_total") is not None:
        if round(move.amount_total, 2) != round(float(payload["amount_total"]), 2):
            raise UserError(
                "El total calculado (%s) no coincide con el reportado a DGII (%s)"
                % (move.amount_total, payload["amount_total"])
            )

    # `_post` en vez de `action_post`: evita el hook de l10n_do_ncf_validation, que
    # consulta el NCF en el webservice de DGII y aqui no aporta nada.
    move._post(soft=False)
    move._get_sequence_cache().clear()

    if move.name != ncf:
        raise UserError("Odoo reemplazo el NCF %s por %s" % (ncf, move.name))
    if move.l10n_do_ecf_send_state != "delivered_accepted":
        raise UserError(
            "Estado e-CF inesperado en %s: %s" % (ncf, move.l10n_do_ecf_send_state)
        )

    # El sello (QR) solo se calcula con la factura ya publicada.
    move._compute_l10n_do_electronic_stamp()
    move.message_post(
        body="e-CF <b>%s</b> cargado con la accion planificada: ya estaba emitido y aceptado "
        "en DGII, por lo que Odoo no lo firmo ni lo envio de nuevo. Maximo de secuencia "
        "%s antes de la carga: %s." % (ncf, doc_type.doc_code_prefix, current_max)
    )
    loaded.append((move.id, move.name, move.amount_total))

log("e-CF cargados sin reenvio a DGII: %s" % loaded)
