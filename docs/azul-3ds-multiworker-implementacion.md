# Azul 3DS multi-worker: informe de implementación y cierre

**Fecha:** 2026-06-11
**Módulo:** `payment_azul_webservices` 17.0.1.2.2 → **17.0.1.3.0**
**Branch:** `17.0-fix-3ds-azul-lf`
**Documento de diseño:** [propuesta-fix-3ds-azul-multiworker.md](./propuesta-fix-3ds-azul-multiworker.md) (aprobada e implementada)
**Severidad original:** Crítica — pagos 3DS fallando intermitentemente solo en producción

---

## 1. Resumen ejecutivo

Los pagos con 3D Secure fallaban únicamente en producción (odoo.sh, 4+ workers HTTP) y
nunca en staging (1 worker). Causa raíz confirmada empíricamente: el módulo dependía del
`session_store` de pyazul —un diccionario Python **en memoria de cada proceso worker**—
para continuar el flujo 3DS, pero los callbacks del banco (method notification y CRes del
challenge) caen en cualquier worker, sin afinidad. Con 4 workers, la probabilidad de que
todo el flujo cayera en el proceso correcto era ~6%.

**Solución implementada:** flujo 3DS 100% stateless. Todo el estado intermedio se persiste
en `payment.transaction`; los callbacks reconstruyen las llamadas a Azul
(`ProcessThreeDSMethod`, `ProcessThreeDSChallenge`) directamente desde la base de datos.
Cualquier worker puede atender cualquier paso. Sin cambios en pyazul, sin dependencias
nuevas, sin cambios de infraestructura.

**Validación final:** flujo real completo contra Azul test APROBADO con la iniciación en
un proceso que murió antes de los callbacks, el method atendido por un worker y el
challenge por otro distinto. Con el código anterior, ese mismo escenario fallaba 8/8 veces.

---

## 2. Cronología

| Fecha | Hito |
|---|---|
| 2026-06-09 | Hipótesis de workers confirmada en entorno aislado `~/repos/azul-3ds-repro`: 4 workers → 8/8 challenges fallidos; 1 worker → 24/24 OK |
| 2026-06-11 | Repro portado al contenedor dev (`lfernandez_v17`): sintético + módulo real + flujo real end-to-end contra Azul test |
| 2026-06-11 | Propuesta aprobada → implementación → validación (harness 12/12, e2e real ×2, suite unitaria 17/17) |
| 2026-06-11 | Entregables de calidad: README.rst, demo data, traducciones, tests unitarios, migración |

---

## 3. Diagnóstico y evidencia (3 niveles)

### 3.1 Nivel 1 — Mecanismo aislado (`azul_mw_repro`)

Addon mínimo que ejecuta el `SecureService.process_challenge` REAL de pyazul con el mismo
patrón de caché por proceso del módulo. El error ocurre **antes de cualquier llamada de
red** (pyazul busca la sesión primero), así que no se necesitan credenciales.

- 4 workers: pago sembrado en PID 11, callbacks cayeron en PIDs 10/12 → **8/8 fallos** con
  el error exacto de producción: `No session data found for session_id`.
- 1 worker (config de staging): **24/24 APROBADA, 0 fallos** — explica por qué staging
  nunca reproduce.

### 3.2 Nivel 2 — Módulo real seedeado (`azul_ws_repro`)

Harness que deja el sistema exactamente como lo deja `secure_sale` real (transacción
`payment.transaction` real en `pending` + sesión en el cliente pyazul cacheado por el
`utils.get_pyazul_client()` real) y dispara el callback contra el endpoint REAL
`/payment/azul_webservices/3ds_return`. Solo la capa de red está stubbeada (el bug ocurre
antes de la red).

- Cross-worker: transacción real → `state=error` con el mensaje de producción.
- Mismo worker (control): → `done` APROBADA.

### 3.3 Nivel 3 — Flujo real end-to-end (Azul test + ACS Modirum)

Pago real de factura desde el browser: `secure_sale` real → AzulOrderId real → method
iframe → callback a worker aleatorio:

```
Worker 719 (15:51): secure_sale real → AzulOrderId 44917929 → requires 3DS
Worker 718 (15:56): method notification → pyazul sin sesión → SESSION_NOT_FOUND
DB: INV/2026/00003 → state=error
```

Mismo error, mismo mecanismo, con tráfico real. **Causa raíz confirmada en los 3 niveles.**

> Dato clave que lo hizo posible: los callbacks 3DS (method y CRes) viajan **por el
> browser del cliente**, no server-to-server, por eso funcionan contra localhost.

---

## 4. Causa raíz

```
1. POST /process              → Worker A: pyazul.secure_sale()
                                 session_store[secure_id] = {...}   ← SOLO EN RAM DE A
2. ACS method notification    → Worker B: busca la sesión en SU RAM → SESSION_NOT_FOUND
3. ACS POST CRes              → Worker C: AzulError "No session data found for session_id"
```

El propio README de pyazul lo advierte: *"For production, your application MUST implement
its own persistent session management"*. El módulo no lo hacía: el comentario de
`utils.py` ("Caching is required to maintain PyAzul's internal 3DS session state") era la
raíz conceptual del diseño roto. Nota: incluso con 1 worker, el reciclaje de procesos
(`limit_request`, deploys) mataba ese estado.

---

## 5. Solución implementada

> Principio: después de la respuesta de `secure_sale`/`secure_hold`, el módulo no vuelve a
> tocar el `session_store` de pyazul. Todo paso posterior se reconstruye desde
> `payment.transaction` y se envía a Azul con llamadas directas
> (`PyAzul.api._async_request(data, operation=..., is_secure=True)`), con payloads
> byte-equivalentes a los que pyazul armaba desde su sesión.

### 5.1 Campos nuevos en `payment.transaction`

| Campo | Propósito |
|---|---|
| `azul_secure_id` (Char, indexado) | ID de correlación que pyazul añade a TermUrl/MethodNotificationUrl. Es como los callbacks del ACS localizan la transacción. Antes se guardaba (mal) en `provider_reference` |
| `azul_3ds_request_data` (Json) | Snapshot exacto de `Amount`/`Itbis`/`OrderNumber` del request inicial. `ProcessThreeDSMethod` debe repetirlos; recalcular podría divergir (tasa USD→DOP del día) |
| `azul_3ds_method_processed` (Boolean) | Idempotencia en DB para method notifications duplicadas; reemplaza el dict en RAM de pyazul. Claim atómico con `UPDATE … RETURNING`; se libera ante fallo técnico para permitir reintento |

`provider_reference` pasa a contener el **AzulOrderId** (convención del core Odoo: la
referencia del PSP). Se mantiene `azul_3ds_session_data` (HTML del form pendiente que el
frontend recoge por polling — mecanismo ya stateless), limpiándolo al llegar a estado
final.

### 5.2 Cambios por archivo

**`models/payment_transaction.py`**
- `_handle_secure_response(result, request_fields)`: persiste `azul_secure_id`, snapshot,
  `azul_order_id`+`provider_reference`; purga la sesión pyazul del worker (higiene PCI:
  para holds esa sesión retiene PAN/CVC); limpia correlación en aprobaciones directas.
- `_azul_send_3ds_method()` / `_azul_send_3ds_challenge(cres)`: llamadas directas a los
  endpoints de Azul con payload 100% desde DB.
- `_process_3ds_method_notification()`: claim idempotente → llamada → manejo de
  challenge/aprobación/error; libera el claim ante fallo técnico.
- `_azul_process_3ds_challenge(cres)`: reemplaza el `client.process_challenge` (que
  requería la sesión del worker iniciador).
- `_get_tx_from_notification_data()`: lookup extendido por `azul_secure_id` y
  `azul_order_id` (lecturas puras de DB).
- `_process_notification_data()`: estados 3DS **en vuelo** (`IsoCode` `3D`/`3D2METHOD`)
  mantienen `pending` en vez de matar el flujo; estados finales limpian el form 3DS.
- Cron `_azul_cron_verify_pending_transactions()`: dominio simplificado (pending > 15
  min, sin exclusiones) + cancelación de flujos abandonados > 2 horas (seguro: sin
  autenticación completada nunca hay autorización ni cobro).

**`controllers/main.py`** — `/payment/azul_webservices/3ds_return` stateless: localiza por
`azul_secure_id`, despacha por fase (method / CRes / verify) a los métodos nuevos.

**`utils.py`** — caché de cliente solo por rendimiento (SSL context), con `write_date` en
la clave → editar credenciales invalida el cliente cacheado. Comentarios corregidos.

**`migrations/17.0.1.3.0/post-migration.py`** — mueve los UUID de `provider_reference` a
`azul_secure_id` y pone `provider_reference = azul_order_id`. No destructiva (regex UUID
estricta, solo provider azul). Verificada sobre datos reales.

### 5.3 Flujo resultante

```
1. POST /process            → Worker A: secure_sale → DB ← todo el estado 3DS
2. ACS method notification  → Worker B: lookup DB por azul_secure_id → claim atómico
                              → ProcessThreeDSMethod directo → challenge o aprobación
3. Frontend polling         → Worker C: lee el form desde DB → muestra challenge
4. ACS POST CRes            → Worker D: ProcessThreeDSChallenge directo → done/cancel
5. Red de seguridad         → cron: VerifyPayment por CustomOrderId; abandono a las 2h
```

Ningún paso asume el worker del paso anterior: el bug es estructuralmente imposible.

---

## 6. Bugs colaterales encontrados y corregidos (mismo origen o destapados por él)

1. **Challenge post-method sin correlación**: el form del challenge derivado del method se
   construía con TermUrl **sin** `secure_id` → ese CRes jamás se podía correlacionar,
   incluso cayendo en el worker correcto. Corregido (TermUrl con `secure_id`).
2. **El cron excluía justo a las víctimas**: el dominio excluía transacciones con
   `azul_3ds_session_data` o `provider_reference` con pinta de UUID — exactamente las 3DS
   atascadas. Quedaban en `pending` para siempre. Corregido.
3. **`provider_reference` con el secure_id** (UUID interno sin significado para Azul) en
   vez del AzulOrderId. Corregido + migración.
4. **Caché de cliente sin invalidación**: cambiar credenciales/certs no surtía efecto
   hasta reiniciar workers. Corregido (clave con `write_date`).
5. **Verificar a mitad de 3DS mataba la transacción** (destapado durante las pruebas):
   `VerifyPayment` devuelve `IsoCode=3D2METHOD` ("el cliente sigue autenticando") y el
   módulo lo trataba como fallo → `error` sobre un flujo legítimo. Crítico también para
   el cron en producción. Corregido (estados en vuelo mantienen `pending`) + cierre por
   abandono a las 2 horas.

---

## 7. Validación

| Prueba | Resultado |
|---|---|
| Harness cross-worker (`azul_ws_repro`, 12 intentos, workers 34/36/37) | **12/12 `done` APROBADA** (con el código viejo: 8/8 fallos) |
| Flujo real e2e #1 (`FIXTEST-7963`): iniciación en proceso shell **muerto** → method en worker 36 → challenge ACS Modirum real → CRes en worker 35 | **APROBADA / `done`** — 3 procesos sin memoria compartida |
| Flujo real e2e #2 (`FIXTEST-28901`): ciclo completo tras recuperación del entorno test de Azul | **APROBADA / `done`** |
| Suite unitaria (`--test-tags azul_webservices`, DB limpia y DB de trabajo) | **17 tests, 0 failed, 0 errors** |
| Migración sobre datos reales (`test_v17e_azul`) | UUIDs movidos correcto; `INV/2026/00003`: `provider_reference=44917929` ✓ |
| Logs post-fix | Cero `No session data found` / `SESSION_NOT_FOUND` |

### Suite unitaria (`tests/test_stateless_3ds.py`)

`@tagged("post_install", "-at_install", "azul_webservices")`. Independientes (empresa
dedicada con moneda DOP como default del entorno, partner y provider propios, cada test
crea su transacción), sin red (cliente pyazul fake que graba cada request). Cubre:
persistencia stateless en iniciación, payloads method/challenge byte-exactos desde DB,
idempotencia del claim ante duplicados, liberación del claim en fallo técnico, TermUrl del
challenge con `secure_id`, estados en vuelo → `pending`, declinación → `cancel`, limpieza
del form en finales, lookup por `secure_id`/`AzulOrderId`, cron (rescata >15min, respeta
recientes, cancela abandonadas >2h), y empresa/moneda correctas.

```bash
odoo -d <db> --test-tags azul_webservices --stop-after-init --workers=0 --max-cron-threads=0
```

---

## 8. Entregables adicionales del módulo

- **`README.rst`** (inglés, estilo OCA): arquitectura stateless documentada, configuración,
  credenciales de prueba, tabla de tarjetas de test, instrucciones de tests, changelog.
- **`demo/payment_provider_demo.xml`**: credenciales del merchant de prueba
  (`39038540035` + auth `3dsecure`; set `splitit` = merchant sin 3DS, documentado).
  El `state` queda `disabled` a propósito: pasar a Test exige subir el cert mTLS
  (`required_if_provider`), y la private key jamás se commitea.
- **`i18n/es_DO.po`**: 100% traducido (0 términos vacíos), incluyendo los nuevos del fix.
- Versión 17.0.1.2.2 → **17.0.1.3.0** + migración.

### Tarjetas de prueba (resumen; detalle en README.rst del módulo)

| Tarjeta | Comportamiento | Límite |
|---|---|---|
| `4005520000000129` (12/28, CVV 123) | **Challenge + Method** — ejercita ambos callbacks | máx **RD$50** |
| `4147463011110059` | Challenge sin method | — |
| `4265880000000007` | Frictionless con method | — |
| `4147463011110117` | Frictionless sin method (aprueba directo) | — |

---

## 9. Infraestructura de pruebas creada (entorno dev)

| Pieza | Ubicación | Uso |
|---|---|---|
| Repro sintético | `~/repos/azul-3ds-repro` (+ evidencias de las corridas) | Demostración del mecanismo puro |
| Harness módulo real | `odoo-pro/azul_ws_repro` (untracked, repro-only) | Validación cross-worker del módulo; stub de red a nivel de clase solo para órdenes fake |
| Script repro módulo real | `~/repos/azul-3ds-repro/repro_real_module.sh` | Corrida automatizada contra el contenedor dev |
| Health-check Azul test | `dev_env_odoo_pro-17/azul_health.sh` | 3 niveles: API viva / ACS Modirum / transacción 3DS real |
| Certs dev mTLS | `dev_env_odoo_pro-17/certs/` (git-ignored) | `progressa.local.crt` + `progressa-dev-unencrypted.key` (par verificado por modulus) |
| Config repro del contenedor | `conf/odoo.conf`: `workers = 4`, `dbfilter = ^test_v17e_azul$` | **Temporal** — quitar para volver a modo dev normal |

---

## 10. Despliegue a producción

1. Merge de `17.0-fix-3ds-azul-lf` → deploy (la migración corre con el upgrade del módulo).
2. **Backlog de transacciones atascadas:** el cron ampliado las drena automáticamente vía
   `VerifyPayment` (autoritativo, por `CustomOrderId`):
   - Azul aprobó (cliente completó el 3DS pero el callback se perdió) → `done` + post-proceso.
   - Azul no la conoce (el flujo murió antes de autorizar — el caso masivo) → `error`; el
     cliente puede reintentar. **Sin cobros perdidos**: el bug mataba el flujo antes de
     cualquier autorización, la tarjeta nunca se cobró.
   - Declinada → `cancel`.
3. Opcional (auditoría): pase único sobre las que quedaron en `error` históricamente:
   ```python
   env['payment.transaction'].search([
       ('provider_code', '=', 'azul_webservices'),
       ('state', '=', 'error'),
       ('azul_order_id', '!=', False),
   ]).with_context(force_azul_verify=True, automated_verify=True)._verify_transaction_status()
   ```
4. Monitoreo post-deploy: `No session data found` debe desaparecer de los logs; las
   transacciones 3DS deben converger a estado final en segundos (o ≤ ~45 min vía cron si
   un callback se pierde).

---

## 11. Gotchas descubiertos en el camino (vale oro para el futuro)

- **ThreatMetrix y adblockers**: la página del method del ACS (Modirum) solo auto-postea
  tras completar device profiling de `online-metrix.net`. Un browser con adblock congela
  el flujo en "Please wait" — no es un bug del módulo. Probar en incógnito limpio.
- **Certs mTLS**: los `.txt` que circulaban eran el cert de **producción**
  (`progressagroup.local`) y la key era de **dev** — par descoordinado (modulus distinto),
  causa del `KEY_VALUES_MISMATCH` histórico. El cert dev correcto es
  `CN=progressa.local, OU=Desarrollo`. Verificar pares con
  `openssl x509/rsa -noout -modulus`.
- **pyazul lee los certs de env vars** (`AZUL_CERT`/`AZUL_KEY`), no de los atributos de
  settings — `utils.py` ya aplica el workaround.
- **Azul test es intermitente**: `SGS-050655 Unable to verify card enrollment` o
  `DECLINADA: No autenticada` en todas las tarjetas = su ACS de pruebas caído (502 en
  Modirum), no un problema de configuración. Usar `azul_health.sh`.
- **Credenciales test**: `splitit` = merchant SIN 3DS (aprueba directo); `3dsecure` =
  merchant 3DS. Con la tarjeta de challenge el monto debe ser ≤ RD$50.
- **Docker Desktop (macOS)**: el mount puede servir `__pycache__` viejo aunque el `.py`
  esté actualizado → limpiar `__pycache__` + restart tras editar código del módulo.
- **El veredicto de los tests** es la línea `odoo.tests.result: 0 failed...`; los
  `ERROR`/tracebacks intermedios pueden ser ruido esperado de tests de caminos negativos.
