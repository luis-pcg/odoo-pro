# Diseño técnico — Módulo de envío de ventas a MsMall

Documento técnico del módulo `pos_msmall_sales_export`, que envía las ventas de un punto de venta de Odoo al API de recepción de ventas de MsMall bajo el contrato `msmall_sales_v1`.

---

## 1. Contexto de la instancia

| Elemento | Situación en la instancia del cliente |
|---|---|
| Versión | Odoo 17.0 Enterprise |
| Compañía | Una sola, moneda DOP |
| Puntos de venta | Varios configurados; **solo SAMBIL** queda habilitado para enviar al API |
| Facturación | Cada venta del punto de venta genera una factura con comprobante fiscal (`l10n_do_fiscal_number`) |
| Diario de facturación | Compartido entre los puntos de venta, por lo que **el filtro de alcance se hace por `pos.config`, nunca por diario ni por compañía** |
| Localización | `l10n_do_accounting` y facturación electrónica instaladas; conviven comprobantes B02, B01 y E32 |

El módulo no modifica la interfaz del cajero ni el flujo de facturación: es un proceso de trastienda que lee ventas ya cerradas y las publica al API.

---

## 2. Arquitectura general

```
pos.order (config_id = SAMBIL)
        │
        ▼
[ extractor ] ──► msmall.sales.batch ──► msmall.sales.chunk ──► POST /api/v1/exporter/sync/ingest
        │                 │                      │                          │
        │                 │                      └── respuesta ─────────────┘
        │                 ▼
        │           conciliación de contadores
        ▼
   ir.cron (programación)          msmall.token ──► POST /auth/token · /auth/refresh · /auth/revoke
```

Cuatro piezas:

1. **Extractor**: selecciona las ventas pendientes del punto de venta habilitado y las transforma al contrato.
2. **Lote (`msmall.sales.batch`)**: unidad de envío y de conciliación, con su `batch_id` estable.
3. **Fragmento (`msmall.sales.chunk`)**: cada petición HTTP efectiva; conserva su payload y la respuesta.
4. **Almacén de tokens (`msmall.token`)**: ciclo de vida de las credenciales de sesión, con control de concurrencia.

---

## 3. Modelo de datos

### 3.1 `pos.config` — campos añadidos

| Campo | Tipo | Uso |
|---|---|---|
| `msmall_export_enabled` | Boolean | Interruptor del envío. Solo el punto de venta de Sambil lo tiene activo |
| `msmall_mall_id` | Char | UUID del centro comercial entregado por MsMall |
| `msmall_local_id` | Char | UUID del local entregado por MsMall |
| `msmall_granularity` | Selection `transaction` / `daily` | Modalidad habilitada por el proveedor para el local |
| `msmall_chunk_size` | Integer | Filas por fragmento; valor acordado en certificación |
| `msmall_base_url` | Char | URL del ambiente (certificación o producción) |
| `msmall_tz` | Char | Zona horaria comercial para `fecha_venta` / `hora_venta` |

Todos los campos van en una pestaña propia de la ficha del punto de venta, visibles solo para el grupo de administración de POS.

### 3.2 `msmall.sales.batch`

| Campo | Tipo | Uso |
|---|---|---|
| `name` | Char | `batch_id` enviado al proveedor, estable y único |
| `config_id` | Many2one `pos.config` | Punto de venta origen |
| `granularity` | Selection | Modalidad del lote; un lote nunca mezcla modalidades |
| `date_from`, `date_to` | Datetime | Ventana cubierta |
| `state` | Selection | `draft` → `queued` → `sending` → `sent` → `done` / `failed` / `review` |
| `row_count` | Integer | Filas extraídas del origen |
| `received`, `inserted`, `updated`, `ventas_inserted`, `ventas_updated` | Integer | Contadores devueltos por el API, sumados por fragmento |
| `attempts` | Integer | Intentos consumidos |
| `next_retry_at` | Datetime | Próximo reintento programado |
| `last_error` | Text | Último detalle sanitizado |

### 3.3 `msmall.sales.chunk`

| Campo | Tipo | Uso |
|---|---|---|
| `batch_id` | Many2one | Lote al que pertenece |
| `chunk_index`, `chunk_total` | Integer | Posición del fragmento, empezando en 1 |
| `payload` | Text | JSON exacto enviado; se conserva hasta conciliar |
| `http_status` | Integer | Código devuelto |
| `response` | Text | Cuerpo de la respuesta, sanitizado |
| `state` | Selection | `pending` / `sent` / `failed` |

### 3.4 `msmall.sales.row`

Traza fila enviada ↔ documento de Odoo, que es lo que permite conciliar y no reenviar dos veces lo mismo.

| Campo | Tipo | Uso |
|---|---|---|
| `chunk_id` | Many2one | Fragmento donde viajó |
| `move_id` | Many2one `account.move` | Factura origen (modalidad `transaction`) |
| `documento_numero` | Char | Número fiscal enviado |
| `sale_date` | Date | Fecha comercial |
| `resumen_id` | Char | Identificador del resumen (modalidad `daily`) |

Índice único por `(config_id, granularity, documento_numero o resumen_id)` para garantizar que un mismo documento no entre dos veces en lotes distintos.

### 3.5 `msmall.token`

| Campo | Tipo | Uso |
|---|---|---|
| `config_id` | Many2one `pos.config` | Una cuenta de servicio por local |
| `access_token`, `refresh_token` | Char | Credenciales de sesión, no expuestas en vistas |
| `expires_at`, `refresh_expires_at` | Datetime | Calculados con `expires_in` y `refresh_expires_in` de la respuesta, nunca con constantes |
| `scope` | Char | Alcance devuelto por el proveedor |

---

## 4. Autenticación y ciclo de tokens

Secuencia implementada:

1. Si no hay token almacenado, se solicita con `client_id` / `client_secret` en `POST /auth/token`.
2. Antes de cada envío se evalúa la vida restante del token. Con **menos del 20 % restante** se renueva mediante `POST /auth/refresh`.
3. La renovación es **exclusiva**: se toma el registro con bloqueo de fila antes de renovar.

```python
self.env.cr.execute(
    "SELECT id FROM msmall_token WHERE id = %s FOR UPDATE NOWAIT", (token.id,)
)
```

   Si otro proceso ya está renovando, el bloqueo falla de inmediato y el proceso actual reintenta la lectura en lugar de pedir una segunda renovación. Esto es obligatorio: el proveedor revoca el token anterior en cada rotación, y dos renovaciones simultáneas dejan la integración con un token inválido.
4. El nuevo par se guarda de forma atómica **antes** de darse por válido, en su propia transacción, de modo que una caída posterior no pierda el `refresh_token` vigente.
5. Si `POST /auth/refresh` responde 401, se vuelve a autenticar con `client_id` / `client_secret`.
6. `POST /auth/revoke` se expone como acción manual para retiro del servidor o rotación por incidente.

El token se reutiliza entre lotes: no se solicita uno nuevo por envío, en respeto de los límites por IP del proveedor (≈20/min en `/auth/token`, 30/min en `/auth/refresh`).

---

## 5. Extracción y mapeo de datos

### 5.1 Selección del origen

```python
domain = [
    ("config_id", "=", config.id),
    ("state", "in", ("paid", "done", "invoiced")),
    ("account_move", "!=", False),
    ("msmall_row_ids", "=", False),      # aún no enviada
    ("date_order", ">=", window_start),
    ("date_order", "<", window_end),
]
```

La ventana se cierra sobre sesiones ya cerradas, para no enviar ventas de una sesión en curso que todavía puede recibir movimientos.

### 5.2 Modalidad `transaction` — una fila por venta

| Campo del contrato | Origen en Odoo |
|---|---|
| `documento_tipo` | Valor estable derivado del tipo de comprobante (`l10n_latam_document_type_id`): `factura` |
| `documento_numero` | `account.move.l10n_do_fiscal_number` — el NCF o e-NCF, enviado como texto para conservar ceros iniciales |
| `fecha_venta` | `pos.order.date_order` convertido a la zona horaria comercial, formato `YYYY-MM-DD` |
| `hora_venta` | Misma conversión, formato `HH:MM:SS` |
| `total_bruto` | `account.move.amount_total` |
| `total_impuesto` | `account.move.amount_tax` |
| `total_neto` | `account.move.amount_untaxed` |

Los importes se serializan como números JSON con punto decimal, sin símbolo de moneda ni separador de miles.

### 5.3 Modalidad `daily` — una fila por día

| Campo del contrato | Origen en Odoo |
|---|---|
| `fecha_venta` | Día comercial consolidado |
| `resumen_id` | Identificador estable por día y local: `{local}-{YYYYMMDD}`; nunca se reutiliza para otro día |
| `cantidad_documentos` | Cantidad de facturas incluidas |
| `total_bruto`, `total_impuesto`, `total_neto` | Sumas del día sobre los mismos campos de §5.2 |

**Definición del día comercial.** Las sesiones de caja del cliente abren por la tarde y cierran después de la medianoche. El módulo expone la regla como configuración: día calendario (`date_order`) o día de la sesión. La regla se fija antes de certificar, porque determina los totales que MsMall conciliará contra el origen.

### 5.4 Devoluciones

Los reembolsos del punto de venta que no generan nota de crédito no tienen número fiscal y, por lo tanto, no tienen representación en el contrato. El módulo los deja fuera del envío y los registra en la cola de revisión, hasta que se acuerde con MsMall el tratamiento (ajuste del resumen del día o documento propio).

---

## 6. Envío, fragmentación e idempotencia

Estructura de la petición:

```json
{
  "mall_id": "{MALL_ID}",
  "local_id": "{LOCAL_ID}",
  "rows": [ ... ],
  "meta": {
    "contract_type": "msmall_sales_v1",
    "granularity": "transaction",
    "batch_id": "ZFRIKI-SAMBIL-20260917-001",
    "chunk_index": 1,
    "chunk_total": 3
  }
}
```

- El `batch_id` se genera una sola vez al crear el lote y **no cambia entre reintentos**.
- Los fragmentos conservan el mismo `batch_id` y varían `chunk_index` / `chunk_total`.
- Un reintento reenvía **el mismo payload almacenado**, no uno reconstruido: es lo que garantiza que la identidad lógica del proveedor (local + fecha + documento, o local + fecha + `resumen_id`) resuelva como actualización y no como venta nueva.
- Ante un corte tras enviar y antes de recibir respuesta, el fragmento queda en `pending` y se reenvía igual; la idempotencia del proveedor decide si inserta o actualiza.

---

## 7. Conciliación

Al recibir 200 con `accepted: true`:

1. Se suman `received` de todos los fragmentos del lote y se comparan con `row_count`.
2. Se verifica que `ventas_inserted + ventas_updated` corresponda a lo enviado.
3. Se comparan los totales monetarios por fecha entre Odoo y los contadores del API.
4. Solo entonces el lote pasa a `done` y sus filas quedan marcadas como enviadas.

Si los contadores no cuadran, el lote pasa a `review` y no se reintenta de forma automática.

---

## 8. Errores y reintentos

| Código | Acción del módulo |
|---|---|
| 200 | Conciliar y cerrar el fragmento |
| 400 | Detener y enviar a cola de revisión; no reintentar sin corrección |
| 401 | Renovar o reautenticar y repetir una vez |
| 403 | Detener; revisar `mall_id` / `local_id` y credenciales |
| 409 | Detener y notificar: webservice deshabilitado para el local |
| 422 | Cola de revisión con el detalle devuelto; no reintentar sin corrección |
| 429 | Esperar y reintentar respetando `Retry-After` |
| 5xx / timeout / error de red | Reintentar el mismo payload con espera progresiva |

Espera entre reintentos: 5, 15, 30 y 60 segundos con variación aleatoria. Superado el umbral de intentos, el lote pasa a `review` y se notifica al responsable.

---

## 9. Programación

Un `ir.cron` por modalidad:

- **`transaction`**: ejecución cada 15 minutos; toma las ventas facturadas de sesiones cerradas que aún no se han enviado.
- **`daily`**: ejecución una vez al día, después del cierre de la última sesión, consolidando el día comercial anterior.

El cron procesa primero los lotes en `queued` cuyo `next_retry_at` ya venció, y luego crea el lote nuevo. Esto evita que un lote fallido quede atrás mientras se siguen generando envíos nuevos.

---

## 10. Seguridad

- `client_id` y `client_secret` se guardan como parámetros del sistema de lectura restringida, nunca en código ni en el módulo.
- `access_token` y `refresh_token` viven en `msmall.token`, sin exposición en vistas ni en reportes.
- La bitácora registra fecha y hora con zona, ambiente, `batch_id`, fragmento, identificadores, código HTTP, duración y contadores. **No** registra secretos ni el encabezado de autorización completo.
- Toda comunicación por HTTPS con validación de certificado.
- La acción de revocación queda disponible para rotación por incidente.

---

## 11. Interfaz de usuario

| Vista | Contenido |
|---|---|
| Ficha del punto de venta | Pestaña de configuración del envío (§3.1) y botón de prueba de conectividad en vacío |
| Lista de lotes | Fecha, modalidad, estado, filas, contadores devueltos, intentos |
| Ficha del lote | Fragmentos, payload conservado, respuestas, último error, botones de reenvío y de marcar como revisado |
| Cola de revisión | Filtro sobre los lotes en estado `review` |

Acceso restringido al grupo de administración del punto de venta.

---

## 12. Pruebas

Pruebas automatizadas con el API simulado, sin salida a la red:

- Construcción del payload en ambas modalidades y validación del formato de fechas, horas e importes.
- Estabilidad del `documento_numero` y del `resumen_id` entre reenvíos.
- Renovación de token al cruzar el 20 % de vida restante y exclusión mutua entre dos procesos.
- Reintento tras 429 con `Retry-After` y tras 5xx con espera progresiva.
- Reenvío del mismo payload ante respuesta perdida, sin generar fila nueva.
- Fragmentación: suma de `received` igual al total enviado.
- Aislamiento: una venta de otro punto de venta nunca entra en el lote.

Los casos anteriores cubren la evidencia que exige la certificación T01–T12.

---

## 13. Estructura del módulo

```
pos_msmall_sales_export/
├── __manifest__.py
├── models/
│   ├── pos_config.py            # configuración por punto de venta
│   ├── msmall_token.py          # ciclo de vida de tokens
│   ├── msmall_sales_batch.py    # lotes, fragmentos y conciliación
│   ├── msmall_sales_row.py      # traza fila ↔ documento
│   └── pos_order.py             # marcado de ventas enviadas
├── lib/
│   ├── msmall_client.py         # cliente HTTP, reintentos y errores
│   └── msmall_payload.py        # transformación al contrato
├── data/
│   └── ir_cron.xml
├── security/
│   ├── ir.model.access.csv
│   └── res_groups.xml
├── views/
│   ├── pos_config_views.xml
│   └── msmall_sales_batch_views.xml
└── tests/
    ├── test_payload.py
    ├── test_token.py
    └── test_dispatch.py
```

---

## 14. Fuera de alcance

- Envío desde otros puntos de venta de la instancia.
- Las alternativas descartadas por el cliente: FTP y la aplicación MsExportador.
- El endpoint `/api/v1/ingesta`, reservado por el proveedor al flujo interactivo de MsMall Web.
- Reportes o tableros de análisis sobre lo enviado, más allá de la pantalla de seguimiento de lotes.
