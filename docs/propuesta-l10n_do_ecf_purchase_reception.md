# Propuesta de desarrollo — `l10n_do_ecf_purchase_reception`

**Recepción de e-CF de proveedores desde Fixcal → Órdenes de Compra / Facturas de Proveedor en Odoo**

| | |
|---|---|
| **Autor** | Luis Fernández |
| **Revisor** | Daniel Pereyra |
| **Fecha** | 2026-08-06 |
| **Origen** | Sesión técnica Daniel / Luis del 2026-08-04 |
| **Estado** | Propuesta — pendiente de aprobación antes de escribir código |
| **Versiones Odoo objetivo** | 17.0 (referencia), 15.0 y 19.0 (backport/forward-port) |
| **API** | Fixcal Emission Service API v3.0 — `https://test.fixcal.do` (sandbox) / `https://api.fixcal.do` (producción) |

---

## 0. Resumen ejecutivo

Hoy los clientes de INDEXA **emiten** e-CF hacia Fixcal sin problema (`l10n_do_ecf_invoicing`), y los que reciben XML de software de terceros lo hacen con módulos **hechos a la medida** (`l10n_do_ecf_reception`, `l10n_do_ecf_reception_workflow`, Babel/don Papito). Lo que **no existe** es el camino inverso genérico: cuando un proveedor nos factura electrónicamente, esa factura llega al API de Fixcal, se guarda ahí, y **nunca entra a Odoo**.

Este módulo cierra ese hueco:

```
Proveedor  ──POST e-CF──▶  Fixcal API  ──[guarda DB + XML en GCS]──▶  ARECF firmado al proveedor
                                │
                                │  GET /fe/recepcion/api/invoices/all   (cron diario)
                                │  GET /{encf}/xml                      (bajo demanda)
                                ▼
                    ┌───────────────────────────────┐
                    │  MODELO INTERMEDIO EN ODOO    │  ← aquí se valida, se mapea, se aprueba
                    │  l10n_do.ecf.received.document│
                    └───────────────────────────────┘
                                │
             ┌──────────────────┼──────────────────┬────────────────────┐
             ▼                  ▼                  ▼                    ▼
      purchase.order      PO + recepción      account.move        POST /acecf/
       (borrador)          + factura          (in_invoice)      (aprobación/rechazo
                                                                  comercial a DGII)
```

**Principio de diseño rector (acordado en sesión):** el modelo intermedio **aísla al core**. La data sucia del proveedor nunca toca `account.move` ni `purchase.order` directamente; sólo entra al core cuando ya está validada y mapeada.

**Decisión tomada sobre el mapeo de productos:** **no se usa IA/LLM ni MCP**. El costo por línea es prohibitivo a escala y el resultado no es determinista. En su lugar se usa el mecanismo nativo de Odoo `product.supplierinfo` (Vendor Product Name / Vendor Product Code) como memoria de aprendizaje: el operario mapea una vez, el sistema recuerda para siempre. Se refuerza con una capa de sugerencia por similitud textual en PostgreSQL (`pg_trgm`), costo cero.

---

## 1. Alcance

### 1.1 Dentro del alcance

1. Conector Odoo ↔ API Fixcal para los endpoints de **Provider Reception**.
2. Acción planificada (cron) que descarga las facturas recibidas del día anterior.
3. Modelo intermedio (documento recibido + líneas) con máquina de estados.
4. Descarga y almacenamiento del XML completo (bajo demanda, no en el cron).
5. Motor de mapeo de productos con aprendizaje vía `product.supplierinfo` + wizard de mapeo masivo.
6. Mapeo de impuestos ITBIS/ISC/retenciones desde `IndicadorFacturacion` y tablas del XML.
7. Manejo de moneda extranjera y tasa de cambio del comprobante.
8. Generación de: `purchase.order` borrador / PO confirmada + recepción / `account.move` (factura de proveedor).
9. Aprobación comercial (ACECF): aprobar o rechazar el comprobante contra DGII vía Fixcal.
10. Validación anti-duplicados a nivel de modelo intermedio y a nivel de `account.move`.
11. Compatibilidad 15.0 / 17.0 / 19.0.
12. Colección **Bruno** versionada dentro del módulo para probar el API desde el código.

### 1.2 Fuera del alcance (fase 1)

- Reemplazar o tocar `l10n_do_ecf_reception` / `_workflow` (siguen operando para Amadita, Cosegla, Unicast).
- El endpoint público de recepción de terceros (`POST /fe/recepcion/api/ecf`): los proveedores apuntan **directo a Fixcal**, Odoo no expone ese endpoint.
- Emisión de ANECF (anulación de comprobantes propios) — ya cubierto por otro flujo.
- Conciliación automática de pagos a proveedores.
- Sucursales DGII (`Sucursal` en el XML): se registra el dato, se pospone la lógica multi-sucursal.

---

## 2. Contrato del API — verificado

> Todo lo de esta sección fue verificado el **2026-08-06** contra `https://test.fixcal.do` con la API key de sandbox que ya vive en `l10n_do_ecf_invoicing/lib/ecf_config.py`. Los ejemplos son respuestas reales, no inventadas.

### 2.1 Autenticación

| Header | Valor | Nota |
|---|---|---|
| `x-api-key` | API key de la empresa | Validada en el API Gateway. Ya está en `ECFConfig._API_KEYS` |
| `env` | `TesteCF` \| `CerteCF` \| `eCF` | Selecciona ambiente DGII. Default `TesteCF` |

Los endpoints de recepción **no requieren el token DGII** (`x-token`), a diferencia de emisión. Esto simplifica el conector: no hay que pasar por `obtain_token`.

**Base URLs:** `TesteCF`/`CerteCF` → `https://test.fixcal.do` · `eCF` → `https://api.fixcal.do`

### 2.2 `GET /fe/recepcion/api/invoices/count` — conteo

Headers: `start-date` (DD-MM-YYYY, req), `end-date` (DD-MM-YYYY, req), `buyer-rnc` (opt), `env` (opt).

```json
{"total_invoices":17,"total_amount":"25866800.22","buyer_rnc":null,
 "start_date":"01-01-2025","end_date":"31-12-2026","env":"TesteCF"}
```

**Uso:** health-check del cron y control de completitud (comparar `total_invoices` con lo que realmente se creó en Odoo).

### 2.3 `GET /fe/recepcion/api/invoices/all` — listado (endpoint principal del cron)

Headers: `start-date` (req), `end-date` (req), `buyer-rnc` (opt), `env` (opt).

```json
{
  "count": 17,
  "invoices": [
    {
      "encf": "E310000000034",
      "ecf_type": "31",
      "date_received": "2026-07-21T17:15:45.102358",
      "date_issued": "2020-04-01T00:00:00",
      "total_amount": "25000000.00",
      "provider_rnc": "131880681",
      "provider_name": "DOCUMENTOS ELECTRONICOS DE 02",
      "xml_gcs_path": "gs://dev-ecf-xmls/TesteCF/ecf/131566332/received/2020/04/E310000000034.xml",
      "approval_status": "pending",
      "approval_datetime": null
    }
  ],
  "start_date": "01-01-2025", "end_date": "31-12-2026", "env": "TesteCF"
}
```

Campos de `ReceivedInvoice`: `encf`, `ecf_type`, `date_received`, `date_issued`, `total_amount`, `provider_rnc`, `provider_name`, `xml_gcs_path`, `approval_status` (`pending`/`approved`/`rejected`), `approval_datetime`.

**Dos hallazgos que condicionan el diseño:**

1. **La respuesta NO trae líneas de detalle.** Sólo cabecera. Para armar líneas de producto hay que bajar el XML, sin excepción.
2. **`xml_gcs_path` es un URI `gs://`, no una URL HTTP.** Odoo **no puede** hacer `GET` sobre `gs://` sin credenciales de GCS. Es un identificador interno de Fixcal, no un link descargable. La descarga se hace por el endpoint del punto 2.5.

### 2.4 `GET /fe/recepcion/api/invoices` — listado por proveedor

Igual que el anterior pero con header `provider-rnc` (requerido). Útil para el botón "Traer facturas de este proveedor" en la ficha del partner.

### 2.5 `GET /{encf}/xml?issuer_rnc=<RNC_PROVEEDOR>` — descarga del XML ✅

Verificado: `GET /E310000000034/xml?issuer_rnc=131880681` → `200`, `application/xml`, 6.606 bytes, e-CF completo con `<Signature>`.

> **Este es el punto crítico que resuelve el "cómo bajo el XML".** El endpoint está documentado bajo el tag *Emission*, pero funciona igual para comprobantes recibidos siempre que se pase `issuer_rnc` = RNC del **proveedor** (el emisor), no el nuestro. Conviene confirmarlo por escrito con el equipo del API para que no lo rompan en un refactor.

### 2.6 `GET /arecf/{encf}?issuer_rnc=<RNC_PROVEEDOR>` — acuse de recibo

Devuelve el ARECF firmado que Fixcal le respondió al proveedor:

```xml
<ARECF><DetalleAcusedeRecibo><Version>1.0</Version>
  <RNCEmisor>131880681</RNCEmisor><RNCComprador>131566332</RNCComprador>
  <eNCF>E310000000034</eNCF><Estado>0</Estado>
  <FechaHoraAcuseRecibo>21-07-2026 17:15:45</FechaHoraAcuseRecibo>
</DetalleAcusedeRecibo><Signature .../></ARECF>
```

`Estado`: `0` = recibido, `1` = no recibido (con `CodigoMotivo` 1-4). Se adjunta al documento como evidencia de auditoría.

### 2.7 `POST /acecf/?submit_to_dgii=true` — aprobación comercial

Body `ACECFApprovalRequest`:

| Campo | Req | Nota |
|---|---|---|
| `issuer_rnc` | ✅ | RNC del proveedor |
| `receiver_rnc` | ✅ | Nuestro RNC (`company_id.vat`) |
| `encf` | ✅ | e-NCF del comprobante |
| `dgii_environment` | ✅ | `TesteCF` / `CerteCF` / `eCF` |
| `approval_status` | ✅ | `1` = aprobado comercialmente · `2` = no aprobado |
| `approval_datetime` | ✅ | ISO-8601 |
| `invoice_date_issued` | ✅ | `FechaEmision` |
| `invoice_total_amount` | ✅ | `MontoTotal` |
| `rejection_code` | sólo si `2` | `1` bienes/servicios no recibidos · `2` defectuosos · `3` otro |
| `rejection_description` | opt | texto libre, ≤255 |
| `ecf_document_id` | opt | si se omite, Fixcal crea el documento metadata-only |
| `version` | opt | default `"1.0"` |

`xml_gcs_path` y `xml_checksum` los genera el servicio — **no enviarlos**.

Respuesta `201` con: `id`, `sent_to_dgii`, `sent_to_dgii_at`, `dgii_submission_status` (`submitted`/`failed`/`null`), `dgii_response`, `sent_to_issuer`, `issuer_delivery_status`, `issuer_delivery_error`, `xml_gcs_path`, `xml_checksum`.

Con `submit_to_dgii=false` se crea el registro local sin enviar — útil para pruebas y para un modo "aprobar en lote y enviar después".

**Consulta:** `GET /acecf/?receiver_rnc=<nuestro RNC>&limit=&offset=` (limit máx 100) para reconciliar estado.

### 2.8 Endpoints de soporte

| Endpoint | Uso en este módulo |
|---|---|
| `GET /directory/taxpayers/{rnc}` | Validar RNC del proveedor contra el Directorio de Facturadores DGII antes de crear el `res.partner` |
| `GET /monitoring/status` | Mostrar estado de servicios DGII en el dashboard; degradar el cron con gracia si DGII está caído |
| `GET /errors` | Catálogo de errores estructurados; usarlo para traducir mensajes al operario |
| `GET /acecf/{approval_id}/xml` | Descargar el ACECF firmado para adjuntarlo al documento |

### 2.9 Limitaciones del API detectadas

| # | Limitación | Impacto | Mitigación propuesta |
|---|---|---|---|
| L1 | `/invoices/all` **no tiene paginación** (`limit`/`offset`) | Un cliente con 5.000 facturas/mes recibe todo en un solo payload | Ventanas de fecha cortas (1 día en el cron). Escalar a rangos por hora si hace falta. Pedir paginación al equipo del API |
| L2 | `ReceivedInvoice` **no expone `buyer_rnc`** por factura | En multicompañía no se sabe a cuál compañía pertenece cada factura sin filtrar | Una llamada por compañía usando el header `buyer-rnc` |
| L3 | Sin líneas de detalle en la respuesta JSON | 1 request HTTP extra por factura | Descarga del XML diferida (sólo al abrir/procesar el documento), no dentro del cron |
| L4 | `xml_gcs_path` no es descargable directamente | — | Usar `GET /{encf}/xml` (§2.5) |
| L5 | Sin webhook / push de facturas nuevas | Latencia = periodo del cron | Cron diario 12:00 AM (acordado) + botón "Sincronizar ahora" |
| L6 | Fechas en `DD-MM-YYYY` en headers, ISO-8601 en el body | Fuente clásica de bugs off-by-one | Helper único de formateo + tests |

---

## 3. Arquitectura

### 3.1 Ubicación en el stack existente

```
l10n_do_accounting            (NCF, tipos de documento, índices únicos)
        │
l10n_do_ecf_invoicing         (ECFConfig, ECFService, res.company: env/versión/certificado)
        │                      ← SE REUTILIZA la capa de configuración y HTTP
        ├── l10n_do_ecf_reception            (recepción XML de terceros — NO se toca)
        ├── l10n_do_ecf_status_check         (consulta de estado — NO se toca)
        └── l10n_do_ecf_purchase_reception   ◀── NUEVO
                    depends: l10n_do_ecf_invoicing, purchase, stock, l10n_do_purchase
```

**Reutilización concreta:**

- `res.company.l10n_do_ecf_service_env` (`TesteCF`/`CerteCF`/`eCF`) y `l10n_do_ecf_api_version` (`v1`/`v3`) ya existen. La recepción **sólo existe en v3 (Fixcal)**; si la compañía está en `v1` el módulo se auto-deshabilita con un mensaje claro.
- `ECFConfig` (`lib/ecf_config.py`) centraliza URLs y API keys fuera de la base de datos. Se extiende con las operaciones de recepción — **no se crea un segundo cliente HTTP paralelo**.
- El patrón `ECFResult` (dataclass `success`/`data`/`error`/`status_code`) se mantiene.

### 3.2 Extensión de `ECFConfig`

```python
# l10n_do_ecf_invoicing/lib/ecf_config.py  → añadir a _ENDPOINTS[V3][*]
"reception_list_all":  "https://test.fixcal.do/fe/recepcion/api/invoices/all",
"reception_list":      "https://test.fixcal.do/fe/recepcion/api/invoices",
"reception_count":     "https://test.fixcal.do/fe/recepcion/api/invoices/count",
"reception_xml":       "https://test.fixcal.do/%s/xml",
"reception_arecf":     "https://test.fixcal.do/arecf/%s",
"acecf_create":        "https://test.fixcal.do/acecf/",
"acecf_list":          "https://test.fixcal.do/acecf/",
"taxpayer_directory":  "https://test.fixcal.do/directory/taxpayers/%s",
```

Nuevo servicio `lib/ecf_reception_service.py` (o métodos nuevos en `ECFService`; se decide en revisión de código):

```python
class ECFReceptionService:
    def list_received(self, start_date, end_date, buyer_rnc=None) -> ECFResult
    def count_received(self, start_date, end_date, buyer_rnc=None) -> ECFResult
    def get_invoice_xml(self, encf, issuer_rnc) -> ECFResult   # texto XML
    def get_arecf(self, encf, issuer_rnc) -> ECFResult
    def submit_acecf(self, payload, submit_to_dgii=True) -> ECFResult
    def list_acecf(self, receiver_rnc, limit=100, offset=0) -> ECFResult
```

Headers de recepción: sólo `x-api-key` + `env` (sin `x-token`).

---

## 4. Modelo de datos

### 4.1 `l10n_do.ecf.received.document` — documento recibido

| Campo | Tipo | Notas |
|---|---|---|
| `name` | Char | = `encf`, `_rec_name` |
| `company_id` | M2o `res.company` | requerido, indexado |
| `encf` | Char(13) | indexado |
| `ecf_type` | Selection | `31`,`32`,`33`,`34`,`41`,`43`,`44`,`45`,`46`,`47` |
| `partner_id` | M2o `res.partner` | proveedor resuelto por RNC |
| `provider_rnc` | Char(11) | del API |
| `provider_name` | Char | del API (razón social tal como la envió el proveedor) |
| `date_issued` | Date | `FechaEmision` |
| `date_received` | Datetime | `date_received` del API |
| `amount_total_api` | Monetary | `total_amount` del API — **referencia inmutable** |
| `amount_total_xml` | Monetary | `Totales/MontoTotal` calculado del XML |
| `amount_untaxed`, `amount_tax`, `amount_exempt` | Monetary | del XML |
| `currency_id` | M2o | `OtraMoneda/TipoMoneda` o DOP |
| `exchange_rate` | Float(6) | `OtraMoneda/TipoCambio` |
| `xml_gcs_path` | Char | referencia informativa de Fixcal |
| `xml_attachment_id` | M2o `ir.attachment` | XML descargado (adjunto Odoo) |
| `arecf_attachment_id` | M2o `ir.attachment` | acuse de recibo |
| `state` | Selection | `draft`→`fetched`→`to_map`→`ready`→`processed` / `rejected` / `error` |
| `approval_state` | Selection | `pending`/`approved`/`rejected` (espejo del API + local) |
| `approval_date` | Datetime | |
| `rejection_code` | Selection | `1`/`2`/`3` |
| `rejection_reason` | Char(255) | |
| `acecf_id_api` | Integer | `id` devuelto por `POST /acecf/` |
| `purchase_order_id` | M2o `purchase.order` | resultado |
| `move_id` | M2o `account.move` | resultado |
| `picking_ids` | O2m/M2m `stock.picking` | resultado |
| `line_ids` | O2m | líneas |
| `error_message` | Text | último error del API/parseo |
| `sync_batch_id` | M2o `l10n_do.ecf.reception.batch` | trazabilidad del cron |

**Restricción SQL:** `UNIQUE(company_id, encf, provider_rnc)` — impide que dos corridas del cron creen dos documentos del mismo comprobante (requisito explícito de la sesión).

**Máquina de estados:**

```
 draft ──fetch XML──▶ fetched ──parse──▶ to_map ──mapeo 100%──▶ ready ──acción──▶ processed
   │                                        │                      │
   └────────────── error ◀──────────────────┘                      └──▶ rejected (ACECF=2)
```

### 4.2 `l10n_do.ecf.received.document.line` — línea

| Campo | Tipo | Origen XML |
|---|---|---|
| `document_id` | M2o | |
| `sequence` | Integer | `NumeroLinea` |
| `xml_item_name` | Char | `NombreItem` ← **clave de mapeo** |
| `xml_item_description` | Char | `DescripcionItem` |
| `xml_item_code` | Char | código extraído de `DescripcionItem` (heurística) |
| `xml_goods_indicator` | Selection | `IndicadorBienoServicio`: `1` bien / `2` servicio |
| `xml_billing_indicator` | Selection | `IndicadorFacturacion`: `1`/`2`/`3`/`4` |
| `xml_uom` | Char | `UnidadMedida` (código DGII) |
| `quantity` | Float | `CantidadItem` |
| `price_unit` | Float(4) | `PrecioUnitarioItem` |
| `discount_amount` | Monetary | `DescuentoMonto` |
| `amount_line` | Monetary | `MontoItem` |
| `product_id` | M2o `product.product` | **resultado del mapeo** |
| `product_uom_id` | M2o `uom.uom` | |
| `tax_ids` | M2m `account.tax` | resultado del mapeo de impuestos |
| `account_id` | M2o `account.account` | cuenta de gasto sugerida |
| `map_state` | Selection | `unmapped` / `auto` / `manual` / `new_product` |
| `map_confidence` | Float | 0–1, similitud del match automático |

### 4.3 `l10n_do.ecf.reception.batch` — lote de sincronización

`company_id`, `date_from`, `date_to`, `env`, `count_api` (del endpoint `/count`), `count_created`, `count_skipped_duplicate`, `count_error`, `state`, `log`.

Sirve para responder la pregunta operativa "¿el cron de anoche trajo todo?" sin leer logs del servidor.

### 4.4 `l10n_do.ecf.product.map` — memoria de mapeo (complemento)

`product.supplierinfo` es la fuente de verdad del aprendizaje (§5), pero necesitamos un índice normalizado para búsqueda rápida y para casos que `supplierinfo` no cubre (líneas de servicio sin producto, cuentas de gasto directas):

| Campo | Tipo |
|---|---|
| `company_id` | M2o |
| `partner_id` | M2o `res.partner` (proveedor) |
| `xml_key` | Char, indexado — nombre normalizado (§5.2) |
| `xml_item_name_raw` | Char — última grafía vista |
| `product_id` | M2o `product.product` |
| `account_id` | M2o `account.account` (opcional) |
| `tax_ids` | M2m `account.tax` (opcional, override) |
| `hit_count` | Integer — cuántas veces se ha usado |
| `last_used` | Datetime |

`UNIQUE(company_id, partner_id, xml_key)`.

---

## 5. Mapeo de líneas de producto — el corazón del módulo

Este es el problema que hace difícil el módulo: **el XML no trae un ID de producto, trae texto libre**. `NombreItem` es como el proveedor llama a la cosa, no como la llamamos nosotros.

### 5.1 Estrategia en cascada

Para cada línea, en orden, deteniéndose en el primer acierto:

| # | Regla | Fuente | `map_state` | Confianza |
|---|---|---|---|---|
| 1 | **Memoria de mapeo**: `xml_key` exacto para ese proveedor | `l10n_do.ecf.product.map` | `auto` | 1.00 |
| 2 | **Vendor Product Code**: `xml_item_code` = `supplierinfo.product_code` del proveedor | `product.supplierinfo` | `auto` | 0.95 |
| 3 | **Vendor Product Name**: `xml_key` = normalización de `supplierinfo.product_name` | `product.supplierinfo` | `auto` | 0.90 |
| 4 | **Código interno propio**: `xml_item_code` = `product.default_code` | `product.product` | `auto` | 0.80 |
| 5 | **Código de barras**: `xml_item_code` = `product.barcode` | `product.product` | `auto` | 0.85 |
| 6 | **Similitud trigram** ≥ umbral (default 0.75) sobre productos ya comprados a ese proveedor | `pg_trgm` | `unmapped` + sugerencia | 0.50–0.89 |
| 7 | Sin match | — | `unmapped` | 0.00 |

Las reglas 1–5 son **determinísticas y gratis**. La 6 es una sugerencia que el operario confirma; se calcula en PostgreSQL, sin llamadas externas, sin costo por token.

> **Sobre IA:** se evaluó usar un LLM/MCP para el mapeo (propuesta de Emmanuel) y se **descartó**. Razones: (a) costo lineal por línea, insostenible con facturas de cientos de líneas; (b) resultado no determinista, inauditable ante DGII; (c) el operario igual tiene que revisar, así que el LLM no elimina el paso humano — sólo agrega costo. La cascada determinística converge a ~100% automático después de las primeras facturas de cada proveedor, que es exactamente el comportamiento que el usuario percibe como "el sistema aprendió".

### 5.2 Normalización (`xml_key`)

Un solo helper, usado tanto al guardar como al buscar, si no el índice no sirve:

```python
def _normalize_item_key(name: str) -> str:
    """'  INTERNET  Fibra-Óptica 100MB  ' → 'internet fibra optica 100mb'"""
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode()
    s = s.lower()
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()
```

Nota: `l10n_do_ecf_invoicing` ya tiene `l10n_do.dgii.ecf.tools.remove_special_character` para el camino de emisión. Aquí hace falta una normalización **más agresiva** (case-folding y colapso de separadores) porque el objetivo es *matching*, no *cumplimiento de formato DGII*. Se implementa aparte y se documenta el porqué.

### 5.3 Extracción del código de producto

El e-CF **no tiene campo estándar para el código del artículo del emisor**. En la práctica los emisores lo meten en `DescripcionItem` con formatos variados. Ya hay precedente en el repo: `l10n_do_ecf_reception._get_l10n_do_line_taxes_ids_from_xml` parsea `<DescripcionItem>E-COM08 {'ISR': 5, 'INI': 18}</DescripcionItem>`.

Heurística por patrones, configurable por proveedor (campo en `res.partner`), con orden de prueba:

1. `[CODIGO] Descripción` → captura entre corchetes
2. `CODIGO - Descripción` / `CODIGO – Descripción`
3. `CODIGO Descripción` donde `CODIGO` matchea `^[A-Z0-9][A-Z0-9._/-]{2,19}\s`
4. Sin patrón → `xml_item_code = False`, se cae a las reglas por nombre

La extracción **nunca falla el proceso**; si no encuentra código, sigue la cascada.

### 5.4 Aprendizaje

Cuando el operario mapea manualmente la línea (o crea un producto nuevo desde el wizard), al guardar:

1. **Se escribe/actualiza `product.supplierinfo`** con `partner_id` = proveedor, `product_name` = `NombreItem` original, `product_code` = `xml_item_code` (si existe). Esto es nativo de Odoo: la próxima orden de compra a ese proveedor ya muestra el nombre del proveedor en la línea, sin que este módulo intervenga. **Ese es el campo del template del producto que se discutió en la sesión.**
2. **Se escribe/actualiza `l10n_do.ecf.product.map`** con `xml_key` normalizado, `hit_count += 1`, `last_used = now`.

La segunda factura de ese proveedor con ese ítem se mapea sola por la regla 1.

### 5.5 Wizard de mapeo

`l10n_do.ecf.received.map.wizard` — lista editable, una fila por línea sin mapear:

```
┌────────────────────────────────────────────────────────────────────────────────┐
│ Mapear líneas — E310000000034 — CLARO DOMINICANA (RNC 101020304)               │
├──────────────────────────┬──────┬─────────┬───────────────────────┬────────────┤
│ Ítem del proveedor       │ Cant │  Monto  │ Producto Odoo         │ Acción     │
├──────────────────────────┼──────┼─────────┼───────────────────────┼────────────┤
│ INTERNET FIBRA OPTICA    │  1.0 │ 4,500.00│ [Internet 100MB    ▾] │ ● Mapear   │
│ CARGO POR INSTALACION    │  1.0 │ 1,200.00│ [                  ▾] │ ○ Crear    │
│ EQUIPO ROUTER TP-LINK    │  2.0 │ 3,000.00│ [Router TP-Link    ▾] │ ● Mapear   │
├──────────────────────────┴──────┴─────────┴───────────────────────┴────────────┤
│ ☑ Recordar estos mapeos para este proveedor                                    │
│                                    [ Cancelar ]  [ Aplicar y continuar ]        │
└────────────────────────────────────────────────────────────────────────────────┘
```

- Sugerencias de la regla 6 pre-cargadas en el `Many2one` con `map_confidence` visible.
- "Crear" abre el formulario de producto con `name`, `type` (de `IndicadorBienoServicio`), `standard_price` (de `PrecioUnitarioItem`) y `seller_ids` precargados.
- El checkbox de recordar está marcado por defecto.

### 5.6 Línea genérica de contingencia

Para líneas que no son productos (cargos administrativos, redondeos, ajustes), el módulo permite mapear a una **cuenta contable** en vez de a un producto (`account_id` en la línea). La factura se crea con línea de tipo `product` sin `product_id`, sólo `name` + `account_id` + impuestos. Esto evita ensuciar el catálogo de productos con basura de una sola vez.

---

## 6. Mapeo de campos XML → Odoo

### 6.1 Estructura real del e-CF v1.0

Verificada contra el XML descargado de `E310000000034` (tipo 31):

```
/ECF/Encabezado/Version
/ECF/Encabezado/IdDoc/{TipoeCF, eNCF, FechaVencimientoSecuencia, TipoIngresos, TipoPago,
                       IndicadorMontoGravado, FechaLimitePago, TerminoPago, TablaFormasPago}
/ECF/Encabezado/Emisor/{RNCEmisor, RazonSocialEmisor, NombreComercial, Sucursal, DireccionEmisor,
                        Municipio, Provincia, TablaTelefonoEmisor/TelefonoEmisor, CorreoEmisor,
                        WebSite, ActividadEconomica, CodigoVendedor, NumeroFacturaInterna,
                        NumeroPedidoInterno, ZonaVenta, FechaEmision}
/ECF/Encabezado/Comprador/{RNCComprador, RazonSocialComprador, ContactoComprador, CorreoComprador,
                           DireccionComprador, MunicipioComprador, ProvinciaComprador,
                           FechaEntrega, FechaOrdenCompra, NumeroOrdenCompra, CodigoInternoComprador}
/ECF/Encabezado/Totales/{MontoGravadoTotal, MontoGravadoI1, MontoGravadoI2, MontoGravadoI3,
                         MontoExento, ITBIS1, ITBIS2, ITBIS3, TotalITBIS, TotalITBIS1..3,
                         MontoImpuestoAdicional, MontoTotal, TotalITBISRetenido, TotalISRRetencion}
/ECF/Encabezado/OtraMoneda/{TipoMoneda, TipoCambio, MontoGravadoTotalOtraMoneda, ...,
                            MontoTotalOtraMoneda}
/ECF/DetallesItems/Item/{NumeroLinea, IndicadorFacturacion, Retencion, NombreItem,
                         IndicadorBienoServicio, DescripcionItem, CantidadItem, UnidadMedida,
                         PrecioUnitarioItem, DescuentoMonto, TablaSubDescuento,
                         TablaImpuestoAdicional, OtraMonedaDetalle, MontoItem}
/ECF/InformacionReferencia/{NCFModificado, RNCOtroContribuyente, FechaNCFModificado, CodigoModificacion}
/ECF/FechaHoraFirma
/ECF/Signature/SignatureValue          ← los primeros 6 caracteres = código de seguridad
```

### 6.2 Cabecera

| XML | Campo Odoo | Notas |
|---|---|---|
| `IdDoc/eNCF` | `encf` → `move.l10n_do_fiscal_number` | |
| `IdDoc/TipoeCF` | `ecf_type` → `move.l10n_latam_document_type_id` | Buscar por `doc_code_prefix` = `E31`… |
| `IdDoc/FechaVencimientoSecuencia` | `move.l10n_do_ncf_expiration_date` | formato `DD-MM-YYYY` |
| `Emisor/RNCEmisor` | `partner_id.vat` | resolución §6.5 |
| `Emisor/RazonSocialEmisor` | `provider_name` / `partner_id.name` si se crea | |
| `Emisor/FechaEmision` | `date_issued` → `move.invoice_date` | `DD-MM-YYYY` |
| `Emisor/Municipio`, `Provincia` | `partner_id.state_id` | reusar `_get_l10n_do_state_ref()` de `l10n_do_ecf_reception` |
| `Emisor/Sucursal` | informativo (fase 2) | |
| `Comprador/RNCComprador` | **validación**: debe ser `company_id.vat` | si no coincide → estado `error` |
| `Comprador/NumeroOrdenCompra` | `purchase_order_ref` | si existe una PO nuestra con ese número → enlazar |
| `Totales/MontoTotal` | `amount_total_xml` | se contrasta con `amount_total_api` |
| `OtraMoneda/TipoMoneda` | `currency_id` | |
| `OtraMoneda/TipoCambio` | `exchange_rate` | §6.4 |
| `Signature/SignatureValue[:6]` | `move.l10n_do_ecf_security_code` | ya hay helper `_get_security_code_from_xml` |
| `FechaHoraFirma` | `move.l10n_do_ecf_sign_date` | |
| `InformacionReferencia/NCFModificado` | `move.l10n_do_origin_ncf` | para NC (34) / ND (33) |
| `InformacionReferencia/CodigoModificacion` | `move.l10n_do_ecf_modification_code` | |

### 6.3 Impuestos

`IndicadorFacturacion` por línea (semántica confirmada en `l10n_do_ecf_invoicing/models/account_move_line.py::_get_invoicing_indicator`):

| Valor | Significado | Impuesto de compra (`account.{company_id}_<xmlid>`) |
|---|---|---|
| `1` | Gravado ITBIS 18% | `tax_18_purch` |
| `2` | Gravado ITBIS 16% | `tax_16_purch` |
| `3` | Gravado ITBIS 0% | `tax_0_purch` |
| `4` | Exento | `tax_0_purch` (o sin impuesto, configurable) |

Casos adicionales:

- **`TablaImpuestoAdicional`** (ISC, CDT, propina): mapear por `TipoImpuesto` a `tax_10_telco`, `tax_2_telco`, `tax_tip_purch`, etc. Configurable por compañía porque no todos los clientes tienen el mismo plan.
- **Precios con impuesto incluido**: si `MontoItem` ya incluye ITBIS, usar la variante `_incl` (`tax_18_purch_incl`). Se detecta comparando `Σ MontoItem` contra `MontoTotal - TotalITBIS`.
- **Retenciones** (`Retencion/MontoITBISRetenido`, `MontoISRRetenido`, tipos 41/47): mapear a los `ret_*` del plan (`ret_100_tax_security`, `ret_30_tax_moral`, `ret_10_isr_person`…). Se implementa **en fase 4**; en fase 1 se marca el documento con warning si trae retenciones.

**Validación de cuadre obligatoria** antes de pasar a `ready`:

```
| Σ (MontoItem de líneas) + Σ impuestos calculados  −  Totales/MontoTotal |  ≤  tolerancia
```
Tolerancia por defecto: `0.05` DOP (configurable). Si no cuadra → estado `error` con detalle del descuadre, nunca se crea el asiento. Esto es lo que evita que un mapeo de impuestos incorrecto contamine la contabilidad.

### 6.4 Moneda y tasa de cambio

| Versión Odoo | Mecanismo |
|---|---|
| **17.0** | Campo `rate` de `account_invoice_rate` (módulo propio del repo, `account_invoice_rate/models/account.py`) y `rate` de `purchase_order_rate`. Ya existe y está en producción |
| **19.0** | Odoo nativo permite fijar la tasa del comprobante en la factura → usar el campo nativo |
| **15.0** | Verificar si `account_invoice_rate` está portado a 15.0; si no, es parte del alcance del backport |

Regla: la tasa **se toma del XML** (`OtraMoneda/TipoCambio`), no de la tabla de tasas del día. El comprobante fiscal manda. Si `TipoCambio` viene vacío en una factura en moneda extranjera → `error`, no se adivina.

Ojo con la convención: `l10n_do_ecf_invoicing` escribe `TipoCambio = 1/rate_odoo` (ver `_get_OtraMoneda_data`, línea `result["TipoCambio"] = f"{1 / exchange_rate:.4f}"`). Al leer hay que **invertir de vuelta**. Es exactamente el tipo de bug que ya nos costó un incidente en Landed Costs; va con test dedicado.

### 6.5 Resolución del proveedor (`res.partner`)

1. Buscar por `vat` = `RNCEmisor` en la compañía (y sus hijas).
2. Si no existe y el auto-alta está habilitado: consultar `GET /directory/taxpayers/{rnc}` para validar contra el Directorio DGII, y crear el partner con `name` = `RazonSocialEmisor`, `vat`, dirección, municipio/provincia, correo, `supplier_rank = 1`, `l10n_do_dgii_tax_payer_type` según `TipoeCF`.
3. Si el auto-alta está deshabilitado: documento en estado `error` con acción "Crear proveedor" a un clic.

El auto-alta es un booleano en `res.company` — hay clientes que no quieren que un cron les cree partners.

---

## 7. Flujos operativos

### 7.1 Cron de sincronización

```python
# ir.cron: "e-CF: Descargar facturas de proveedores"
# Diario, 00:00 (acordado en sesión), numbercall = -1, doall = False
model._cron_fetch_received_ecf()
```

Algoritmo:

```
para cada compañía con l10n_do_ecf_purchase_reception_enabled = True:
    si company.l10n_do_ecf_api_version != 'v3':  saltar (log info)
    date_from = date_to = hoy - 1 día        (parametrizable: días hacia atrás, default 1)
    batch = crear l10n_do.ecf.reception.batch
    count_api = GET /fe/recepcion/api/invoices/count   (buyer-rnc = company.vat)
    payload   = GET /fe/recepcion/api/invoices/all     (buyer-rnc = company.vat)
    para cada invoice del payload:
        si ya existe (company, encf, provider_rnc):  count_skipped_duplicate++ ; continuar
        si ya existe account.move con ese l10n_do_fiscal_number para ese proveedor:
            crear documento en estado 'error' marcado como duplicado-en-core  (§7.5)
        crear documento en estado 'draft'   ← SIN bajar el XML todavía
        count_created++
    batch.count_api = count_api ; cerrar batch
    si count_created + count_skipped_duplicate != count_api:  log warning + actividad al responsable
```

**El cron no descarga XMLs.** Con 500 facturas serían 500 requests HTTP serializados dentro de una transacción larga. El XML se baja cuando el operario abre el documento o cuando pulsa "Procesar" (o vía un segundo cron de baja prioridad con `limit=N`, siguiendo el patrón que ya usan los crones de `l10n_do_ecf_reception`: `_autopost_reception_invoice(limit=75)`).

**Solapamiento de crones:** se toma un lock por compañía (`ir.config_parameter` con timestamp, o `SELECT ... FOR UPDATE NOWAIT` sobre el batch) para que una corrida manual no pise a la programada.

**Reintentos:** timeouts y 5xx → reintento con backoff (3 intentos). 4xx → error registrado, sin reintento.

### 7.2 Procesamiento del documento

```
[Documento en 'draft']
   │ botón "Descargar XML"  (o cron secundario)
   ▼
GET /{encf}/xml?issuer_rnc=<provider_rnc>  →  ir.attachment  →  estado 'fetched'
   │ parseo
   ▼
Validaciones: RNCComprador == company.vat · cuadre de totales · moneda/tasa
   │
   ├─ falla → 'error' + mensaje concreto
   ▼
Mapeo automático en cascada (§5.1)  →  estado 'to_map'
   │
   ├─ 100% de líneas mapeadas → 'ready' automáticamente
   └─ hay 'unmapped' → wizard de mapeo → al aplicar → 'ready'
```

### 7.3 Acciones desde `ready` (las cuatro que pidió Daniel)

| Acción | Qué hace | Resultado |
|---|---|---|
| **Crear OC** | `purchase.order` en borrador con proveedor, moneda, tasa, líneas mapeadas | `purchase_order_id` |
| **Crear OC + confirmar + recibir** | Lo anterior + `button_confirm()` + validar el `stock.picking` con las cantidades del XML | `+ picking_ids` |
| **Crear OC + recibir + facturar** | Lo anterior + `action_create_invoice()` + poblar campos fiscales del e-CF | `+ move_id` |
| **Sólo crear factura** | `account.move` tipo `in_invoice` directo, sin PO ni movimiento de stock | `move_id` |

Todas terminan en estado `processed` con enlaces navegables a los documentos generados. La acción por defecto es configurable por compañía y **override por proveedor** (`res.partner`) — hay proveedores de servicios donde nunca hay OC ni recepción.

En la factura generada se llenan además: `l10n_do_fiscal_number`, `l10n_latam_document_type_id`, `l10n_do_ncf_expiration_date`, `l10n_do_ecf_security_code`, `l10n_do_ecf_sign_date`, `is_ecf_invoice = True`, `l10n_do_expense_type` (heredado del partner vía `l10n_do_purchase`), y se adjunta el XML. Esto alimenta el **606** de `dgii_reports` sin trabajo manual — beneficio secundario grande que conviene destacar al cliente.

### 7.4 Aprobación comercial (ACECF)

Dos botones en el documento, disponibles desde `fetched` en adelante:

**Aprobar comercialmente**
```
POST /acecf/?submit_to_dgii=true
{ issuer_rnc, receiver_rnc, encf, dgii_environment, approval_status: 1,
  approval_datetime, invoice_date_issued, invoice_total_amount }
```

**Rechazar** → wizard que pide `rejection_code` (1 no recibidos / 2 defectuosos / 3 otro) y `rejection_description`, luego el mismo POST con `approval_status: 2`.

Del `201` se guardan `id` → `acecf_id_api`, `dgii_submission_status`, `dgii_response`, `issuer_delivery_status`. Si `dgii_submission_status = "failed"` se muestra el error crudo y se habilita reintento — **no se marca como aprobado localmente si DGII lo rechazó**. El estado local debe ser un espejo fiel del estado en DGII; ese fue el requisito explícito ("garantizar que el estado sea consistente en ambos sistemas").

Cron de reconciliación semanal opcional: `GET /acecf/?receiver_rnc=` y comparar contra `approval_state` local.

**Regla de negocio:** rechazar comercialmente **no** borra el documento en Odoo; lo lleva a `rejected` y bloquea la creación de OC/factura. Queda como evidencia.

### 7.5 Anti-duplicados — tres capas

| Capa | Mecanismo | Cubre |
|---|---|---|
| **1. Modelo intermedio** | `UNIQUE(company_id, encf, provider_rnc)` en `l10n_do.ecf.received.document` | Cron corrido dos veces, corrida manual sobre rango ya procesado |
| **2. Chequeo contra el core** | Antes de crear la factura: buscar `account.move` con `l10n_do_fiscal_number = encf` y `commercial_partner_id = partner` y `move_type in ('in_invoice','in_refund')` | El operario ya digitó la factura a mano antes de que llegara el cron |
| **3. Índice único de BD** | `account_move_unique_l10n_do_fiscal_number_purchase_manual` sobre `(l10n_do_fiscal_number, commercial_partner_id, company_id)`, ya existente en `l10n_do_accounting` | Red de seguridad final a nivel PostgreSQL |

Comportamiento acordado en la capa 2: **no bloquear en silencio**. Se crea el documento intermedio en estado `error` con mensaje explícito («El comprobante E31… ya existe en la factura FACT/2026/0123») y un botón "Ver factura existente" + un botón "Vincular a la factura existente" (que asocia el XML como adjunto y marca `processed` sin crear nada nuevo). El operario ve qué pasó en vez de preguntarse por qué faltan facturas.

---

## 8. Compatibilidad 15.0 / 17.0 / 19.0

| Área | 15.0 | 17.0 | 19.0 |
|---|---|---|---|
| `detailed_type` vs `type` en producto | `type` + `detailed_type` | `detailed_type` | `type` + `is_storable` |
| Tasa de cambio en factura | verificar `account_invoice_rate` | `account_invoice_rate.rate` | nativo |
| Vistas: `attrs` vs atributos directos | `attrs="{...}"` | `invisible="..."` | `invisible="..."` |
| `stock.picking` — validación | `button_validate` + wizard | idem | idem |
| Sucursales DGII | no soportado | parcial | soportado |
| API Fixcal | idéntico en las tres | idéntico | idéntico |

**Estrategia:** la lógica de negocio (conector, parseo, mapeo, cálculo de impuestos) vive en métodos sin dependencias de versión y se comparte 1:1 entre ramas. Sólo divergen: manifiesto, vistas XML, y una capa fina de compatibilidad (`_get_product_type_vals()`, `_set_invoice_rate()`). Desarrollo primero en **17.0** (rama de referencia, donde está el resto del stack e-CF), luego port a 19.0 y 15.0.

> Aprendizaje del repo: hubo casos de fixes que quedaron sólo en 19.0 sin backport a 17.0 (FOB inflado en Landed Costs). Este módulo se desarrolla en 17.0 primero y los ports se abren **en el mismo sprint**, no "después".

---

## 9. Pruebas

### 9.1 Colección Bruno (requisito de la sesión)

Versionada dentro del módulo, no en Postman:

```
l10n_do_ecf_purchase_reception/
└── bruno/
    ├── bruno.json
    ├── environments/
    │   ├── sandbox.bru          # base = https://test.fixcal.do, env = TesteCF
    │   ├── certification.bru    # base = https://test.fixcal.do, env = CerteCF
    │   └── production.bru       # base = https://api.fixcal.do,  env = eCF
    └── reception/
        ├── 01-count-received.bru
        ├── 02-list-all-received.bru
        ├── 03-list-by-provider.bru
        ├── 04-download-invoice-xml.bru
        ├── 05-download-arecf.bru
        ├── 06-acecf-approve.bru
        ├── 07-acecf-reject.bru
        ├── 08-acecf-list.bru
        └── 09-taxpayer-directory.bru
```

Ejemplo (`02-list-all-received.bru`):

```
meta { name: List all received invoices, type: http, seq: 2 }
get  { url: {{base_url}}/fe/recepcion/api/invoices/all }
headers {
  x-api-key: {{api_key}}
  env: {{env}}
  start-date: {{start_date}}
  end-date: {{end_date}}
}
assert { res.status: eq 200
         res.body.count: isNumber }
```

Las API keys **no van en el repo**: las variables `api_key` se resuelven desde el `.env` local de Bruno, igual que se hace con las credenciales de Azul.

### 9.2 Tests unitarios Odoo

| Test | Verifica |
|---|---|
| `test_parse_ecf_31` | XML tipo 31 → cabecera + N líneas, campos correctos |
| `test_parse_ecf_34_credit_note` | NC → `l10n_do_origin_ncf` y `l10n_do_ecf_modification_code` |
| `test_parse_foreign_currency` | `TipoCambio` invertido correctamente; montos en DOP y USD cuadran |
| `test_tax_mapping_indicators` | `IndicadorFacturacion` 1/2/3/4 → impuesto de compra correcto |
| `test_tax_mapping_included` | precio con ITBIS incluido → `tax_18_purch_incl` |
| `test_totals_mismatch_blocks` | descuadre > tolerancia → estado `error`, sin `account.move` |
| `test_product_map_exact` | segunda factura del mismo proveedor mapea sola (regla 1) |
| `test_product_map_supplierinfo` | match por `supplierinfo.product_code` (regla 2) |
| `test_product_map_creates_supplierinfo` | mapeo manual escribe `product.supplierinfo` |
| `test_duplicate_same_batch` | mismo `encf` dos veces en un payload → un solo documento |
| `test_duplicate_cron_rerun` | correr el cron dos veces → 0 documentos nuevos |
| `test_duplicate_manual_invoice` | factura ya digitada a mano → documento en `error`, mensaje correcto |
| `test_wrong_buyer_rnc` | `RNCComprador` ≠ `company.vat` → `error` |
| `test_create_po_confirm_receive` | flujo completo PO → picking → factura |
| `test_acecf_approve_payload` | payload ACECF exacto contra el schema |
| `test_acecf_dgii_failure` | `dgii_submission_status = failed` → estado local NO cambia a aprobado |

**Fixtures:** XMLs reales del sandbox (ya tenemos `E310000000034`, `E330000000001`, `E340000000015` disponibles), anonimizados, en `tests/fixtures/`.

> Cuidado con el patrón que nos ha mordido antes: `setUpClass` sin `@classmethod` hace que los tests **nunca corran** y `run_tests.sh` reporte PASS igual. Revisar `test_logs/modules/l10n_do_ecf_purchase_reception.log` con grep de `FAIL|ERROR` explícitamente, no confiar en el PASS.

### 9.3 Pruebas de integración

- Sandbox con las 17 facturas ya cargadas (`131566332` como comprador) — dataset listo para usar.
- Prueba de volumen: simular 500 facturas para medir tiempo del cron y decidir si hace falta paginar por horas.
- Prueba de resiliencia: API caída (timeout, 500, 401) → el cron no debe dejar batches colgados ni transacciones abiertas.

---

## 10. Plan de trabajo por fases

| Fase | Entregable | Días est. |
|---|---|---|
| **0 — Preparación** | Colección Bruno completa, credenciales de sandbox por cliente, confirmación por escrito de que `GET /{encf}/xml` es contrato estable para recibidos, dataset de XMLs de prueba | 2 |
| **1 — Conector + modelo intermedio** | `ECFReceptionService`, modelos `document`/`line`/`batch`, cron diario, vistas lista/formulario, dedup capas 1–3, parseo de cabecera, validación de cuadre | 8 |
| **2 — Mapeo de productos** | Cascada de 6 reglas, normalización, `l10n_do.ecf.product.map`, escritura de `product.supplierinfo`, wizard de mapeo, sugerencia `pg_trgm` | 6 |
| **3 — Generación de documentos** | Las 4 acciones (PO / PO+recepción / PO+recepción+factura / factura sola), mapeo de impuestos, moneda y tasa, campos fiscales e-CF en la factura | 7 |
| **4 — Aprobación comercial** | `POST /acecf/`, wizard de rechazo con códigos, ARECF adjunto, cron de reconciliación, retenciones (tipos 41/47) | 4 |
| **5 — Multiversión** | Port a 19.0 y 15.0, capa de compatibilidad, tasa de cambio nativa en 19 | 4 |
| **6 — Hardening** | Reintentos con backoff, lock de cron, logs estructurados, dashboard de lotes, actividades al responsable ante fallos, manual de usuario | 4 |
| | **Total** | **~35 días/hombre** |

Las fases 1→2→3 son secuenciales. La 4 puede ir en paralelo con la 3. La 5 arranca cuando la 3 esté estable.

**Hitos de demo:** fin de fase 1 (facturas listadas en Odoo), fin de fase 3 (factura de proveedor creada de punta a punta), fin de fase 4 (aprobación/rechazo reflejado en DGII).

---

## 11. Riesgos

| # | Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|---|
| R1 | `GET /{encf}/xml` no es contrato oficial para comprobantes recibidos y lo cambian | Media | **Alto** — sin XML no hay líneas | Confirmar por escrito en fase 0; pedir endpoint explícito `/fe/recepcion/api/ecf/{encf}/xml`; el `xml_gcs_path` queda como plan B vía credenciales GCS |
| R2 | Volumen alto sin paginación en `/invoices/all` | Media | Medio | Ventanas de 1 día; escalar a rangos por hora; pedir `limit`/`offset` al equipo del API |
| R3 | Proveedores con nomenclatura de ítems caótica (cambia entre facturas) | **Alta** | Medio | La normalización absorbe variaciones de formato; el operario mapea de nuevo cuando cambia de verdad; `hit_count` permite detectar mapeos que dejaron de usarse |
| R4 | Mapeo de impuestos incorrecto → contabilidad mal | Media | **Alto** | Validación de cuadre obligatoria antes de crear el asiento; el documento se queda en `error` en vez de generar basura |
| R5 | Auto-alta masiva de partners duplicados | Media | Medio | Validación contra Directorio DGII; auto-alta desactivable; búsqueda por `vat` normalizado |
| R6 | Convención invertida de `TipoCambio` (1/rate) | Alta | Medio | Test dedicado, helper único de conversión, revisión cruzada con `_get_OtraMoneda_data` |
| R7 | Fixcal cambia el schema del API sin aviso | Baja | Alto | Colección Bruno en CI como smoke test contra sandbox; parseo tolerante a campos nuevos |
| R8 | Facturas de proveedores extranjeros (tipo 46/47) con campos ausentes | Media | Bajo | Manejo explícito de `IdentificadorExtranjero`; ya hay precedente en `l10n_do_ecf_reception` |
| R9 | Alcance crece a "conciliación automática de pagos" | Alta | Medio | Congelar alcance de fase 1 con este documento aprobado |

---

## 12. Preguntas abiertas para Daniel

1. **¿Confirmamos `GET /{encf}/xml` con el equipo del API como camino oficial para bajar el XML de un comprobante recibido?** Es la dependencia más crítica del diseño. Si prefieren exponer un endpoint dedicado bajo `/fe/recepcion/`, mejor todavía — pero hay que saberlo antes de codificar.
2. **Multicompañía:** ¿una llamada al API por compañía usando `buyer-rnc`, o una sola llamada sin filtro y repartir en Odoo? Con `buyer-rnc` es más limpio pero son N llamadas; además `ReceivedInvoice` no trae el RNC del comprador, así que sin el filtro no podríamos repartir. Propongo N llamadas.
3. **Acción por defecto:** ¿"crear OC en borrador" para todos, o configurable por proveedor desde el día uno? Propongo configurable por compañía con override por proveedor (poco código, evita una fase 2 de retrabajo).
4. **Aprobación comercial automática:** ¿aprobar automáticamente el ACECF al confirmar la recepción de mercancía, o siempre manual? La normativa tiene plazo; un cron de "aprobar lo que lleve N días sin decisión" podría ser útil pero es una decisión de negocio, no técnica.
5. **Retenciones (tipos 41/47):** ¿entran en fase 1 o se posponen a fase 4 como propongo? Depende de si hay un cliente concreto esperándolas.
6. **Cliente piloto:** ¿cuál? Afecta qué proveedores y qué tipos de comprobante priorizar en los fixtures de prueba.
7. **Retención del XML por 10 años:** el XML vive en el bucket de Fixcal. En Odoo se guarda como `ir.attachment` (filestore). ¿Duplicamos el almacenamiento o guardamos sólo la referencia y bajamos bajo demanda? Propongo **guardarlo en Odoo**: el costo de disco es marginal frente a depender de un tercero para una obligación fiscal de 10 años, y permite reprocesar sin red.

---

## Anexo A — Endpoints Fixcal relevantes (referencia rápida)

| Método | Path | Uso |
|---|---|---|
| `GET` | `/fe/recepcion/api/invoices/all` | Listado de recibidas (cron) |
| `GET` | `/fe/recepcion/api/invoices` | Listado por proveedor |
| `GET` | `/fe/recepcion/api/invoices/count` | Conteo / control de completitud |
| `GET` | `/{encf}/xml?issuer_rnc=` | XML completo del comprobante |
| `GET` | `/arecf/{encf}?issuer_rnc=` | Acuse de recibo firmado |
| `POST` | `/acecf/?submit_to_dgii=` | Aprobación/rechazo comercial |
| `GET` | `/acecf/?receiver_rnc=` | Listado de aprobaciones emitidas |
| `GET` | `/acecf/{approval_id}/xml` | ACECF firmado |
| `GET` | `/directory/taxpayers/{rnc}` | Validación de RNC contra DGII |
| `GET` | `/monitoring/status` | Estado de servicios DGII |
| `GET` | `/errors` | Catálogo de errores |

Documentación pública: <https://test.portal.fixcal.do/developers/es> · OpenAPI: `GET /openapi.json` con header `x-api-key`.

## Anexo B — Módulos del repo que se reutilizan

| Módulo | Qué se aprovecha |
|---|---|
| `l10n_do_ecf_invoicing` | `lib/ecf_config.py` (URLs, API keys), `lib/ecf_service.py` (patrón HTTP + `ECFResult`), `res.company` (env, versión, certificado), `const.py` (`ECFEnvironment`, `ECFVersion`) |
| `l10n_do_accounting` | `l10n_do_fiscal_number`, `l10n_latam_document_type_id`, `l10n_do_expense_type`, `l10n_do_ncf_expiration_date`, índices únicos de comprobantes de compra |
| `l10n_do_ecf_reception` | Patrones de parseo: `_get_security_code_from_xml`, `_get_l10n_do_state_ref` (códigos de provincia DGII), resolución de país, mapeo de `l10n_do_dgii_tax_payer_type` |
| `l10n_do_purchase` | Tipos de gasto en órdenes de compra |
| `account_invoice_rate` / `purchase_order_rate` | Campo `rate` para la tasa del comprobante en 17.0 |
| `dgii_reports` | Consumidor final: las facturas generadas alimentan el 606 automáticamente |
