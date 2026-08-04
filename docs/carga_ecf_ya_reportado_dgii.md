# Cargar en Odoo una factura cuyo e-CF ya está en DGII (sin reenviarlo)

Caso: el e-CF ya fue emitido, firmado y aceptado por DGII (por otro sistema, por
contingencia, o porque se emitió fuera de Odoo) pero la factura no existe en
Odoo. Hay que crearla con su NCF real, dejarla **publicada**, y que Odoo **no**
la firme ni la mande a DGII, sin romper la emisión futura ni la secuencia.

## Por qué basta con el estado del e-CF

`l10n_do_ecf_invoicing` firma y envía en dos puntos, y **ambos filtran por
`l10n_do_ecf_send_state == "to_send"`**:

| Punto | Archivo |
|---|---|
| Al publicar | `l10n_do_ecf_invoicing/models/account_move.py:1116` (`_post`) |
| Al registrar el primer pago | `l10n_do_ecf_invoicing/models/account_move.py:1473` (`_compute_payment_state`) |

Los tres crons (`Send signed pending`, `Poll TrackID pending`, `Poll FC without
TrackID`) buscan `signed_pending` o `delivered_pending`, nunca un estado final.

Por eso la factura se **crea directamente con
`l10n_do_ecf_send_state = "delivered_accepted"`**, antes de publicarla: ninguno
de los dos caminos la toma, no se genera XML, no se llama al webservice y
ningún cron la vuelve a mirar. No hace falta parchear ni desactivar módulos.

Datos opcionales del e-CF original (si se tiene la representación impresa o el
XML): `l10n_do_ecf_security_code`, `l10n_do_ecf_sign_date`,
`l10n_do_ecf_trackid` y el XML firmado en `l10n_do_ecf_edi_file`. Con el código
de seguridad y la fecha de firma, el sello/QR del PDF de Odoo apunta al e-CF
real en DGII.

## Efecto en la secuencia (lo importante)

En RD el próximo NCF **no** sale de un contador: sale del **máximo
`sequence_number` ya usado** para el mismo tipo de documento, grupo de compañías
y dirección (venta vs. compra). Ver `_get_last_sequence_domain`
(`l10n_do_accounting/models/account_move.py:258`), el recorte al rango del pool
(`l10n_do_document_pools/models/account_move.py:29`) y `_get_last_sequence` del
`sequence.mixin` de Odoo (`ORDER BY sequence_number DESC LIMIT 1`).

| NCF que cargas | Efecto en las facturas futuras |
|---|---|
| máximo + 1 | Ninguno: la numeración sigue corrida. **Caso normal.** |
| menor al máximo (rellenar hueco) | Ninguno. |
| mayor a máximo + 1 | La próxima factura salta a `NCF + 1`; los números intermedios ya no los puede usar Odoo. |

Los tres scripts **bloquean el tercer caso** salvo que se pida explícitamente
(`allow_sequence_jump=True` / `ecf_allow_sequence_jump` en el contexto). Si hay
que cargar varios NCF, cargarlos **en orden ascendente** (las funciones
`load_many` / los payloads se ordenan solos).

Otras dos guardas:

- **NCF duplicado** en la misma compañía → rechazado.
- **NCF fuera del pool vigente** (con `l10n_do_sequence_manager` activo) →
  rechazado. Fuera del rango el movimiento es invisible para el cálculo de la
  secuencia, así que el pool podría volver a emitir ese mismo número y chocar
  con el índice único `account_move_unique_l10n_do_name_sales` al publicar.

### Detalle fino: la caché de secuencia de la transacción

Odoo guarda el último número asignado en `cr.cache['sequence.mixin']` y **solo
invalida esa caché en el `write` del campo `name`, no en el `create`**
(`account/models/sequence_mixin.py:114`). Crear una factura con `name` explícito
deja la caché vieja: la siguiente factura numerada automáticamente **en la misma
transacción** reutilizaría el número y reventaría con
`duplicate key ... account_move_unique_name`. Por eso los scripts que corren
dentro de una sola transacción (`odoo shell`, acción planificada) llaman a
`move._get_sequence_cache().clear()`. Por XML-RPC no aplica: cada llamada es su
propia transacción.

## Las tres vías (todas validadas)

| Archivo | Cómo se usa | Publica con |
|---|---|---|
| `load_ecf_already_reported.py` | `odoo shell`, payload en el propio archivo | `_post()` |
| `load_ecf_already_reported_rpc.py` | XML-RPC desde cualquier máquina, sin tocar el servidor | `action_post()` |
| `load_ecf_scheduled_action.py` | Acción **planificada** (`ir.cron`) que se corre a mano con *Ejecutar manualmente*; pegar el código una vez | `_post()` |

Las tres comparten payload:

```python
{
    "ncf": "E310000001609",
    "invoice_date": "2026-06-08",        # 08/06/2026 (dd/mm/yyyy de DGII)
    "company_vat": "131793898",          # o company_id
    "journal_id": 8,                      # opcional
    "partner": {"vat": "130674671", "name": "CLIENTE RNC 130674671",
                "payer_type": "taxpayer", "create": True},
    "lines": [{"description": "Servicios facturados", "quantity": 1,
               "price_unit": 9508.18, "tax_percent": 18}],   # o tax_ids / tax_names
    "amount_tax": 1711.54,                # opcional: cuadra el ITBIS al centavo de DGII
    "amount_total": 11219.72,             # opcional: verificación, aborta si no cuadra
    "tax_group_name": "ITBIS",            # opcional: grupo a cuadrar (por defecto el mayor)
    "income_type": "01",                  # opcional
    "origin_ncf": "E310000001500",        # notas de crédito/débito
    "ecf_modification_code": "01",        # notas de crédito/débito
    "ecf": {"security_code": "7Yx2Kp", "sign_date": "2026-06-08 00:00:00",
            "trackid": "...", "xml_path": "/ruta/E310000001609.xml"},
}
```

### Cuadrar el ITBIS al centavo (`amount_tax`)

El ITBIS calculado por Odoo puede diferir en centavos del reportado a DGII (caso
real: 9,508.18 × 18% = **1,711.47**, DGII reporta **1,711.54**). El e-CF ya
emitido es la fuente de verdad, así que el script fuerza el importe.

Lo hace escribiendo el campo `tax_totals`, que tiene un `inverse` en
`account.move` (`account/models/account_move.py:2532`, el mismo camino que el
widget de totales de la factura: *"Edit Tax amounts if you encounter rounding
issues"*): ajusta la primera línea del grupo de impuesto **y resincroniza la
línea de cobro**.

Escribir las líneas a mano (aunque sea con `check_move_validity=False`) **no
funciona**: al publicar, la línea de término de pago se recalcula desde
`needed_terms` y el asiento revienta con `The entry is not balanced`.

### 1. `odoo shell`

```bash
docker exec -i lfernandez_v19 bash -lc \
  "odoo shell -c /etc/odoo/odoo.conf -d MI_DB --no-http --max-cron-threads=0" \
  < load_ecf_already_reported.py
```

Publica con `_post()`, lo que además evita el hook de `l10n_do_ncf_validation`
(que consulta el NCF en el webservice de DGII al publicar y aquí no aporta
nada). Hace `commit` al final.

### 2. XML-RPC

```bash
ODOO_URL=http://localhost:8092 ODOO_DB=MI_DB ODOO_USER=admin ODOO_PASSWORD=admin \
  python3 load_ecf_already_reported_rpc.py
```

Sólo llamadas RPC estándar (`create` / `write` / `action_post`). Dos avisos:

- Usa `action_post`, así que si la compañía tiene
  `ncf_validation_target` en `internal` o `both`, `l10n_do_ncf_validation`
  consultará el NCF en DGII al publicar (consulta de lectura, no emite; para un
  e-CF ya aceptado debería pasar). Con el valor por defecto (`external`) las
  facturas de venta con numeración interna ni se revisan.
- Cada llamada RPC commitea: si algo falla después del `create`, el script borra
  el borrador para que no quede ocupando el NCF.

### 3. Acción planificada (se corre a mano)

Instalar una vez: **Ajustes > Técnico > Automatización > Acciones planificadas >
Nuevo**, modelo `account.move`, tipo *Ejecutar código Python*, y pegar el código
que hay debajo de la marca `INICIO CODIGO ACCION` en
`load_ecf_scheduled_action.py`. Para que **nunca corra sola**: *Ejecutar cada*
`999 semanas` y *Próxima fecha de ejecución* `2090-01-01 00:00:00` (o archivarla;
el botón manual funciona igual porque Odoo la busca con `include_not_ready=True`).

Uso normal:

1. Abrir la acción y revisar `PAYLOADS` — **ya viene cargado** con el e-CF
   `E310000001609` (RNC 130674671, 2026-06-08, base 9,508.18, ITBIS 1,711.54,
   código de seguridad `7Yx2Kp`). Guardar si se cambia algo.
2. Pulsar **Ejecutar manualmente**.
3. Vaciar `PAYLOADS` y guardar, para que quede lista para la próxima carga.

Flujo probado tal cual (DB `v19_ecf_manual`, cron instalado desde el archivo sin
tocar nada): sembrado `…1607` + `…1608`, un `method_direct_trigger` (lo que hace
el botón) creó `E310000001609` con base 9,508.18 + ITBIS 1,711.54 = 11,219.72,
fecha 2026-06-08, cliente ANDRICKSON COMERCIO INTERNACIONAL SRL, sin XML e-CF y
con sello `…CodigoSeguridad=7Yx2Kp`; la siguiente factura normal salió `…1610`.

El cron corre en su **propia transacción**: si algo no cuadra, aborta con el
error a la vista y no deja nada a medias (ni borradores ocupando el NCF). El
resumen queda en Ajustes > Técnico > Registro (`ir.logging`) y en el chatter de
cada factura.

Las guardas de secuencia se relajan con `ALLOW_SEQUENCE_JUMP` /
`ALLOW_OUT_OF_POOL` al inicio del código (déjalas en `False`).

Nota sobre el error en pantalla: `method_direct_trigger` envuelve la excepción en
un `RuntimeError` sin mensaje, así que el texto del `UserError` aparece **al final
del traceback** del diálogo.

Como un `ir.cron` delega en una `ir.actions.server`, también se puede invocar por
RPC pasando la data en el contexto, sin editar el código:

```python
server_action_id = cron.ir_actions_server_id.id
models.execute_kw(db, uid, pwd, 'ir.actions.server', 'run', [[server_action_id]], {
    'context': {'ecf_payloads': [ {...}, {...} ]},
})
```

Notas de implementación: `safe_eval` prohíbe `import` y la asignación de
atributos (`STORE_ATTR`), de ahí que el código use `partner.write({...})` y sólo
los builtins permitidos.

## Validación

Dos arneses, repetibles:

```bash
./replicate_ecf_already_reported.sh --setup   # 1ra vez: prepara v19_ecf_load
./replicate_ecf_already_reported.sh           # 13/13 — vía odoo shell
./replicate_ecf_already_reported_rpc.sh       # 15/15 — vías RPC y acción planificada
```

Los dos arneses usan la **data real** del e-CF a cargar:

| Campo | Valor |
|---|---|
| NCF | `E310000001609` |
| RNC cliente | `130674671` (ANDRICKSON COMERCIO INTERNACIONAL SRL) |
| Fecha | `08/06/2026` → `2026-06-08` |
| Facturado | 9,508.18 |
| ITBIS | 1,711.54 |
| Total | 11,219.72 |

Antes de las pruebas se siembra `E310000001607` para simular la numeración que ya
venía en producción, y el pool E31 se configura `[1, 5000]`.

Qué se comprobó (ambos verdes):

- La factura queda **publicada** con su NCF real, `delivered_accepted`, **sin
  XML e-CF** y con el sello/QR apuntando al e-CF real de DGII.
- Los importes quedan **exactos**: base 9,508.18, ITBIS 1,711.54 (ajustado desde
  el 1,711.47 del 18%), total 11,219.72, fecha 2026-06-08, cliente RNC
  130674671, y el asiento balanceado.
- **La emisión futura no se afecta**: `…1608` emitido normal → `…1609` cargado →
  la siguiente normal sale `…1610`. Lo mismo tras la acción planificada.
- **Cobrar** la factura cargada no dispara firma ni envío.
- Rellenar un hueco no mueve la numeración futura; el salto de secuencia está
  bloqueado y, si se fuerza, queda documentado en el chatter y en el log.
- El pool sigue `valid` con su `próximo número` coherente.
- La acción planificada, disparada con **Ejecutar manualmente**, carga igual que
  el loader; y cuando una guarda salta, **no queda ningún residuo** (rollback de
  su transacción).
- En el arnés de `odoo shell` se parchean la firma XML y **todo** el tráfico HTTP
  (`HTTPAdapter.send`) para que cualquier intento de contactar DGII haga fallar
  la prueba; ninguna prueba lo dispara. En el de RPC se verifica además que
  ninguna factura quedó con XML e-CF.
- La compañía de prueba **no tiene certificado de firma cargado**: si algún
  camino intentara firmar, reventaría.
