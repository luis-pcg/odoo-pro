# Spec de implementación: `l10n_do_hr_payroll_sync`

Sincronización centralizada de parámetros legales de nómina RD desde PROGRESSA (maestro) hacia N instancias Odoo 17 cliente.

Base: `docs/Odoo Architecture Design Payroll.pdf`. Este spec **diverge del PDF en tres puntos** (scope, transporte, identidad de registros); las divergencias están justificadas en §2 y §3 contra el código real de `l10n_do_hr_payroll` 17.0.1.1.3.

---

## 1. Objetivo

Cuando la DGII o la TSS publica un cambio de parámetro (escala ISR anual, monto por dependiente, porcentajes de riesgo laboral), hoy hay que editarlo a mano en cada base cliente o publicar release del módulo y correr `-u` en cada instancia. Este módulo lo distribuye desde una sola instancia.

**No es** un sincronizador de nómina. No viaja ningún dato de empleados, contratos, sueldos ni nóminas.

---

## 2. Decisión de scope: qué se sincroniza y qué NO

Hallazgo del código que cambia el diseño del PDF:

`l10n_do_hr_payroll/data/hr_salary_rule.xml` **no tiene `noupdate`** (verificado: `grep -c noupdate` → 0). Las reglas salariales ya se redistribuyen hoy en cada `-u l10n_do_hr_payroll`. En cambio `l10n_do_hr_retention_scale.xml` y `l10n_do_occupational_risk_type.xml` **sí tienen `noupdate="1"`**: nunca se actualizan solas.

Consecuencia: **ya existen dos canales de distribución** y hay que asignar cada modelo a uno solo.

| Canal | Mecanismo | Apropiado para |
|---|---|---|
| **A — git** | data XML sin `noupdate` + `-u modulo` | Registros que contienen código Python o refs a otros XMLIDs. Versionados, code-reviewed |
| **B — sync API** | este módulo | Parámetros numéricos puros que cambian por calendario legal, sin código |

### 2.1 Tabla de asignación

| Modelo | Canal | Razón |
|---|---|---|
| `l10n.do.hr.retention.scale` | **B (sync)** | Escalas ISR. Cambian cada año fiscal. `noupdate=1` hoy → no llegan solas. **Caso de uso principal** |
| `l10n.do.occupational.risk.type` | **B (sync)** | `name` + `percentage`. Global, sin `company_id`, sin código. `noupdate=1` |
| `res.company.l10n_do_hr_dependent_amount` | **B (sync)** | Monto legal por dependiente. Único campo de `res.company` que es parámetro de ley |
| `hr.salary.rule` | **A (git)** | Contiene `condition_python` y `amount_python_compute`. Sincronizarlo por API = ejecución remota de código en 40 instancias. Además ya se distribuye por `-u`; sincronizarlo crearía doble fuente y el `-u` revertiría lo sincronizado |
| `hr.payroll.structure`, `.structure.type`, `hr.salary.rule.category`, `hr.payslip.input.type` | **A (git)** | Estructura del módulo, no parámetro legal. Cambian con el código |
| `l10n.do.hr.payroll.payment.division` | **NO se sincroniza** | `company_id` **required** + `UNIQUE(company_id, name, payment_division)`. Es config por compañía, no maestro. Requeriría mapeo de compañías cross-instancia sin ganancia real |
| `l10n.do.hr.payroll.days.division` | **NO se sincroniza** | Igual que arriba: `UNIQUE(company_id, name)` |
| `res.company.l10n_do_ngo`, `l10n_do_occupational_risk_type_id`, `l10n_do_last_payroll_day` | **NO se sincroniza** | Config propia de cada cliente. Pisarla desde el maestro es un bug, no una feature |

> **Divergencia vs PDF.** El PDF §4.4 lista los 31 items incluyendo `hr.salary.rule`, las divisions y todos los campos de `res.company`. Sincronizar campos python es un vector de RCE hacia todos los clientes; sincronizar las divisions y la config por-cliente de `res.company` pisa configuración legítima del cliente. Scope reducido a 3 items.

### 2.2 Regla dura de seguridad

El allowlist de modelos y campos vive **hardcodeado en `models/sync_registry.py`**, no en un modelo de base de datos ni en `ir.config_parameter`. Si el allowlist fuera configurable, comprometer el maestro (o un admin del maestro) permitiría inyectar `amount_python_compute` arbitrario y obtener ejecución de código en todas las instancias cliente. El allowlist se cambia con un release del módulo, revisado en PR.

El cliente valida el allowlist **de su lado** al recibir. No confía en que el maestro mande solo lo permitido.

---

## 3. Arquitectura

### 3.1 Divergencia: pull con revisión, no push con cola

El PDF recomienda push + message queue (RabbitMQ/Celery/OCA `queue_job`) + dead letter queue + ACK/NACK. Eso resuelve entrega confiable a clientes que pueden estar caídos.

Un contador de revisión monotónico resuelve lo mismo sin infraestructura:

- El maestro mantiene `revision` incremental. Cada publicación de cambios crea una revisión nueva.
- Cada cliente guarda `last_revision` aplicada.
- El cron del cliente pregunta `GET /diff?since=<last_revision>` y aplica lo que falte.

Propiedades que salen gratis: idempotencia, recuperación de clientes offline (piden desde su revisión al volver), sin cola, sin DLQ, sin protocolo ACK, sin reintentos con backoff, y clientes detrás de firewall funcionan sin exponer puerto.

**Push queda como optimización opcional** ("poke"): el maestro hace POST vacío a `/poke` del cliente para que corra su pull ya mismo. Si el poke falla, el cron lo recoge igual. El poke no transporta datos, así que no necesita entrega garantizada.

```
┌──────────────────────────────────────────┐
│ PROGRESSA (maestro, Odoo 17)             │
│  l10n_do_hr_payroll  (datos maestros)    │
│  l10n_do_hr_payroll_sync                 │
│    · sync.revision  (contador + payload) │
│    · sync.client    (registro clientes)  │
│    · sync.log       (auditoría)          │
│    · controller  /l10n_do_payroll_sync/* │
└──────────────────────────────────────────┘
         ▲ GET /diff?since=N   (cliente pregunta — modo normal)
         │ POST /ack           (cliente reporta resultado)
         │
   ┌─────┴──────┬────────────┬────────────┐
   │            │            │            │
Cliente 1    Cliente 2    Cliente N    (cron c/6h + poke opcional)
```

### 3.2 Divergencia: identidad de registros por XMLID

El PDF no define cómo el cliente sabe a qué registro local corresponde uno remoto. Los `id` de base no coinciden entre instancias.

Todos los registros maestros ya tienen XMLID (`l10n_do_hr_payroll.l10n_do_hr_retention_scale_1`, `.risk_type_1`, …). **El XMLID completo es la clave de sincronización.** El cliente resuelve con `env.ref(xmlid, raise_if_not_found=False)`:

- Encontrado → `write()` de los campos permitidos.
- No encontrado → `create()` + insertar `ir.model.data` con ese mismo XMLID y `noupdate=True`.

Registros maestros creados a mano (sin XMLID) se les asigna uno al publicar, bajo el módulo `l10n_do_hr_payroll_sync` (ej. `l10n_do_hr_payroll_sync.scale_2027_1`).

### 3.3 Prerrequisito: vigencia temporal de las escalas ISR

`l10n.do.hr.retention.scale` no tiene campo de fecha. `_compute_annual_retention` busca sobre todas las escalas existentes. Si el sync reemplaza las escalas de 2026 por las de 2027, recalcular una nómina de 2026 daría el ISR de 2027.

Dos salidas:

- **MVP (recomendada).** Sync reemplaza el set completo de forma atómica. Se acepta que las nóminas viejas no se pueden recalcular con la escala de su año — ya están validadas y contabilizadas con los montos guardados. Documentarlo. Bloquear el sync si hay nóminas en borrador (§5.4).
- **Completa.** Agregar `date_from`/`date_to` a `l10n.do.hr.retention.scale` y filtrar en `_compute_annual_retention` y `_get_annual_exempt_amount`. Es un cambio en `l10n_do_hr_payroll`, no en este módulo. Fuera del MVP.

---

## 4. Modelos

Módulo: `l10n_do_hr_payroll_sync`. Un solo módulo, dos roles según `ir.config_parameter` `l10n_do_payroll_sync.role` ∈ `master` | `client`. Los menús y modelos del rol contrario se ocultan con grupo.

### Lado maestro

```
l10n.do.payroll.sync.client
  name              Char      required
  base_url          Char      required   # https://cliente.dominio.do
  api_key           Char      required   # generado, groups="base.group_system"
  active            Boolean   default True
  last_revision     Integer   readonly   # última revisión que el cliente confirmó
  last_contact      Datetime  readonly
  state             Selection [ok, behind, error, never]  compute
  log_ids           One2many  → sync.log

l10n.do.payroll.sync.revision
  number            Integer   readonly, secuencia
  publish_date      Datetime  readonly
  user_id           Many2one  res.users  readonly
  note              Text                  # "Escalas ISR 2027, Norma DGII 05-2026"
  payload           Text      readonly    # JSON congelado (ver §6.1)
  payload_hash      Char      readonly    # sha256 del payload
  state             Selection [draft, published]
```

`payload` se congela al publicar. Una revisión publicada es inmutable — todos los clientes reciben exactamente los mismos bytes, y `payload_hash` lo prueba.

### Lado cliente

```
ir.config_parameter:
  l10n_do_payroll_sync.role         = 'client'
  l10n_do_payroll_sync.master_url   = 'https://progressa.dominio.do'
  l10n_do_payroll_sync.api_key      = '<secreto>'
  l10n_do_payroll_sync.last_revision = '17'
```

### Ambos lados

```
l10n.do.payroll.sync.log
  client_id         Many2one  sync.client   # solo maestro
  revision_number   Integer
  direction         Selection [out, in]
  model             Char
  xmlid             Char
  operation         Selection [create, write, skip]
  state             Selection [done, error]
  message           Text
  create_date       Datetime
```

`sync.log` hereda `mail.thread` en el maestro para que los errores generen actividad al responsable.

---

## 5. Endpoints

Prefijo `/l10n_do_payroll_sync`. Todos `type="json"`, `auth="none"`, `csrf=False`, autenticación manual en decorador propio.

### 5.1 Autenticación

Header `X-Payroll-Sync-Key: <api_key>`.

- Comparación con `hmac.compare_digest` — nunca `==` (timing attack).
- Rechazo con HTTP 401 y cuerpo genérico. No distinguir "cliente no existe" de "key inválida".
- **HTTPS obligatorio.** El controller rechaza si `request.httprequest.scheme != 'https'`, salvo que `ir.config_parameter` `l10n_do_payroll_sync.allow_http` esté en `1` (solo para desarrollo local; documentar que nunca va en producción).
- Rate limit: máx. 60 req/min por api_key, contador en `ir.config_parameter` o cache en memoria. Exceso → HTTP 429.
- Cada request autenticada actualiza `last_contact` del cliente.

La api_key se genera con `secrets.token_urlsafe(32)`, se muestra **una sola vez** al crearla y se guarda hasheada (`hashlib.sha256`) en el maestro. Campo con `groups="base.group_system"`.

### 5.2 `GET /diff` — maestro

Request: `{"since": 16}`

Response:
```json
{
  "revision": 18,
  "since": 16,
  "records": [
    {
      "model": "l10n.do.hr.retention.scale",
      "xmlid": "l10n_do_hr_payroll.l10n_do_hr_retention_scale_1",
      "operation": "write",
      "values": {"name": "...", "sequence": 1, "exempt": true,
                 "percent": 0.0, "base_amount": 0.0,
                 "top_amount": 435000.0, "fixed_amount": 0.0}
    }
  ],
  "deletions": ["l10n_do_hr_payroll_sync.scale_2026_5"],
  "hash": "sha256:..."
}
```

Devuelve el **estado consolidado** de los modelos sincronizados a la revisión actual, no el delta acumulado revisión por revisión. Un cliente 10 revisiones atrás y uno 1 revisión atrás aplican el mismo payload final — menos casos que probar, y el resultado es idempotente.

### 5.3 `POST /ack` — maestro

Request: `{"revision": 18, "state": "done", "applied": 6, "errors": []}`
→ actualiza `last_revision`, `last_contact`, crea `sync.log`.

### 5.4 `POST /apply` — cliente (solo si se usa poke)

Sin cuerpo de datos. Dispara el pull del cliente inmediatamente. Autenticado igual. Responde `{"queued": true}`.

### 5.5 Pre-chequeos del cliente antes de aplicar

Aborta y registra en `sync.log` si:

1. Existen `hr.payslip` en estado `draft` o `verify` (recalcularían con parámetros nuevos a mitad de proceso).
2. El allowlist local rechaza algún modelo o campo del payload.
3. El `hash` recibido no coincide con el sha256 recalculado sobre `records`.

---

## 6. Aplicación en el cliente

### 6.1 Serialización

Solo tipos JSON planos. Sin `Many2one` en el payload MVP (los 3 modelos sincronizados no tienen ninguno que cruce). Si en el futuro hace falta, se serializa como XMLID del destino, nunca como id numérico.

`Float` se serializa con `repr()` para no perder precisión en `base_amount` (416220.01).

### 6.2 Transacción

Todo el batch en una sola transacción. Cualquier error → rollback completo, `last_revision` no avanza, `sync.log` con el traceback. Nunca estado parcialmente aplicado.

```python
with self.env.cr.savepoint():
    for rec in payload["records"]:
        self._apply_record(rec)
```

### 6.3 Aplicación

```python
def _apply_record(self, rec):
    model, xmlid = rec["model"], rec["xmlid"]
    self._check_allowlist(model, rec["values"])          # valida del lado cliente
    target = self.env.ref(xmlid, raise_if_not_found=False)
    if target:
        target.sudo().write(rec["values"])
        op = "write"
    else:
        target = self.env[model].sudo().create(rec["values"])
        self.env["ir.model.data"].sudo().create({
            "module": xmlid.split(".")[0],
            "name": xmlid.split(".")[1],
            "model": model,
            "res_id": target.id,
            "noupdate": True,
        })
        op = "create"
    self._log(model, xmlid, op)
```

`sudo()` es necesario: `l10n.do.hr.retention.scale.write()` bloquea `name` y `sequence` a quien no sea `base.group_system` (ver `l10n_do_hr_retention_scale.py:18-25`). El cron corre con un usuario de servicio dedicado, no con `base.user_root` interactivo.

`noupdate=True` en el `ir.model.data` creado evita que un `-u l10n_do_hr_payroll` posterior pise lo sincronizado.

### 6.4 Borrados

`deletions` desactiva o borra por XMLID. Para escalas ISR, borrar sobrante es correcto (el set de escalas es cerrado). Si el `unlink` falla por FK, se registra el error y **no** se aborta el batch — el borrado es best-effort, las escrituras no.

### 6.5 Cron

```xml
<record id="ir_cron_payroll_sync_pull" model="ir.cron">
    <field name="name">Payroll Sync: pull parameters</field>
    <field name="interval_number">6</field>
    <field name="interval_type">hours</field>
    <field name="active" eval="False"/>   <!-- se activa al configurar rol client -->
</record>
```

---

## 7. Seguridad — resumen

| Riesgo | Mitigación |
|---|---|
| Campos con código Python cruzando instancias (RCE) | Allowlist hardcodeado en el módulo, sin `hr.salary.rule`. Validado en ambos extremos |
| Maestro comprometido → 40 clientes comprometidos | Sin campos ejecutables en el allowlist, el peor caso es corrupción de parámetros numéricos: detectable, auditable en `sync.log`, reversible |
| Credenciales en tránsito | HTTPS obligatorio en el controller. `api_key` hasheada en reposo, `compare_digest` al validar |
| Cliente malicioso pidiendo diffs | Todos los clientes reciben el mismo payload público de parámetros legales. No hay datos de otros clientes en la respuesta |
| Enumeración de api_keys | Rate limit 60/min + 401 genérico |
| Cambio de parámetro a mitad de nómina | Pre-chequeo de payslips en draft/verify aborta el sync |

Sin `ir.rule` cross-cliente necesaria: el maestro no expone datos por cliente.

---

## 8. Estructura del módulo

```
l10n_do_hr_payroll_sync/
├── __manifest__.py            depends: ["l10n_do_hr_payroll"]
├── controllers/
│   ├── __init__.py
│   ├── auth.py                decorador de autenticación + rate limit
│   └── main.py                /diff, /ack, /apply
├── models/
│   ├── sync_registry.py       ALLOWLIST (hardcodeado)
│   ├── sync_client.py         maestro
│   ├── sync_revision.py       maestro, publicación + payload
│   ├── sync_log.py            ambos
│   └── res_config_settings.py rol, master_url, api_key
├── data/ir_cron.xml
├── security/
│   ├── payroll_sync_security.xml   grupos master/client
│   └── ir.model.access.csv
├── views/                     sync_client, sync_revision, sync_log, settings
├── tests/
└── readme/
```

`sync_registry.py`:
```python
ALLOWLIST = {
    "l10n.do.hr.retention.scale": [
        "name", "sequence", "exempt", "percent",
        "base_amount", "top_amount", "fixed_amount",
    ],
    "l10n.do.occupational.risk.type": ["name", "percentage"],
    "res.company": ["l10n_do_hr_dependent_amount"],
}
```

`res.company` requiere resolución especial: el cliente lo aplica a **todas** sus compañías con `l10n_do_hr_payroll` instalado, no por XMLID.

---

## 9. Fases

| Fase | Alcance | Entregable |
|---|---|---|
| **F1** | Modelos, allowlist, `/diff` + `/ack`, cron pull, aplicación por XMLID, `sync.log`. Solo `l10n.do.hr.retention.scale` | Escalas ISR sincronizan. Suficiente para el caso real anual |
| **F2** | `l10n.do.occupational.risk.type` + `res.company.l10n_do_hr_dependent_amount`. Dashboard de clientes con `state`, alertas `mail.thread` sobre clientes atrasados | Operable a escala |
| **F3** | Poke (`/apply`), rollback a revisión anterior desde el maestro | Latencia baja + reversión |
| **F4** *(opcional, solo si el volumen lo pide)* | `date_from`/`date_to` en `l10n.do.hr.retention.scale` (§3.3) | Recálculo histórico correcto |

`queue_job`/RabbitMQ/Celery **no entran en ninguna fase**. El diseño pull-con-revisión no los necesita (§3.1). Si algún día el push con entrega garantizada se vuelve requisito real, se evalúa entonces.

---

## 10. Tests

`tests/`, con `@tagged('post_install', '-at_install')`. Ojo con el patrón roto de otros tests de nómina del repo: usar `@classmethod def setUpClass(cls)`, no `def setUpClass(self)`, y **no** poner el tag `-standard` o nunca corren en CI.

| Test | Verifica |
|---|---|
| `test_apply_creates_missing_record` | XMLID inexistente → create + `ir.model.data` con `noupdate=True` |
| `test_apply_updates_existing_record` | XMLID existente → write, sin duplicar |
| `test_apply_is_idempotent` | Aplicar la misma revisión dos veces no cambia nada la segunda |
| `test_allowlist_rejects_unknown_model` | Payload con `hr.salary.rule` → rechazado por el cliente |
| `test_allowlist_rejects_unknown_field` | Payload con `condition_python` → rechazado |
| `test_rollback_on_partial_failure` | Un registro inválido → ningún cambio persiste, `last_revision` no avanza |
| `test_hash_mismatch_aborts` | Payload manipulado → abortado |
| `test_auth_rejects_bad_key` | 401 |
| `test_auth_rejects_http` | Sin HTTPS y sin `allow_http` → rechazado |
| `test_draft_payslip_blocks_sync` | Nómina en borrador → sync abortado |
| `test_float_precision_preserved` | `base_amount = 416220.01` sobrevive el round-trip JSON |
| `test_isr_computation_after_sync` | `_compute_annual_retention` da el valor correcto con escalas nuevas |

Escenario de integración manual: dos bases (`test_sync_master`, `test_sync_client`), publicar revisión, correr cron del cliente, verificar escalas y `sync.log`.

---

## 11. Riesgos abiertos

1. **Migración inicial.** Los clientes existentes tienen escalas con XMLID de `l10n_do_hr_payroll` y `noupdate=1`. La primera sincronización las va a escribir. Verificar caso por caso que no haya escalas editadas a mano en clientes — el `pre-migrate.py` de 17.0.1.1.2 ya borró las que no tenían XMLID, así que el terreno está parejo.
2. **Nómina en curso.** El pre-chequeo de payslips en draft bloquea el sync; un cliente con borradores permanentes nunca sincronizaría. Necesita alerta al maestro (F2) y override manual.
3. **`res.company` multicompañía.** Un cliente con varias compañías recibe `l10n_do_hr_dependent_amount` para todas. Confirmar con negocio que es lo deseado.
4. **Versión del módulo.** Un cliente en `l10n_do_hr_payroll` 17.0.1.0.x no tiene el campo `fixed_amount`. El `/diff` debe incluir la versión mínima requerida y el cliente abortar si no la cumple.
