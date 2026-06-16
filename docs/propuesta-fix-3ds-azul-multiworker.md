# Propuesta: flujo 3DS stateless en `payment_azul_webservices` (fix multi-worker)

**Fecha:** 2026-06-11
**Estado:** Aprobada e implementada (2026-06-11) — validada: 12/12 challenges cross-worker OK con harness, y flujo real completo contra Azul test (method en worker A, challenge en worker B, iniciación en un tercer proceso ya muerto) → APROBADA/done
**Severidad:** Crítica (pagos 3DS fallan intermitentemente en producción)
**Evidencia de causa raíz:** `~/repos/azul-3ds-repro` (bug reproducido con 4 workers: 8/8 challenges fallidos; control con 1 worker: 24/24 aprobados)

---

## 1. Resumen ejecutivo

Los pagos con 3D Secure fallan solo en producción (odoo.sh, N workers HTTP) y nunca en
staging/test (1 worker). La causa raíz está confirmada empíricamente: el módulo delega la
continuidad del flujo 3DS al `session_store` de `pyazul`, que es **un diccionario Python en
memoria del proceso**. En modo prefork multi-worker, los callbacks del banco (method
notification y challenge/CRes) caen en workers distintos al que inició el pago, donde la
sesión no existe, y pyazul lanza `No session data found for session_id` /
`SESSION_NOT_FOUND`.

**La solución propuesta elimina por completo la dependencia del `session_store` de pyazul
después de la iniciación del pago.** Todo el estado intermedio del flujo 3DS se persiste en
`payment.transaction` (base de datos), y los callbacks reconstruyen las llamadas a los
endpoints de Azul (`ProcessThreeDSMethod`, `ProcessThreeDSChallenge`) directamente desde la
DB, sin importar qué worker los atienda. Este es exactamente el patrón que usan los
providers oficiales del core de Odoo (Adyen, Stripe): **la base de datos es la única fuente
de verdad; ningún request asume afinidad de proceso.**

El propio README de pyazul lo exige: *"For production, your application MUST implement its
own persistent session management (e.g., Redis, database)"*. El módulo hoy no lo hace.

---

## 2. Causa raíz y anatomía del fallo

### 2.1 Flujo 3DS actual (el que muere)

```
Browser                    Odoo (N workers)                         Azul / ACS
  │                              │
  │ POST /payment/azul_webservices/process
  │ ───────────────────────────▶ Worker A
  │                              │ pyazul.secure_sale()
  │                              │   → genera secure_id (UUID)
  │                              │   → session_store[secure_id] = {azul_order_id,
  │                              │       amount, itbis, order_number, ...}   ← SOLO EN RAM DE A
  │                              │ tx.provider_reference = secure_id
  │                              │ tx.azul_3ds_session_data = <html form>
  │ ◀── method form / challenge ─┘
  │
  │ (iframe ACS) POST /3ds_return?secure_id=...&threeDSMethodData=...
  │ ───────────────────────────▶ Worker B
  │                              │ tx._process_3ds_method_notification()
  │                              │   → pyazul.process_3ds_method(azul_order_id)
  │                              │   → busca azul_order_id en session_store de B
  │                              │   → ✗ SESSION_NOT_FOUND  (sesión vive en A)
  │
  │ (ACS) POST /3ds_return?secure_id=...&CRes=...
  │ ───────────────────────────▶ Worker C
  │                              │ pyazul.process_challenge(secure_id)
  │                              │   → session_store de C no tiene secure_id
  │                              │   → ✗ AzulError "No session data found for session_id"
  │                              │ tx._set_error(...)
```

Con 4 workers, P(los 3 pasos caigan en el mismo proceso) ≈ 6%. En staging odoo.sh hay 1
worker (restricción del FAQ de odoo.sh) → irreproducible ahí por diseño.

Nota adicional: incluso con 1 worker el estado en RAM no sobrevive el **reciclaje de
workers** (`limit_request`, `limit_time_*`, deploys), así que la afinidad de sesión nunca
sería una solución, solo reduciría la frecuencia.

### 2.2 Puntos exactos de dependencia de estado en memoria

| # | Punto | Ubicación | Problema |
|---|-------|-----------|----------|
| 1 | `process_challenge(session_id=provider_reference)` | `controllers/main.py:175-183` | pyazul resuelve `AzulOrderId` desde `session_store[secure_id]` → falla en otro worker |
| 2 | `process_3ds_method(azul_order_id=...)` | `models/payment_transaction.py:1313-1321` | pyazul busca `Amount/Itbis/OrderNumber` en `session_store` por `azul_order_id` → `SESSION_NOT_FOUND` en otro worker |
| 3 | `get_session_info(secure_id)` (fallback para AzulOrderId) | `models/payment_transaction.py:400-403` | Funciona hoy solo porque corre en el mismo request que la iniciación; frágil |
| 4 | Dedup de method notifications (`processed_methods`) | `pyazul/services/secure.py:319-326` | Dict por proceso: duplicados que caen en otro worker no se dedupean |
| 5 | `_client_cache` a nivel de módulo | `utils.py:15,93-96` | Comentado como *"required for 3DS session continuity"* — esa premisa es falsa en multi-worker y es la raíz conceptual del diseño actual |

### 2.3 Bugs colaterales detectados durante el análisis (mismo origen)

- **Challenge post-method sin correlación:** cuando el method notification deriva en
  challenge, el formulario se construye con `term_url` **sin** `secure_id`
  (`models/payment_transaction.py:1417-1418`). El CRes de ese challenge llega a
  `/3ds_return` solo con `CRes` en el body → `reference = None` → el controller loguea
  *"No transaction reference found"* y redirige sin procesar. Es decir: aun cayendo en el
  worker correcto, el challenge derivado del method 2.0 no se puede correlacionar.
- **Cron de rescate excluye justo a las víctimas:** `_azul_cron_verify_pending_transactions`
  (`models/payment_transaction.py:1226-1239`) excluye transacciones con
  `azul_3ds_session_data` set o `provider_reference` con pinta de UUID — exactamente las
  transacciones 3DS atascadas por este bug. Hoy quedan en `pending` para siempre.
- **`provider_reference` contiene el `secure_id`** (UUID interno de pyazul, sin significado
  para Azul) en vez del `AzulOrderId`. Rompe la convención del core (donde
  `provider_reference` es la referencia del PSP) y obliga al hack del dominio del cron.
- **Caché de cliente sin invalidación:** `_client_cache` con clave `provider_{id}` nunca se
  invalida; cambiar credenciales/certificados en el provider no surte efecto hasta
  reiniciar workers.

---

## 3. El patrón del core de Odoo (qué hace un provider "Odoo way")

Análisis de `odoo/addons/payment` y providers de referencia (Adyen es el caso 3DS más
parecido):

1. **Cero estado en proceso.** Todo el estado intermedio vive en `payment.transaction`.
   Adyen maneja 3DS2 (redirect + additional details) sin un solo dict de módulo: el
   `returnUrl` lleva `merchantReference` y el controller re-busca la transacción en DB en
   cada paso (`payment_adyen/controllers/main.py`, rutas `/payments/details` y `/return`).
2. **Pipeline estándar de notificaciones.** Los callbacks entran por
   `_handle_notification_data(provider_code, data)` →
   `_get_tx_from_notification_data()` (lookup 100% DB: `reference`,
   `provider_reference` o campo propio) → `_process_notification_data()` → transición de
   estado (`payment/models/payment_transaction.py:670-710`).
3. **Transiciones de estado idempotentes.** `_set_pending/_set_done/_set_error/...` solo
   escriben si el estado actual está en `allowed_states`
   (`payment/models/payment_transaction.py:799-856`). Un webhook duplicado entregado a otro
   worker se ignora silenciosamente. Esa es la estrategia de concurrencia del core: no hay
   `SELECT FOR UPDATE`, hay idempotencia.
4. **Verificación stateless de callbacks.** `payment.utils.generate_access_token` /
   `check_access_token` (HMAC derivado de los propios parámetros,
   `payment/utils.py:15-44`): cualquier worker valida sin estado compartido.
5. **Campos propios en `payment.transaction`** para datos específicos del provider
   (patrón `_inherit` + campos `<code>_*`), nunca blobs en variables de módulo.
6. **Cron de finalización tolerante a fallos** que re-procesa por dominio sobre la DB
   (`payment/models/payment_transaction.py:980-1007`).

El módulo Azul ya usa partes de esto (estados, `azul_3ds_session_data` para el polling del
frontend, cron de verificación), pero el corazón del flujo 3DS quedó delegado al estado en
RAM de pyazul. La propuesta cierra esa brecha.

### Insight clave que habilita el fix

Los dos endpoints de Azul que se invocan desde callbacks **no necesitan nada que no esté
(o no pueda estar) en la base de datos**:

| Endpoint | Payload requerido | Fuente tras el fix |
|---|---|---|
| `ProcessThreeDSMethod` | `Channel`, `Store`, `AzulOrderId`, `MethodNotificationStatus`, `Amount`, `Currency` ("DOP"), `OrderNumber`, `Itbis` | DB: `azul_order_id` + snapshot persistido del request inicial |
| `ProcessThreeDSChallenge` | `Channel`, `Store`, `AzulOrderId`, `CRes` | DB: `azul_order_id`; `CRes` viene en el POST del ACS |

(Verificado en `pyazul/services/secure.py:344-356` y `:383-392` — los valores que pyazul
saca del `session_store` son exactamente esos.) Además, el cliente HTTP de pyazul es
accesible sin pasar por `SecureService`: `PyAzul.api._async_request(data, operation=...,
is_secure=True)` (`pyazul/index.py:64`, `pyazul/api/client.py:242-294`), y
`create_challenge_form` es un helper estático sin estado (`pyazul/services/secure.py:41`).
**No se requiere ningún cambio en pyazul.**

---

## 4. Solución propuesta

### 4.0 Principio de diseño

> Después de la respuesta inicial de `secure_sale`/`secure_hold`, el módulo no vuelve a
> leer ni escribir el `session_store` de pyazul. Todo paso posterior (method, challenge,
> verificación, rescate por cron) se reconstruye desde `payment.transaction` y se envía a
> Azul con llamadas directas al API client. Cualquier worker puede atender cualquier paso.

### 4.1 Nuevos campos en `payment.transaction`

```python
azul_secure_id = fields.Char(
    string="Azul 3DS Correlation ID",
    index=True, readonly=True,
    help="Correlation ID appended to the 3DS callback URLs. Used to locate the "
         "transaction from ACS callbacks; it is NOT the provider reference.",
)
azul_3ds_request_data = fields.Json(
    string="Azul 3DS Request Snapshot",
    readonly=True,
    help="Exact Amount/Itbis/OrderNumber sent in the initial secure request. "
         "Required to replay ProcessThreeDSMethod statelessly from any worker.",
)
azul_3ds_method_processed = fields.Boolean(
    string="3DS Method Processed", readonly=True,
    help="Database-backed idempotency flag for duplicate 3DS method notifications.",
)
```

Decisiones:

- **`azul_secure_id` reemplaza el abuso de `provider_reference`.** `provider_reference`
  pasa a contener el `AzulOrderId` (convención del core). El `secure_id` sigue siendo el
  parámetro que pyazul añade a `TermUrl`/`MethodNotificationUrl`
  (`pyazul/services/secure.py:170-173`), así que se conserva como clave de correlación de
  callbacks — pero persistida e indexada en DB.
- **Snapshot vs recálculo:** `ProcessThreeDSMethod` debe repetir el `Amount`/`Itbis`/
  `OrderNumber` del request original. Recalcularlos con `_to_dop_cents()` en el callback
  reintroduciría riesgo de divergencia (la conversión USD→DOP usa la tasa del día:
  `models/payment_transaction.py:233`). Se persiste el valor exacto enviado, en centavos,
  tal cual salió en la iniciación.
- **PCI:** el snapshot contiene solo montos y referencia de orden. **Nunca** se persiste
  PAN/CVC/expiración (que es lo que pyazul sí guarda en su session para holds —
  `pyazul/services/secure.py:189-230` — y la razón por la que "persistir el session_store
  completo" se descartó, ver §5).
- Se mantiene `azul_order_id` (ya existe, indexado) y `azul_3ds_session_data` (HTML del
  form pendiente que el frontend recoge vía polling `_get_post_processing_values` — ese
  mecanismo ya es DB-based y multi-worker-safe; se conserva tal cual, limpiándolo al llegar
  a estado final).

### 4.2 Iniciación (`_handle_secure_response`, `models/payment_transaction.py:370`)

Cambios:

1. `self.azul_secure_id = result["id"]` (en vez de `provider_reference`).
2. `AzulOrderId` de la respuesta → `self.azul_order_id` **y** `self.provider_reference`.
   La respuesta de Azul lo incluye en los tres escenarios (3D2METHOD, 3D challenge,
   aprobación directa). El fallback actual a `get_session_info()` se conserva solo como
   última red dentro del mismo request (mismo worker, válido) y loguea WARNING si se usa.
3. Persistir el snapshot:
   ```python
   self.azul_3ds_request_data = {
       "Amount": payment_data["Amount"],
       "Itbis": payment_data["Itbis"],
       "OrderNumber": payment_data["OrderNumber"],
   }
   ```
4. Si la respuesta es aprobación/declinación directa (sin 3DS), limpiar
   `azul_secure_id`/`azul_3ds_request_data` — no hay callbacks que esperar.

La iniciación **sigue usando `pyazul.secure_sale/secure_hold`** sin cambios: ocurre en un
solo request/worker y no tiene problema de concurrencia. Solo dejamos de depender de lo que
pyazul recuerda después.

### 4.3 Method notification stateless (reemplaza `_process_3ds_method_notification`)

Nuevo método que construye el payload desde DB y llama el endpoint directo:

```python
def _azul_send_3ds_method(self, status="RECEIVED"):
    """Send ProcessThreeDSMethod to Azul, rebuilt entirely from DB state."""
    self.ensure_one()
    snapshot = self.azul_3ds_request_data or {}
    data = {
        "Channel": "EC",
        "Store": self.provider_id.azul_webservices_merchant_account,
        "AzulOrderId": self.azul_order_id,
        "MethodNotificationStatus": status,
        "Amount": snapshot.get("Amount"),
        "Currency": "DOP",
        "OrderNumber": snapshot.get("OrderNumber"),
        "Itbis": snapshot.get("Itbis"),
    }
    return self.provider_id._azul_make_request(
        lambda client: azul_utils.run_async(
            client.api._async_request(data, operation="processthreedsmethod", is_secure=True)
        ),
        offline=True,
    )
```

**Idempotencia cross-worker** (sustituye al `processed_methods` en RAM de pyazul y al check
frágil `"3DS Challenge" in azul_3ds_session_data` de `models/payment_transaction.py:1302`):
reclamo atómico del flag antes de llamar a Azul:

```python
self.env.cr.execute(
    """UPDATE payment_transaction
          SET azul_3ds_method_processed = TRUE
        WHERE id = %s AND azul_3ds_method_processed IS NOT TRUE
        RETURNING id""",
    [self.id],
)
if not self.env.cr.fetchall():
    return  # otro worker ya lo procesó (o lo está procesando)
self.invalidate_recordset(["azul_3ds_method_processed"])
```

Si la llamada a Azul falla con error técnico (timeout/red), se revierte el flag para que el
duplicado del ACS o el cron lo reintente. El resto del manejo de respuesta
(`3D_SECURE_CHALLENGE` → `_handle_3ds_challenge_response`, `APROBADA` → notificación,
errores → `_set_error`) se conserva.

### 4.4 Challenge stateless

En `_handle_3ds_challenge_response` (`models/payment_transaction.py:1395`) y en el
controller:

1. **Corrección del TermUrl del challenge post-method:** construirlo con la correlación
   propia: `term_url = f"{base_url}{route}?secure_id={self.azul_secure_id}"`
   (hoy va pelado, `models/payment_transaction.py:1418` — bug colateral §2.3).
   `create_challenge_form` es estático y se sigue usando tal cual.
2. **Procesamiento del CRes sin sesión** (reemplaza `client.process_challenge` en
   `controllers/main.py:175-183`):

```python
def _azul_send_3ds_challenge(self, cres):
    """Send ProcessThreeDSChallenge to Azul. Only needs AzulOrderId (DB) + CRes (ACS POST)."""
    self.ensure_one()
    data = {
        "Channel": "EC",
        "Store": self.provider_id.azul_webservices_merchant_account,
        "AzulOrderId": self.azul_order_id,
        "CRes": cres,
    }
    return self.provider_id._azul_make_request(
        lambda client: azul_utils.run_async(
            client.api._async_request(data, operation="processthreedschallenge", is_secure=True)
        ),
        offline=True,
    )
```

Idempotencia: si el ACS reenvía el CRes (refresh, doble POST), la primera respuesta ya
movió la transacción a estado final; `_process_notification_data` + `_update_state` del
core ignoran la segunda. Si Azul rechaza un CRes repetido con error, el handler solo marca
error si `state == 'pending'` (mismo criterio que `_verify_transaction_status`).

### 4.5 Controller `/payment/azul_webservices/3ds_return` (`controllers/main.py:97`)

Reescritura para alinearse al pipeline estándar:

1. **Lookup:** `azul_secure_id` (campo dedicado, indexado) como clave primaria de búsqueda;
   fallback por `reference`/`CustomOrderId` se conserva. Dominio sin el filtro de UUID.
2. **Despacho por fase** (igual que hoy: `threeDSMethodData` → method, `CRes` → challenge,
   resto → `_verify_transaction_status()`), pero invocando los métodos stateless nuevos.
3. **Canalizar por `_handle_notification_data`:** extender
   `_get_tx_from_notification_data` para resolver por `azul_secure_id`/`azul_order_id`,
   de modo que el controller haga
   `request.env["payment.transaction"].sudo()._handle_notification_data("azul_webservices", data)`
   y herede gratis `_execute_callback()` idempotente y el logging estándar del core.
4. **Respuesta rápida al method notification:** el iframe del ACS tiene timeout de ~10s
   (EMVCo). El handler hace una sola llamada HTTP a Azul; sin cambios de comportamiento
   visible, pero se documenta la restricción en el docstring.
5. Seguridad: el `secure_id` es un UUID4 (~122 bits de entropía) que actúa como bearer
   token de correlación, más el dominio restringido por `provider_code` y estado. Es el
   mismo nivel de garantía que hoy, ahora con lookup determinista. (Mejora opcional, no
   bloqueante: añadir `access_token` HMAC de `payment.utils` al TermUrl que nosotros
   construimos en el paso 4.4.1.)

### 4.6 Cron de rescate (`_azul_cron_verify_pending_transactions`)

El endpoint `VerifyPayment` de Azul es stateless por naturaleza (consulta por
`CustomOrderId` = `tx.reference`) y ya está implementado (`_verify_transaction_status`).
Cambios al dominio (`models/payment_transaction.py:1226-1239`):

```python
[
    ("provider_code", "=", "azul_webservices"),
    ("state", "=", "pending"),
    ("create_date", "<=", cutoff_time),   # cutoff: 15 min para no pisar flujos 3DS activos
]
```

- Se eliminan las exclusiones por `azul_3ds_session_data` y por `provider_reference`
  UUID-like: con el flujo stateless ya no hay "sesión activa en RAM" que proteger, y las
  transacciones 3DS atascadas (las víctimas actuales) pasan a ser rescatables.
- Al cerrar una transacción (done/cancel/error), limpiar `azul_3ds_session_data` para que
  el polling del frontend no re-inyecte un challenge viejo.
- Esto convierte el cron en la **red de seguridad** del flujo: aunque un callback se pierda
  por completo (red, ACS caído), la transacción converge a su estado real en ≤ ~30-45 min.

### 4.7 `utils.py` — caché de cliente

- El comentario *"Caching is required to maintain PyAzul's internal 3DS session state"*
  (`utils.py:14,85,93`) queda obsoleto: la corrección hace que **ningún** flujo dependa de
  la sesión del cliente. El caché se conserva solo por costo de construcción (SSL context,
  settings), con clave `f"provider_{id}_{write_date}"` para invalidar al editar
  credenciales (bug colateral §2.3).
- Higiene de memoria: tras una iniciación 3DS, purgar la entrada del `session_store` del
  cliente cacheado (`client.secure.session_store.pop(secure_id, None)`) — evita acumular
  PAN/CVC en RAM del worker indefinidamente (hoy las sesiones solo se limpian si el flujo
  completa en el mismo worker).

### 4.8 Migración de datos

Script de migración del módulo (pre-init o `migrations/`):

```sql
-- secure_id mal ubicado en provider_reference → mover a azul_secure_id
UPDATE payment_transaction
   SET azul_secure_id = provider_reference,
       provider_reference = azul_order_id
 WHERE provider_code = 'azul_webservices'
   AND provider_reference ~* '^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}$';
```

Las transacciones `pending` atascadas pre-deploy no tienen snapshot
(`azul_3ds_request_data` vacío) → no se les puede replayar el method, pero el cron ampliado
(§4.6) las verifica vía `VerifyPayment` y las cierra en su estado real. Es el camino de
saneamiento del backlog de producción.

### 4.9 Flujo resultante

```
1. POST /process              → Worker A: pyazul.secure_sale()
                                 DB ← azul_secure_id, azul_order_id, provider_reference,
                                      azul_3ds_request_data, azul_3ds_session_data, state=pending
2. ACS method notification    → Worker B: lookup DB por azul_secure_id
                                 claim atómico azul_3ds_method_processed
                                 ProcessThreeDSMethod directo (payload 100% desde DB)
                                 → challenge: DB ← azul_3ds_session_data (HTML), TermUrl con secure_id
                                 → aprobada: _handle_notification_data → done
3. Frontend polling           → Worker C: lee azul_3ds_session_data desde DB → muestra challenge
4. ACS POST CRes              → Worker D: lookup DB por azul_secure_id
                                 ProcessThreeDSChallenge directo (AzulOrderId desde DB + CRes)
                                 _handle_notification_data → done/cancel
5. Red de seguridad           → cron (cualquier worker): VerifyPayment por reference
```

Ningún paso asume el worker del paso anterior. El bug es estructuralmente imposible.

---

## 5. Alternativas evaluadas y descartadas

| Alternativa | Por qué se descarta |
|---|---|
| **B. Re-sembrar el `session_store` del worker receptor desde DB antes de llamar a pyazul** | Funciona, pero mantiene dos fuentes de verdad y escribe en internals de la librería (frágil ante upgrades de pyazul). Más código para el mismo resultado que la llamada directa. Solo tendría sentido si los endpoints necesitaran datos que no podemos reconstruir — no es el caso. |
| **C. `session_store` persistente (dict-like respaldado en DB/Redis) inyectado a `SecureService`** | `SecureService.__init__` acepta `session_store`, pero la fachada `PyAzul` no lo propaga (`pyazul/index.py:71`) → habría que instanciar servicios a mano. Peor: la sesión de pyazul guarda `card_number`/`expiration`/`cvc` para holds (`pyazul/services/secure.py:189-230`); persistirla a DB es una **violación PCI-DSS directa** (prohibido almacenar CVC post-autorización). Redis no existe en odoo.sh. Descartada con firmeza. |
| **D. Afinidad de sesión / reducir a 1 worker** | odoo.sh no ofrece sticky sessions por proceso; 1 worker degrada toda la instancia de producción; y el estado en RAM igual muere con el reciclaje de workers. No es solución, es ocultamiento. |
| **E. Parchear pyazul para que su store sea persistente** | Convierte un fix de módulo en mantenimiento de un fork de SDK. El SDK ya declara explícitamente que la persistencia es responsabilidad de la aplicación. |

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El payload directo difiera de lo que Azul espera (vs lo que arma pyazul) | Los payloads propuestos son **byte-equivalentes** a los de `pyazul/services/secure.py:344-356` y `:383-392`; mismos campos, mismas fuentes. Tests unitarios comparan contra el payload de pyazul. |
| Carrera entre dos method notifications simultáneas en workers distintos | Claim atómico vía `UPDATE ... RETURNING` (§4.3); a lo sumo una llamada llega a Azul. |
| CRes duplicado | Transiciones idempotentes del core; error de Azul en repetido no pisa estados finales. |
| Snapshot ausente (transacciones viejas o flujo no-3DS) | Guard: sin `azul_3ds_request_data` → fallback inmediato a `_verify_transaction_status()`. |
| Regresión en flujos no-3DS, tokenización, refund/capture/void | No se tocan: ya son stateless (usan `azul_order_id` de DB). Suite de regresión los cubre. |
| Migración marca mal un `provider_reference` | Regex UUID estricta + solo `provider_code = azul_webservices`; dry-run sobre dump de producción antes del deploy. |

---

## 7. Plan de validación

1. **Tests unitarios** (mock de `AzulAPI._async_request`):
   - payload de `_azul_send_3ds_method` / `_azul_send_3ds_challenge` == payload que pyazul
     habría construido con sesión viva;
   - idempotencia del claim de method (dos llamadas concurrentes → una sola request);
   - lookup del controller por `azul_secure_id` en cada fase;
   - dominio del cron incluye 3DS atascadas y respeta el cutoff.
2. **Repro empírico (la prueba reina):** adaptar `~/repos/azul-3ds-repro` para ejecutar el
   flujo nuevo con `--workers=4`, forzando que iniciación, method y challenge caigan en
   PIDs distintos (mismo harness que ya demostró 8/8 fallos). Criterio de aceptación:
   **0 fallos en N ≥ 50 corridas cross-worker**.
3. **Staging odoo.sh:** smoke test funcional del flujo completo (no valida el fix
   multi-worker — staging tiene 1 worker — pero valida integración real con Azul de
   pruebas).
4. **Producción:** deploy + monitoreo de logs (`No session data found` debe desaparecer) +
   verificación de que el cron ampliado drena el backlog de transacciones `pending`
   atascadas. Rollback: revertir el deploy; la migración de datos es no destructiva
   (`azul_secure_id` es campo nuevo; `provider_reference` queda con `azul_order_id`, que es
   el valor correcto también para el código viejo en flujos no-3DS).

---

## 8. Alcance y esfuerzo estimado

| Pieza | Archivos | Esfuerzo |
|---|---|---|
| Campos nuevos + snapshot en iniciación | `models/payment_transaction.py` | 0.5 d |
| Métodos stateless method/challenge + idempotencia | `models/payment_transaction.py` | 1 d |
| Controller + `_get_tx_from_notification_data` | `controllers/main.py`, `models/payment_transaction.py` | 0.5 d |
| Cron + limpieza `azul_3ds_session_data` + utils/caché | `models/payment_transaction.py`, `utils.py` | 0.5 d |
| Migración + tests + corrida repro 4 workers | `migrations/`, `tests/`, repro env | 1–1.5 d |
| **Total** | | **~3.5–4 días** |

Sin cambios en pyazul, sin dependencias nuevas, sin cambios de infraestructura.
