# payment_azul_webservices — Documentación Técnica

**Módulo:** `payment_azul_webservices`
**Versión:** 17.0.1.1.1
**Autor:** INDEXA SRL / Progressa Group
**Categoría:** Accounting / Payment Providers
**Licencia:** Propietaria
**Dependencia externa:** `pyazul` (librería Python)

---

## Tabla de Contenidos◊◊

1. [Propósito del Módulo](#1-propósito-del-módulo)
2. [Diferencia con `payment_azul`](#2-diferencia-con-payment_azul)
3. [Arquitectura y Estructura de Archivos](#3-arquitectura-y-estructura-de-archivos)
4. [Conceptos Clave del Ecosistema Azul](#4-conceptos-clave-del-ecosistema-azul)
5. [Flujo Completo de Pago (sin 3DS)](#5-flujo-completo-de-pago-sin-3ds)
6. [Flujo Completo de Pago con 3D Secure](#6-flujo-completo-de-pago-con-3d-secure)
7. [DataVault — Tokenización de Tarjetas](#7-datavault--tokenización-de-tarjetas)
8. [Captura Manual y Void](#8-captura-manual-y-void)
9. [Reembolsos](#9-reembolsos)
10. [Verificación de Transacciones Pendientes (Cron)](#10-verificación-de-transacciones-pendientes-cron)
11. [Configuración del Proveedor en Odoo](#11-configuración-del-proveedor-en-odoo)
12. [Modelos de Datos](#12-modelos-de-datos)
13. [Controladores HTTP](#13-controladores-http)
14. [Capa JavaScript (Frontend)](#14-capa-javascript-frontend)
15. [PyAzul — Librería Subyacente](#15-pyazul--librería-subyacente)
16. [Códigos de Respuesta y Manejo de Errores](#16-códigos-de-respuesta-y-manejo-de-errores)
17. [Seguridad y Credenciales](#17-seguridad-y-credenciales)
18. [Métodos de Pago Soportados](#18-métodos-de-pago-soportados)
19. [Glosario de Términos](#19-glosario-de-términos)

---

## 1. Propósito del Módulo

`payment_azul_webservices` integra Odoo 17 con **Azul** (procesador de pagos dominicano) mediante su **API de WebServices** (integración directa/inline). El cliente ingresa los datos de tarjeta directamente en el formulario de Odoo — **sin redireccionamiento** al portal de Azul.

Capacidades principales:

| Función | Soportado |
|---------|-----------|
| Pago con tarjeta (inline) | ✅ |
| 3D Secure (3DS2) | ✅ |
| Tokenización (DataVault) | ✅ |
| Pago con token guardado | ✅ |
| Captura manual (authorize-then-capture) | ✅ parcial |
| Void (anulación antes de captura) | ✅ |
| Reembolso completo | ✅ |
| Express Checkout | ✅ |
| Monedas soportadas | DOP, USD |

---

## 2. Diferencia con `payment_azul`

El repositorio contiene **dos módulos** de Azul con enfoques distintos:

| Aspecto | `payment_azul_webservices` | `payment_azul` |
|---------|--------------------------|----------------|
| **Flujo** | Inline / Directo (WebServices API) | Redireccionamiento (Payment Page) |
| **Formulario tarjeta** | Dentro de Odoo | Página externa de Azul |
| **3DS** | Soporte completo | Sin soporte |
| **Captura manual** | Sí | No |
| **Void** | Sí | No |
| **Tokenización** | Full DataVault | Básica (vía redirect) |
| **Reembolso** | Sí | Sí |
| **Cron de verificación** | Sí (cada 30 min) | No |
| **Dependencia Python** | `pyazul` | Ninguna |
| **Complejidad frontend** | Alta (manejo 3DS) | Baja (auto-redirect) |
| **Autenticación** | SSL Cert + Auth1/Auth2 | MID + Signature Key |
| **Experiencia usuario** | Sin salir de la tienda | Abandona tienda temporalmente |

**Regla general:** Usar `payment_azul_webservices` para experiencia premium sin redirección y con 3DS completo. Usar `payment_azul` para integración básica con menor complejidad técnica.

---

## 3. Arquitectura y Estructura de Archivos

```
payment_azul_webservices/
├── __init__.py                        # Hooks post_init / uninstall
├── __manifest__.py                    # Declaración del módulo
├── const.py                           # Constantes y mappings
├── utils.py                           # PyAzul client factory + run_async
│
├── controllers/
│   └── main.py                        # Endpoints HTTP: /process y /3ds_return
│
├── models/
│   ├── account_payment_method.py      # Registro del método de pago azul_webservices
│   ├── payment_provider.py            # Configuración del proveedor + request helper
│   ├── payment_token.py               # Gestión y borrado de tokens DataVault
│   └── payment_transaction.py         # Core: toda la lógica de transacciones (~1340 líneas)
│
├── views/
│   ├── payment_azul_webservices_template.xml   # Formulario inline de tarjeta
│   ├── payment_provider_views.xml              # Formulario de configuración del proveedor
│   ├── payment_token_view.xml                  # Vista de tokens guardados
│   └── payment_transaction_views.xml           # Botones de acción en transacciones
│
├── data/
│   ├── payment_provider_data.xml      # Registro inicial del proveedor
│   └── payment_azul_cron.xml          # Cron job de verificación (cada 30 min)
│
├── static/src/js/
│   ├── payment_form.js                # Captura de datos de tarjeta + submit al servidor
│   └── post_processing.js             # Manejo de 3DS Method + Challenge modal
│
├── security/
│   └── ir.model.access.csv
└── i18n/
    └── es_DO.po
```

---

## 4. Conceptos Clave del Ecosistema Azul

### 4.1 Azul WebServices API

La **API de WebServices de Azul** permite a los comercios procesar pagos directamente desde su servidor, sin redirigir al cliente. El comercio recoge los datos de tarjeta, los envía a Azul vía HTTPS con certificado SSL mutuo, y recibe la respuesta en tiempo real.

Azul tiene dos entornos:
- **Desarrollo:** `pruebas.azul.com.do`
- **Producción:** `pagos.azul.com.do`

### 4.2 MID (Merchant Identification Number)

Número de identificación único del comercio ante Azul. Requerido en cada transacción. En Odoo se configura en el campo `azul_webservices_merchant_account`.

### 4.3 Auth1 / Auth2

Credenciales de autenticación del comercio para acceder a la API de WebServices. Son equivalentes a un usuario/contraseña de la API. Se envían como headers HTTP en cada petición.

### 4.4 SSL Certificate + Private Key (PEM)

La API de WebServices de Azul requiere **autenticación mutua TLS** (mTLS). El servidor del comercio presenta su certificado SSL al servidor de Azul. Azul solo acepta peticiones de certificados previamente registrados.

- `azul_webservices_cert_pem` — Contenido del certificado en formato PEM
- `azul_webservices_key_pem` — Clave privada correspondiente en formato PEM (también acepta Base64)

### 4.5 Channel

El campo `CHANNEL` identifica el tipo de integración. Para e-commerce se usa siempre `"EC"` (E-Commerce).

### 4.6 AzulOrderId

ID único que Azul asigna internamente a cada transacción exitosa. Se almacena en el campo `azul_order_id` de `payment.transaction` y es necesario para operaciones posteriores (reembolso, void, verificación).

### 4.7 CustomOrderId

Referencia del comercio que se envía a Azul con cada transacción. En Odoo es el campo `reference` de la transacción (ej. `S00001-1`). Permite verificar el estado de una transacción en Azul usando el ID del comercio.

### 4.8 IsoCode / ResponseCode

Código de respuesta estándar ISO 8583 que indica el resultado de la transacción:
- `00` = Aprobada
- Otros códigos = Rechazada/Error (ver sección de códigos de respuesta)

### 4.9 DataVault

El **DataVault** es el sistema de tokenización de Azul. Permite guardar los datos de una tarjeta en los servidores de Azul y recibir un token (`DataVaultToken`) para cobros futuros sin volver a ingresar los datos de tarjeta. Esto elimina el riesgo de almacenar datos PCI en el servidor del comercio.

- El token incluye: `DataVaultToken` (string único), `DataVaultBrand` (marca de la tarjeta), `DataVaultExpiration` (expiración)

### 4.10 3D Secure (3DS / 3DS2)

**3D Secure** es un protocolo de autenticación adicional diseñado por las redes de tarjetas (Visa, Mastercard) para reducir el fraude en pagos online. Verifica la identidad del portador de la tarjeta involucrando al banco emisor.

**3DS2** (segunda versión) es el estándar actual, más fluido que el antiguo 3DS1. Introduce:
- **Frictionless flow** — el banco aprueba automáticamente sin intervención del usuario
- **Challenge flow** — el banco pide verificación activa al usuario (OTP, biometría, etc.)

#### Componentes del flujo 3DS2:

| Término | Significado |
|---------|-------------|
| **3DS Method** | Pre-step que recopila datos del navegador del usuario enviándolos al banco emisor silenciosamente (en iframe oculto) |
| **ACS (Access Control Server)** | Servidor del banco emisor que realiza la autenticación 3DS |
| **3DS Method Data** | Datos enviados al ACS en el 3DS Method step |
| **3DS Session ID / AReq** | ID de sesión de autenticación generado por Azul |
| **Challenge** | Pantalla adicional del banco emisor (modal con iframe) donde el usuario verifica su identidad |
| **CReq (Challenge Request)** | Datos enviados al ACS para iniciar el challenge |
| **CRes (Challenge Response)** | Respuesta del ACS cuando el usuario completa el challenge |
| **threeDSMethodData** | Parámetro POST que el ACS envía de vuelta al callback del comercio tras el 3DS Method |
| **TermURL** | URL del comercio donde el ACS redirige al usuario después del challenge |
| **MethodNotificationURL** | URL del comercio que recibe la notificación silenciosa del 3DS Method |
| **Challenge Indicator** | Preferencia del comercio: sin preferencia (01), sin challenge (02), solicitar challenge (03), challenge mandatorio (04) |

---

## 5. Flujo Completo de Pago (sin 3DS)

```
Cliente (Browser)           Odoo Server              Azul API
      │                          │                       │
      │── Llena formulario ──────▶│                       │
      │   (número, exp, CVC)      │                       │
      │                          │                       │
      │── POST /payment/azul_webservices/process ────────▶│
      │   {reference, card_number,│                       │
      │    expiration, cvc,       │                       │
      │    save_card}             │                       │
      │                          │                       │
      │                          │── PyAzul.sale() ──────▶│
      │                          │   {CardNumber,         │
      │                          │    Expiration, CVC,    │
      │                          │    Amount, Currency,   │
      │                          │    MerchantId...}      │
      │                          │                        │
      │                          │◀── Response ──────────│
      │                          │   {IsoCode: "00",      │
      │                          │    AzulOrderId,        │
      │                          │    AuthorizationCode,  │
      │                          │    DataVaultToken?}    │
      │                          │                        │
      │                          │ _handle_successful_payment()
      │                          │ → tx._set_done()       │
      │                          │ → crear token si save_card
      │                          │                        │
      │◀── {success} ────────────│                        │
      │                          │                        │
      │── redirect → /payment/status                      │
```

**Métodos involucrados:**

1. `AzulPaymentController.process_payment()` — Recibe datos del formulario
2. `payment.transaction._send_payment_request()` — Orquestador principal
3. `payment.transaction._process_card_payment()` — Detecta si usar 3DS o no
4. `payment.transaction._process_non_3ds_payment()` — Envía a la API sin 3DS
5. `payment.provider._azul_make_request()` — Wrapper de llamada a PyAzul
6. `payment.transaction._process_notification_data()` — Procesa la respuesta
7. `payment.transaction._handle_successful_payment()` — Marca transacción como `done`

---

## 6. Flujo Completo de Pago con 3D Secure

### 6.1 Visión General

El flujo 3DS2 tiene **dos fases opcionales** antes de que el pago se autorice:

```
FASE 1: 3DS Method (fingerprinting)   →   FASE 2: Challenge (verificación usuario)   →   Pago
   [Silenciosa, iframe oculto]                [Visible, modal con iframe del banco]
```

### 6.2 Flujo Detallado

```
Cliente (Browser)           Odoo Server              Azul API / ACS
      │                          │                       │
      │── POST /payment/azul_webservices/process ────────▶│
      │                          │                       │
      │                          │── PyAzul.sale(enable_3ds=True) ──▶│
      │                          │                       │
      │                          │◀── Response: PENDING ─│
      │                          │   {azul_3ds_session_data: "<form...>",
      │                          │    is_method_form: true}
      │                          │                        │
      │◀── {redirect_form_html,  │                        │
      │     requires_3ds: true,  │                        │
      │     is_method_form: true}│                        │
      │                          │                        │
      │══ FASE 1: 3DS Method ═══════════════════════════ │
      │                          │                        │
      │── Crea iframe oculto con │                        │
      │   form del Method ────────────────────────────────▶ ACS
      │   (tdsMmethodForm)       │                    ACS recibe datos
      │                          │                    del browser
      │◀── POST /payment/azul_webservices/3ds_return ─────│
      │    (threeDSMethodData)   │                        │
      │                          │                        │
      │                          │ _process_3ds_method_notification()
      │                          │── PyAzul.process_3ds_method() ───▶│
      │                          │                        │
      │                          │◀── Response con CReq  │
      │                          │    (Challenge Request) │
      │                          │                        │
      │══ FASE 2: Challenge ════════════════════════════  │
      │                          │                        │
      │◀── {challenge_form_html} │                        │
      │                          │                        │
      │── Muestra modal con      │                        │
      │   iframe del ACS ─────────────────────────────────▶ ACS
      │   (banco emisor)         │                    Usuario verifica
      │                          │                    (OTP, biometría)
      │◀── ACS hace POST a TermURL ───────────────────────│
      │    con CRes              │                        │
      │                          │                        │
      │      GET /payment/azul_webservices/3ds_return     │
      │      (CRes parámetro)    │                        │
      │                          │                        │
      │                          │── PyAzul.process_challenge(CRes) ▶│
      │                          │                        │
      │                          │◀── Response final ────│
      │                          │   {IsoCode: "00",      │
      │                          │    AzulOrderId, Auth...}
      │                          │                        │
      │                          │ _process_notification_data()
      │                          │ tx._set_done()         │
      │                          │                        │
      │── redirect → /payment/status                      │
```

### 6.3 Callback Unificado `/payment/azul_webservices/3ds_return`

El módulo usa **un único endpoint** para manejar todos los callbacks de 3DS. La diferencia entre fases se detecta por parámetros:

| Parámetro recibido | Fase | Acción |
|-------------------|------|--------|
| `threeDSMethodData` | 3DS Method notification | `_process_3ds_method_notification()` |
| `CRes` o `cres` | Challenge response | `_handle_3ds_challenge_response()` + `process_challenge()` |
| Ninguno | Verificación general | `_verify_transaction_status()` |

### 6.4 Campos de `payment.transaction` para 3DS

| Campo | Descripción |
|-------|-------------|
| `azul_order_id` | ID asignado por Azul (persiste) |
| `azul_3ds_session_data` | HTML temporal del form 3DS (se limpia después) |
| `provider_reference` | Session ID de 3DS (también usado como AzulOrderId post-pago) |

### 6.5 Challenge Indicator

Configurable en el proveedor:

| Código | Descripción |
|--------|-------------|
| `01` | Sin preferencia (el banco decide) |
| `02` | No solicitar challenge (frictionless preferido) |
| `03` | Solicitar challenge activo |
| `04` | Challenge mandatorio por regulación |

---

## 7. DataVault — Tokenización de Tarjetas

### 7.1 Qué es

DataVault es el sistema de **almacenamiento seguro de tarjetas** de Azul. El comercio nunca almacena datos PCI; en su lugar recibe un `DataVaultToken` — string único que representa la tarjeta en los servidores de Azul.

### 7.2 Guardar tarjeta durante un pago

El usuario activa `Save card` en el formulario de pago. Odoo envía `SaveToDataVault: "1"` a Azul. La respuesta incluye:
- `DataVaultToken` — token único de la tarjeta
- `DataVaultBrand` — marca (Visa, Mastercard, etc.)
- `DataVaultExpiration` — expiración
- `CardNumber` — últimos 4 dígitos (masked)

Odoo crea un registro `payment.token` con `provider_ref = DataVaultToken`.

### 7.3 Pago con token guardado

```
payment.transaction._process_token_payment()
    └── PyAzul.sale_with_token({DataVaultToken, ...})
        → Azul usa la tarjeta almacenada
        → Sin ingresar datos de tarjeta nuevamente
```

### 7.4 Borrar token (archivar)

Al archivar un `payment.token` en Odoo:

```python
payment.token._handle_archiving()
    └── PyAzul.delete_token({TrxType: "DELETE", DataVaultToken: ...})
        → Azul elimina la tarjeta de DataVault
```

Si Azul falla el borrado, se lanza `ValidationError` para evitar tokens huérfanos.

---

## 8. Captura Manual y Void

### 8.1 Autorización sin captura (Hold)

Cuando el proveedor tiene `capture_manually = True`, el flujo es:

```
Sale → Estado "authorized" (fondos reservados, no capturados)
     → Botón "Capture" → Estado "done" (fondos capturados)
     → Botón "Void"    → Estado "cancel" (reserva liberada)
```

### 8.2 Captura parcial

El módulo declara soporte `"support_manual_capture": "partial"`. Se puede capturar un monto menor al autorizado.

**Método:** `payment.transaction._send_capture_request()`

```python
PyAzul.post_sale({
    "OriginalDate": ...,
    "AzulOrderId": tx.azul_order_id,
    "Amount": minor_amount,
    ...
})
```

### 8.3 Void (anulación)

**Método:** `payment.transaction._send_void_request()`

```python
PyAzul.void({
    "AzulOrderId": tx.azul_order_id,
    ...
})
```

Solo válido antes de que la transacción sea capturada/liquidada.

---

## 9. Reembolsos

**Tipo soportado:** Solo reembolso completo (`"support_refund": "full_only"`)

**Método:** `payment.transaction._send_refund_request()`

```python
PyAzul.refund({
    "AzulOrderId": tx.azul_order_id,
    "Amount": minor_amount,
    ...
})
```

Se crea una nueva `payment.transaction` con `operation = "refund"` y estado `done` si Azul confirma el reembolso.

El botón `Refund Transaction` aparece en el formulario de transacción solo cuando:
- `state == 'done'`
- `provider_code == 'azul_webservices'`

---

## 10. Verificación de Transacciones Pendientes (Cron)

### 10.1 Por qué existe

En casos de 3DS, fallos de red o timeouts, una transacción puede quedar en estado `pending` en Odoo sin que se haya recibido la respuesta final de Azul. El cron resuelve esto consultando el estado real en Azul.

### 10.2 Configuración

```xml
<field name="interval_number">30</field>
<field name="interval_type">minutes</field>
<field name="numbercall">-1</field>  <!-- infinito -->
```

Se ejecuta **cada 30 minutos** indefinidamente.

### 10.3 Lógica

```python
payment.transaction._azul_cron_verify_pending_transactions()
    → Busca txs con state='pending' y provider_code='azul_webservices'
    → Para cada una: _verify_transaction_status()
        → PyAzul.verify_payment({CustomOrderId: tx.reference})
        → Actualiza estado según respuesta de Azul
```

### 10.4 Verificación manual

Botón **"Verify Status"** en el formulario de transacción:
```python
payment.transaction.action_verify_azul_status()
```

Disponible para todas las transacciones de Azul (cualquier estado).

---

## 11. Configuración del Proveedor en Odoo

### 11.1 Campos de credenciales

Todos los campos de credenciales son `password=True` (enmascarados en UI) y solo visibles para usuarios con grupo `base.group_system`.

| Campo | Descripción | Requerido |
|-------|-------------|-----------|
| `azul_webservices_merchant_account` | MID del comercio | Sí |
| `azul_webservices_auth_1` | Authorization 1 | Sí |
| `azul_webservices_auth_2` | Authorization 2 | Sí |
| `azul_webservices_cert_pem` | Contenido del certificado SSL PEM | Sí |
| `azul_webservices_key_pem` | Clave privada SSL PEM o Base64 | Sí |

### 11.2 Campos de configuración 3DS

| Campo | Descripción | Default |
|-------|-------------|---------|
| `azul_webservices_enable_3ds` | Activar 3D Secure | `True` |
| `azul_webservices_challenge_indicator` | Preferencia de challenge | `01` (sin preferencia) |
| `azul_webservices_term_url` | URL de callback post-challenge | `/payment/azul_webservices/3ds_return` |
| `azul_webservices_method_notification_url` | URL de callback 3DS Method | `/payment/azul_webservices/3ds_return` |

### 11.3 Entorno

El módulo determina el entorno automáticamente según el estado del proveedor en Odoo:

| Estado Odoo | Entorno PyAzul | Servidor Azul |
|-------------|----------------|---------------|
| `enabled` | `prod` | `pagos.azul.com.do` |
| `test` / `disabled` | `dev` | `pruebas.azul.com.do` |

### 11.4 Capacidades declaradas

```python
{
    "support_tokenization": True,
    "support_refund": "full_only",
    "support_manual_capture": "partial",
    "support_express_checkout": True,
}
```

---

## 12. Modelos de Datos

### 12.1 `payment.provider` — Campos propios

```
azul_webservices_merchant_account    Char    MID
azul_webservices_auth_1              Char    Auth 1 (system only)
azul_webservices_auth_2              Char    Auth 2 (system only)
azul_webservices_cert_pem            Char    Certificado SSL PEM (system only)
azul_webservices_key_pem             Char    Clave privada PEM (system only)
azul_webservices_term_url            Char    TermURL 3DS
azul_webservices_method_notification_url  Char  Method URL 3DS
azul_webservices_challenge_indicator  Selection  Indicador de challenge
azul_webservices_enable_3ds          Boolean    Activar 3DS
```

### 12.2 `payment.transaction` — Campos propios

```
azul_order_id         Char    AzulOrderId de la transacción aprobada
azul_3ds_session_data Char    HTML temporal del form 3DS (se limpia post-proceso)
```

### 12.3 `payment.token` (heredado)

El token de Azul usa los campos estándar:
```
provider_ref    → DataVaultToken (el token de Azul)
payment_details → "Visa •••• 4242" (formato display)
```

---

## 13. Controladores HTTP

### 13.1 `POST /payment/azul_webservices/process`

```
Tipo:    JSON
Auth:    public
CSRF:    Sí
```

**Parámetros de entrada:**

| Parámetro | Tipo | Descripción |
|-----------|------|-------------|
| `reference` | str | Referencia de la transacción Odoo |
| `card_number` | str | Número de tarjeta |
| `expiration` | str | Formato YYYYMM |
| `cvc` | str | Código de seguridad |
| `save_card` | bool | Tokenizar la tarjeta |

**Respuesta posible:**

```json
// Si requiere 3DS:
{
    "redirect_form_html": "<form ...>",
    "requires_3ds": true,
    "is_method_form": true
}

// Si pago completo (sin 3DS): null
```

### 13.2 `GET/POST /payment/azul_webservices/3ds_return`

```
Tipo:    HTTP
Auth:    public
CSRF:    No (callback externo)
```

Endpoint unificado para todos los callbacks de 3DS. Detecta la fase por los parámetros presentes.

---

## 14. Capa JavaScript (Frontend)

### 14.1 `payment_form.js`

Extiende el mixin estándar `paymentForm` de Odoo.

**Métodos clave:**

| Método | Descripción |
|--------|-------------|
| `_prepareInlineForm()` | Fuerza flujo `direct` para Azul |
| `_processDirectFlow()` | Recopila datos de tarjeta y llama al endpoint |
| `_getInlineFormInputs()` | Obtiene campos del formulario inline |
| `_validateCardInputs()` | Validación básica de campos |
| `_extractCardData()` | Formatea expiración como YYYYMM |
| `_handlePaymentError()` | Maneja errores RPCError y genéricos |

**Formato de expiración:** El selector de mes/año se convierte a `YYYYMM` requerido por Azul.

### 14.2 `post_processing.js`

Maneja el flujo 3DS en el frontend. ~450 líneas.

**Responsabilidades:**

1. **3DS Method** — Crea iframe oculto con el form del Method:
   ```html
   <iframe style="display:none" ...>
       <form name="tdsMmethodForm" action="[ACS URL]">
           <input name="threeDSMethodData" value="...">
       </form>
   </iframe>
   ```
   Espera la notificación de Odoo y avanza al siguiente paso.

2. **Challenge modal** — Muestra modal con iframe del banco emisor:
   ```html
   <div class="modal ...">
       <iframe src="[ACS Challenge URL]">
           [Formulario de autenticación del banco]
       </iframe>
   </div>
   ```

3. **Polling de completación** — Detecta cuando el challenge termina mediante:
   - Conteo de formularios en el iframe (≤1 form = completado)
   - Monitoreo cross-origin con try/catch
   - Polling de fallback cada 2 segundos

4. **Limpieza** — Elimina modal y iframes al completar.

---

## 15. PyAzul — Librería Subyacente

### 15.1 Qué es

`pyazul` es la librería Python (dependencia externa) que abstrae la comunicación con la API de Azul WebServices. Es **asíncrona** (basada en `asyncio`).

### 15.2 Configuración (`AzulSettings`)

```python
AzulSettings(
    AUTH1=...,           # Authorization 1
    AUTH2=...,           # Authorization 2
    MERCHANT_ID=...,     # MID
    ENVIRONMENT=...,     # "prod" o "dev"
    AZUL_CERT=...,       # Contenido PEM del certificado
    AZUL_KEY=...,        # Contenido PEM de la clave privada
    CHANNEL="EC",        # E-Commerce
)
```

### 15.3 Operaciones disponibles

| Método PyAzul | Descripción |
|---------------|-------------|
| `client.sale(data)` | Pago con tarjeta |
| `client.sale_with_token(data)` | Pago con DataVault token |
| `client.post_sale(data)` | Captura post-autorización |
| `client.void(data)` | Anulación de transacción |
| `client.refund(data)` | Reembolso |
| `client.verify_payment(data)` | Verificar estado por CustomOrderId |
| `client.delete_token(data)` | Borrar token de DataVault |
| `client.process_3ds_method(data)` | Procesar 3DS Method notification |
| `client.process_challenge(session_id, challenge_response)` | Procesar CRes del challenge |

### 15.4 Manejo asíncrono en contexto síncrono

Odoo es síncrono; PyAzul es asíncrono. El módulo usa `utils.run_async()`:

```python
def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)
```

Ejemplo de uso:
```python
result = azul_utils.run_async(client.sale(data))
```

### 15.5 Cache del cliente

El cliente PyAzul se cachea por `provider.id` para evitar re-inicialización:

```python
_client_cache = {}
cache_key = f"provider_{provider.id}"
```

### 15.6 Excepciones PyAzul

| Excepción | Cuándo ocurre |
|-----------|---------------|
| `AzulResponseError` | Azul responde con error explícito (e.g., tarjeta declinada) |
| `AzulError` | Error de cliente PyAzul (configuración, red, etc.) |

---

## 16. Códigos de Respuesta y Manejo de Errores

### 16.1 Resultado de transacción

| IsoCode | Resultado | Estado Odoo |
|---------|-----------|-------------|
| `00` | Aprobada | `done` |
| Cualquier otro | Rechazada/Error | `error` o `cancel` |

### 16.2 Mensajes de respuesta almacenados

En transacciones aprobadas: `AuthorizationCode` o `ResponseMessage`
En rechazadas: descripción con IsoCode + ErrorDescription

### 16.3 Errores comunes

| Escenario | Comportamiento |
|-----------|----------------|
| Campos de configuración faltantes | ValidationError al inicializar cliente |
| Tarjeta declinada (`AzulResponseError`) | Mensaje del banco al usuario |
| Error de red/timeout | Transacción queda `pending`, cron la verifica |
| 3DS challenge fallido | `tx._set_error(...)` con mensaje descriptivo |
| Token inválido en DataVault | Error al intentar pago con token |

---

## 17. Seguridad y Credenciales

### 17.1 Almacenamiento

Todas las credenciales sensibles tienen `groups="base.group_system"` — solo administradores del sistema pueden verlas.

Los campos de credenciales usan `password="True"` en las vistas — se muestran como `●●●●●●` en la UI.

### 17.2 Certificados SSL (mTLS)

Los certificados PEM se inyectan como variables de entorno antes de cada request:
```python
os.environ["AZUL_CERT"] = settings.AZUL_CERT
os.environ["AZUL_KEY"] = settings.AZUL_KEY
```

### 17.3 No almacenamiento PCI

El módulo **nunca almacena** datos completos de tarjeta. Los datos solo viajan en memoria desde el formulario hasta el primer request a Azul. El `DataVaultToken` que se persiste es un identificador opaco sin valor si se extrae fuera del contexto de Azul.

### 17.4 CSRF

El endpoint `/payment/azul_webservices/process` usa `csrf=True`.
El endpoint `/payment/azul_webservices/3ds_return` usa `csrf=False` porque recibe callbacks externos de Azul/ACS.

---

## 18. Métodos de Pago Soportados

```python
DEFAULT_PAYMENT_METHOD_CODES = [
    "card",        # Genérico
    "visa",
    "mastercard",
    "amex",
    "discover",
]
```

### Mapping de marcas Azul → Odoo

| Respuesta Azul (`DataVaultBrand`) | Código Odoo |
|-----------------------------------|-------------|
| `visa` | `visa` |
| `mastercard`, `mc`, `master card` | `mastercard` |
| `amex`, `american express` | `amex` |
| `discover` | `discover` |
| `diners`, `diners club` | `diners` |
| `jcb` | `jcb` |
| `unionpay`, `union pay` | `unionpay` |
| `maestro` | `maestro` |

---

## 19. Glosario de Términos

| Término | Definición |
|---------|------------|
| **3DS / 3D Secure** | Protocolo de autenticación adicional para pagos online. Involucra al banco emisor para verificar la identidad del portador |
| **3DS2** | Versión 2 del protocolo 3D Secure. Más fluido, soporta frictionless flow y biometría |
| **ACS** | Access Control Server. Servidor del banco emisor que ejecuta la autenticación 3DS |
| **AuthorizationCode** | Código de autorización bancaria asignado a una transacción aprobada |
| **Azul** | Procesador de pagos dominicano. Opera `pagos.azul.com.do` |
| **AzulOrderId** | ID interno de Azul para una transacción (distinto al `CustomOrderId` del comercio) |
| **Channel EC** | E-Commerce. Canal de integración para tiendas online |
| **Challenge** | Paso de verificación activa del usuario en 3DS (OTP, biometría, pregunta secreta) |
| **CReq / CRes** | Challenge Request / Challenge Response. Mensajes entre el comercio y el ACS durante el challenge |
| **CustomOrderId** | Referencia del comercio enviada a Azul. En Odoo es `payment.transaction.reference` |
| **DataVault** | Sistema de tokenización de Azul. Almacena tarjetas de forma segura y entrega tokens |
| **DataVaultToken** | Token opaco que representa una tarjeta guardada en DataVault |
| **Frictionless** | Flujo 3DS donde el banco aprueba automáticamente sin requerir acción del usuario |
| **IsoCode** | Código de respuesta ISO 8583. `00` = aprobado |
| **MID** | Merchant Identification Number. Identificador único del comercio ante Azul |
| **mTLS** | Mutual TLS. Autenticación bidireccional donde el cliente también presenta certificado |
| **PEM** | Privacy Enhanced Mail. Formato de codificación para certificados y claves SSL |
| **PyAzul** | Librería Python asíncrona que abstrae la API de Azul WebServices |
| **RRN** | Retrieval Reference Number. Número de referencia de la red de tarjetas |
| **TermURL** | URL del comercio donde el ACS redirige al usuario tras el challenge 3DS |
| **Tokenización** | Proceso de reemplazar datos sensibles (número de tarjeta) por un token no sensible |
| **Void** | Anulación de una transacción autorizada antes de que sea capturada/liquidada |
| **WebServices API** | API REST de Azul para integración directa (inline), sin redirigir al usuario |

---

*Documentación generada para el módulo `payment_azul_webservices` v17.0.1.1.1*
*Desarrollado por INDEXA SRL — Progressa Group*
