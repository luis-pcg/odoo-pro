# Generador masivo de e-CF de prueba en modo Certificación

**Módulo afectado:** `l10n_do_ecf_invoicing` (19.0.1.0.11)
**Fecha:** 2026-09-16
**Estado:** propuesta / pendiente de decisión
**Plan de ejecución acordado:** ver `plan_implementacion.md` (opción B, sin BD dedicada, dentro de `l10n_do_ecf_invoicing`)

---

## 1. Objetivo

Que un usuario en entorno **Certificación (`CerteCF`)** pueda generar de forma masiva y
automatizada los comprobantes de prueba exigidos por DGII, por cada tipo de e-CF,
con control del nivel de automatización (borrador / validar+firmar / enviar) y
pudiendo **re-ejecutar** el proceso cuando DGII rechaza o devuelve documentos.

---

## 2. Lo que ya existe en el código (base sobre la que se construye)

| Pieza | Ubicación | Nota |
|---|---|---|
| Entorno del servicio (`TesteCF` / `CerteCF` / `eCF`) | `l10n_do_ecf_invoicing/models/res_company.py:18` | campo `l10n_do_ecf_service_env` |
| Selector de entorno en Ajustes | `l10n_do_ecf_invoicing/views/res_config_settings_views.xml:31` | hoy con `groups="base.group_no_one"` (solo modo desarrollador) |
| Botón que abre una acción desde Ajustes | `l10n_do_ecf_invoicing/models/res_config_settings.py:31` (`l10n_do_show_ecf_doc_types`) | **precedente exacto** del patrón "botón en Ajustes → act_window" |
| Firma al validar | `account_move.py:1239` (`_post`) → `l10n_do_generate_sign_ecf()` | validar ya firma y deja estado `signed_pending` |
| Envío a DGII | `account_move.py:1365` (`l10n_do_signed_pending`) | lo llama el cron `l10n_do_ecf_send_pending` |
| Consulta de estado | `account_move.py:1480` / `:1519` | crons cada 15 min |
| Caso especial Certificación | `account_move.py:1215` | en `CerteCF`, E32 < 250.000 genera **XML adicional** en `l10n_do_ecf_cert_file` (el que se sube al portal DGII) |
| Tipo 41 no se firma al validar | `account_move.py:1164` (`_do_immediate_sign`) | excepción que el generador debe contemplar |
| Tipos de e-CF habilitados por diario | `models/l10n_do_account_journal_document_type.py:6` (`l10n_do_enable_ecf`) | filtro natural de "qué tipos puede emitir esta empresa" |
| Tipos permitidos según tipo de contribuyente | `l10n_do_accounting/models/account_journal.py:58` (`_get_l10n_do_ncf_types_data`) | define qué partner sirve para cada tipo |
| Rangos de secuencia NCF | `l10n_do_document_pools/models/journal_document_type.py:52` (`sequence_start`/`sequence_end`) | permite cargar el rango que DGII asigna para el set de pruebas |

### Restricciones que condicionan el diseño (importantes)

1. **Constraint de entorno**: `res_company.py:69` impide pasar a `eCF` (Producción) si ya
   existen facturas con timbre emitidas en otro entorno. **Certificar en la misma BD de
   producción deja la empresa bloqueada para pasar a Producción.**
   → O se certifica en BD/empresa dedicada, o hay que relajar el constraint para ignorar
   documentos marcados como "de certificación".
2. **Contaminación fiscal**: los documentos de prueba son `account.move` reales: entran en
   606/607/608, IT-1 y libro mayor. Requiere marcado + exclusión, o empresa/BD aparte.
3. **Partner por tipo**: `_get_journal_ncf_types` valida `l10n_do_dgii_tax_payer_type`; sin
   partners correctos (taxpayer, non_payer, special, governmental, foreigner) los tipos
   44/45/46/47 no se pueden emitir.
4. **RNC**: `l10n_do_rnc_validation` valida el RNC → usar los RNC del set de pruebas DGII,
   no valores inventados.
5. **Tipos de compra**: 41, 43 y 47 son documentos **de compra** (emitidos por el comprador);
   31/32/33/34/44/45/46 son de venta. El generador necesita diario de compra y de venta.
6. **Consumo de secuencia NCF**: ver §2.1. Es la restricción más dura del diseño y
   **un diario dedicado no la resuelve**.

### 2.1 Impacto en las secuencias NCF

El NCF **no** sale de un `ir.sequence` por diario. `l10n_do_accounting/models/account_move.py:276`
(`_get_last_sequence_domain`) elimina a propósito el filtro por diario:

```python
where_string = where_string.replace("journal_id = %(journal_id)s AND", "")
where_string += " AND l10n_latam_document_type_id = %(l10n_latam_document_type_id)s"
where_string += " AND company_id = ANY(%(company_ids)s)"
where_string += " AND COALESCE(l10n_latam_manual_document_number, FALSE) = %(l10n_do_manual_number)s"
```

El talonario es **por tipo de documento + grupo de empresas** (padre + hijas), y el siguiente
número sale del último `account.move` posteado con ese tipo. Consecuencias:

- Un diario "Certificación" **comparte numeración** con el diario real de ventas.
- El número **no se recupera**: `_deduce_sequence_number_reset` devuelve `"never"`
  (`account_move.py:298`); cancelar un e-CF rechazado por DGII deja el hueco consumido.
- Con `l10n_do_document_pools` instalado, las pruebas además **consumen el rango autorizado**:
  `_l10n_do_pool_moves_domain` (`l10n_do_document_pools/models/journal_document_type.py:91`)
  cuenta por tipo de documento y `company_id child_of root`, sin filtrar diario a propósito.
- La numeración manual (`l10n_latam_manual_document_number`) sí abre talonario aparte, pero
  `_post` (`l10n_do_ecf_invoicing/models/account_move.py:1239`) excluye esos documentos de la
  firma → no se emite e-CF. **No es escapatoria.**

| Opción de aislamiento | ¿Aísla numeración? | Nota |
|---|---|---|
| **BD dedicada** (copia de producción, se descarta al terminar) | ✅ total | También esquiva el constraint de entorno (`res_company.py:69`). **Recomendada.** |
| Empresa nueva sin relación padre/hijo | ✅ | Frágil: si se cuelga del mismo padre, el aislamiento desaparece. Duplica RNC y certificado. |
| Diario dedicado | ❌ | El dominio ignora `journal_id`. |
| Numeración manual | ❌ | Rompe la emisión de e-CF. |
| Misma empresa, aceptar el consumo | ⚠️ | Solo si el contribuyente **aún no emite e-CF en producción** (contador virgen). |

Matiz importante del caso real: la certificación ocurre **antes** de emitir e-CF en producción,
así que los contadores E31/E32… suelen estar en cero. El daño no es "me robó números de
facturas reales", es que **producción arrancaría en el siguiente número de las pruebas** en vez
del rango que DGII autorice. Eso se fija con `l10n_do_enable_first_sequence`
(`account_move.py:545`), que permite escribir el NCF inicial **solo mientras no exista ningún
documento posteado de ese tipo** — condición que las pruebas destruyen. Por eso la BD dedicada
es la vía limpia.

---

## 3. Dónde vive el código

**Recomendado: módulo satélite nuevo `l10n_do_ecf_certification`** que depende de
`l10n_do_ecf_invoicing`.

Razones:
- El generador de data de prueba **no debe viajar a producción**; se instala para certificar
  y se desinstala después (se lleva sus modelos y su menú).
- Evita ensuciar el módulo de facturación con lógica de pruebas y campos de uso temporal.
- Permite iterar rápido sin tocar la firma/envío (código crítico ya certificado).

Alternativa: dentro de `l10n_do_ecf_invoicing` detrás de un grupo. Más simple de desplegar,
pero deja el generador (y su menú) presente en producción para siempre.

---

## 4. Propuestas

### Propuesta A — Solo wizard (mínima)

Wizard transitorio `l10n_do.ecf.test.generator.wizard`. El usuario marca tipos, cantidades
y nivel de automatización; el wizard crea/valida/envía y devuelve una acción con los
documentos creados. Los documentos quedan marcados con un booleano
`l10n_do_is_certification_doc` en `account.move`.

- Re-ejecutar = abrir el wizard otra vez y pedir las cantidades faltantes **a mano**.
- Sin historial: el avance se mira filtrando la lista de facturas por
  "Documentos de certificación" + agrupando por Estado de envío.
- **Esfuerzo: ~1,5 días.** **Riesgo: bajo.**

### Propuesta B — Wizard + "Corrida de certificación" *(recomendada)*

Igual que A, pero el wizard **crea un registro persistente** `l10n_do.ecf.certification.run`
con una línea por tipo de e-CF. La corrida es la pantalla de trabajo del proceso: muestra
por tipo cuántos documentos faltan, cuántos aceptó DGII, cuántos rechazó, y permite
**"Generar faltantes"** tantas veces como haga falta.

```
run
 ├─ name            (CERT/2026/0001)
 ├─ company_id, journal_sale_id, journal_purchase_id
 ├─ state           draft / in_progress / done
 ├─ automation      draft | post | send | send_track
 └─ line_ids  (una por tipo de e-CF)
      ├─ l10n_latam_document_type_id  (E31, E32, …)
      ├─ qty_target        (cuántos exige el set)
      ├─ qty_generated / qty_accepted / qty_pending / qty_refused   (computados)
      ├─ qty_missing       = target - accepted - pending
      ├─ partner_id, product_id, amount, sequence_start (opcional)
      └─ move_ids          (documentos generados por esa línea)
```

- **Re-ejecución nativa**: `qty_missing` recalcula solo al cambiar el estado de envío de los
  documentos (los rechazados por DGII se cancelan automáticamente en `l10n_do_signed_pending`),
  y "Generar faltantes" emite **documentos nuevos con NCF nuevo** (nunca reutiliza secuencia).
- Botones en la corrida: `Generar faltantes`, `Enviar pendientes`, `Actualizar estado en DGII`,
  `Descargar XMLs (zip)` — este último resuelve la entrega del set a DGII, incluido el
  `l10n_do_ecf_cert_file` que ya genera el módulo para E32 < 250k.
- Deja **trazabilidad** del proceso de certificación (auditoría, soporte, repetirlo por cliente).
- **Esfuerzo: ~4-5 días.** **Riesgo: medio-bajo.**

### Propuesta C — B + catálogo de casos de prueba

Añade `l10n_do.ecf.certification.case`: plantillas de caso configurables (líneas, ITBIS 18 /
exento / ISC, propina legal, descuentos, retenciones, moneda extranjera, NC/ND con referencia).
La corrida instancia plantillas en vez de facturas genéricas.

- Permite reproducir **literalmente** el set de pruebas que DGII entrega (que varía por
  contribuyente y por tipo), no solo "N facturas por tipo".
- Los casos se pueden exportar/importar como data → reutilizable en cada certificación de
  cliente sin volver a configurar.
- **Esfuerzo: +3 días sobre B.** **Riesgo: medio** (es donde se concentra la variabilidad DGII).

### Comparación

| | A (wizard) | B (wizard + corrida) | C (B + casos) |
|---|---|---|---|
| Generación masiva por tipo | ✅ | ✅ | ✅ |
| Re-ejecutar tras rechazo | manual | ✅ automático (`qty_missing`) | ✅ |
| Historial/auditoría | ❌ | ✅ | ✅ |
| Descarga de XMLs del set | ❌ | ✅ | ✅ |
| Fidelidad al set real DGII | baja | media | alta |
| Esfuerzo | 1,5 d | 4-5 d | 7-8 d |

**Recomendación: implementar B ahora**, con los modelos preparados para que C sea una
extensión aditiva (la línea de corrida ya lleva `partner_id`/`product_id`/`amount`, que en C
pasan a venir de la plantilla).

---

## 5. Dónde va el botón

Se evaluaron las tres ideas planteadas:

| Ubicación | Veredicto | Motivo |
|---|---|---|
| **Menú propio "Certificación DGII"** en Contabilidad | ✅ **principal** | Es un proceso, no una propiedad de un registro. Descubrible, filtrable por grupo, y desaparece al desinstalar el módulo. |
| **Botón en Ajustes** (sección República Dominicana) | ✅ **secundario** | Es donde el usuario ya configura entorno y certificado; un `btn-link` que abre la misma acción. Precedente idéntico: `l10n_do_show_ecf_doc_types`. |
| **Acción en la lista de facturas** | ⚠️ **solo para reintentos** | Como generador es confuso: los registros seleccionados no son la entrada del proceso. Sí tiene sentido como server action *"Regenerar documentos de certificación"* sobre documentos rechazados seleccionados. |

Visibilidad y seguridad (las tres capas, no solo la vista):

1. Vista: `invisible="l10n_do_ecf_service_env == 'eCF'"` y `country_code != 'DO'`.
2. Menú: `groups="l10n_do_ecf_certification.group_ecf_certification"` (grupo nuevo, implica
   `account.group_account_manager`). Nota: el selector de entorno hoy está en
   `base.group_no_one`, así que el consultor que certifica ya trabaja en modo desarrollador;
   el grupo nuevo evita depender de eso.
3. Código: `raise UserError` si `company.l10n_do_ecf_service_env == 'eCF'` al ejecutar.
   **La guarda de servidor es obligatoria**: sin ella, un cambio de entorno a mitad de la
   corrida generaría comprobantes fiscales reales.

---

## 6. Diseño funcional de la propuesta B

### 6.1 Wizard de creación

Campos:

- **Tipos de e-CF** (`one2many` de líneas): tipo, cantidad, diario, partner, producto, importe,
  (opcional) secuencia inicial. Se precarga con los tipos que tengan `l10n_do_enable_ecf = True`
  en los diarios de la empresa.
- **Nivel de automatización** (`selection`):
  | Valor | Qué hace |
  |---|---|
  | `draft` | Solo crea borradores |
  | `post` | Valida → firma el XML (queda `signed_pending`) |
  | `send` | Valida + `l10n_do_signed_pending()` (envía a DGII) |
  | `send_track` | Lo anterior + consulta de estado (`l10n_do_update_ecf_trackid_status`) |
- **Incluir NC/ND** (`33`/`34`): se generan al final, referenciando facturas ya aceptadas de
  la misma corrida (requisito de DGII: el documento origen debe existir).
- **Ejecución**: *inmediata* o *en segundo plano*. Para lotes grandes, en segundo plano vía
  `ir.cron._trigger()` (nativo, sin depender de `queue_job`, que no está en el stack).

### 6.2 Marcado y aislamiento de los documentos

- Campo `l10n_do_certification_run_id` (m2o a la corrida) en `account.move` → filtro,
  agrupación y exclusión.
- Filtro de sistema en los reportes DGII (606/607/608/IT-1) para excluir
  `l10n_do_certification_run_id != False`. *(Requiere tocar los módulos de reportes: alcance a
  confirmar; ver §8.)*
- Recomendación operativa alternativa y más barata: **certificar en BD o empresa dedicada**,
  y así ni el constraint de `res_company.py:69` ni los reportes son problema.

### 6.3 Partners y productos de prueba

El módulo siembra (si no existen) partners de prueba por tipo de contribuyente requerido:
`taxpayer`, `non_payer`, `special`, `governmental`, `foreigner`, con los RNC del set de pruebas
DGII, y un producto "Producto de certificación e-CF" con ITBIS 18% e impuesto exento.
Todos con `ref = 'ECF-CERT'` para poder limpiarlos al desinstalar.

---

## 7. Mockups de las vistas

### 7.1 Ajustes → Contabilidad → sección República Dominicana

Herencia: `l10n_do_ecf_invoicing.res_config_settings_view_form` (la vista que **crea** el
ancla; heredar la de `l10n_do_accounting` no funcionaría — el ancla no existe ahí).
Posición: `<xpath expr="//button[@name='l10n_do_show_ecf_doc_types']/.." position="after">`.

```
┌ Dominican Republic ────────────────────────────────────────────────┐
│                                                                    │
│  ECF API Version            ( ) V1 (Legacy)   (•) V3 (Fixcal API)  │
│                                                                    │
│  ECF Environment            [ Certification            ▾]          │
│                                                                    │
│  Signing Certificate        [ cert.p12 ] 🗑                         │
│  Certificate Password       [ ••••••••• ]                          │
│                                                                    │
│  → Manage ECF Document Types                                       │
│                                                                    │
│  ╔══════════════════════════════════════════════════════════════╗  │  ← NUEVO
│  ║ ⚠ Entorno de Certificación activo                            ║  │  invisible si
│  ║   Puede generar el set de comprobantes de prueba de DGII.    ║  │  env != CerteCF
│  ║   → Generar set de pruebas DGII                              ║  │
│  ╚══════════════════════════════════════════════════════════════╝  │
└────────────────────────────────────────────────────────────────────┘
```

### 7.2 Menú

```
Contabilidad
 ├─ Tablero
 ├─ Clientes
 ├─ Proveedores
 ├─ Contabilidad
 ├─ Informes
 ├─ Certificación DGII          ← NUEVO (solo si env = CerteCF y grupo certificación)
 │   ├─ Corridas de certificación
 │   └─ Generar set de pruebas
 └─ Configuración
```

### 7.3 Wizard "Generar set de pruebas DGII"

```
┌ Generar set de pruebas DGII ───────────────────────────────────── ✕ ┐
│                                                                     │
│  Empresa            [ Mi Empresa SRL          ]  Entorno: CerteCF   │
│  Diario de venta    [ Facturas de cliente  ▾ ]                      │
│  Diario de compra   [ Facturas de proveedor ▾]                      │
│                                                                     │
│  Nivel de automatización                                            │
│    ( ) Solo crear borradores                                        │
│    ( ) Validar y firmar (no enviar a DGII)                          │
│    (•) Validar, firmar y enviar a DGII                              │
│    ( ) Enviar y consultar estado hasta respuesta                    │
│                                                                     │
│  ☑ Incluir notas de crédito (E34) y débito (E33) sobre las          │
│    facturas aceptadas de esta corrida                               │
│  ☐ Ejecutar en segundo plano                                        │
│                                                                     │
│  Tipos a generar                                                    │
│  ┌──────┬──────────────────────────┬─────┬───────────┬───────────┐  │
│  │ Tipo │ Descripción              │ Cant│ Cliente   │ Importe   │  │
│  ├──────┼──────────────────────────┼─────┼───────────┼───────────┤  │
│  │ ☑E31 │ Crédito Fiscal           │  5  │ CERT-TAX  │  10,000.00│  │
│  │ ☑E32 │ Consumo                  │ 10  │ CERT-CONS │   1,500.00│  │
│  │ ☑E33 │ Nota de Débito           │  2  │ CERT-TAX  │     500.00│  │
│  │ ☑E34 │ Nota de Crédito          │  2  │ CERT-TAX  │     500.00│  │
│  │ ☑E41 │ Compras                  │  3  │ CERT-INF  │   2,000.00│  │
│  │ ☑E43 │ Gasto Menor              │  2  │ CERT-INF  │     800.00│  │
│  │ ☑E44 │ Régimen Especial         │  2  │ CERT-ESP  │   3,000.00│  │
│  │ ☑E45 │ Gubernamental            │  2  │ CERT-GOB  │   4,000.00│  │
│  │ ☐E46 │ Exportación              │  0  │ CERT-EXT  │   5,000.00│  │
│  │ ☐E47 │ Pago al Exterior         │  0  │ CERT-EXT  │   1,000.00│  │
│  └──────┴──────────────────────────┴─────┴───────────┴───────────┘  │
│                                                                     │
│                                   [ Cancelar ]  [ Generar ]         │
└─────────────────────────────────────────────────────────────────────┘
```

Solo aparecen los tipos con `l10n_do_enable_ecf = True` en los diarios de la empresa; el
resto ni se listan (evita generar comprobantes que la empresa no está autorizada a emitir).

### 7.4 Corrida de certificación (modelo persistente — propuesta B)

```
┌ CERT/2026/0001 ─────────────────────────────────────────────────────┐
│ [Generar faltantes] [Enviar pendientes] [Actualizar estado DGII]    │
│ [Descargar XMLs]                          Borrador → En curso → ✔   │
│                                                                     │
│  Empresa   Mi Empresa SRL        Entorno   CerteCF                  │
│  Creado    16/09/2026 10:12      Usuario   Luis Fernández           │
│                                                                     │
│  ┌──────┬──────┬─────────┬──────────┬───────────┬──────────┬─────┐  │
│  │ Tipo │ Meta │ Generado│ Aceptado │ Pendiente │ Rechazado│Falta│  │
│  ├──────┼──────┼─────────┼──────────┼───────────┼──────────┼─────┤  │
│  │ E31  │   5  │    5    │    5     │     0     │    0     │  0  │  │
│  │ E32  │  10  │   10    │    8     │     1     │    1     │  1  │  │ ← re-ejecutable
│  │ E33  │   2  │    2    │    2     │     0     │    0     │  0  │  │
│  │ E41  │   3  │    3    │    0     │     3     │    0     │  0  │  │
│  └──────┴──────┴─────────┴──────────┴───────────┴──────────┴─────┘  │
│                                                                     │
│  📎 Documentos generados (20)   Registro (chatter con respuestas    │
│                                  de DGII por documento)             │
└─────────────────────────────────────────────────────────────────────┘
```

Las columnas se calculan desde `l10n_do_ecf_send_state` de los documentos de cada línea:
`delivered_accepted`/`conditionally_accepted` → Aceptado; `signed_pending`/`delivered_pending`
→ Pendiente; `delivered_refused`/`not_sent` → Rechazado.

### 7.5 Lista de facturas (filtro + acción de reintento)

```
Facturas de cliente                                   [Filtros ▾] [Agrupar por ▾]
                                                       ├ …
  ☑ 3 seleccionadas   [Acciones ▾]                     └ Documentos de certificación  ← NUEVO
                         ├ …                              (Agrupar por ▸ Estado de envío, ya existe)
                         └ Regenerar documentos de certificación   ← NUEVO (server action)

┌───┬────────────┬───────────────┬──────────────┬─────────────────────┬──────────┐
│ ☑ │ Número     │ Cliente       │ Tipo doc.    │ Estado de envío     │ Total    │
├───┼────────────┼───────────────┼──────────────┼─────────────────────┼──────────┤
│ ☑ │ E320000012 │ CERT-CONS     │ E32 Consumo  │ 🔴 Delivered refused│  1,500.00│
│ ☐ │ E310000005 │ CERT-TAX      │ E31 Crédito  │ 🟢 Accepted         │ 10,000.00│
└───┴────────────┴───────────────┴──────────────┴─────────────────────┴──────────┘
```

La columna *Estado de envío* ya existe en la vista lista (`views/account_views.xml:80`,
`optional="hide"`); la corrida la deja visible por defecto en su acción.

---

## 8. Plan de implementación (propuesta B)

| Fase | Contenido | Días |
|---|---|---|
| 1 | Módulo `l10n_do_ecf_certification`: modelos `run` + `run.line`, grupo de seguridad, guarda de entorno | 1,0 |
| 2 | Generador: partners/producto de prueba, construcción de facturas por tipo (venta y compra), NC/ND con referencia | 1,5 |
| 3 | Niveles de automatización + ejecución en segundo plano (`ir.cron._trigger`) | 0,5 |
| 4 | Vistas: menú, wizard, formulario de corrida, botón en Ajustes, server action de reintento, filtro en lista | 1,0 |
| 5 | Descarga de XMLs en zip (incluye `l10n_do_ecf_cert_file` de E32) | 0,5 |
| 6 | Tests (`TransactionCase` con `l10n_do_active_test` para no golpear DGII) + traducción es_DO generada con `odoo i18n export` | 1,0 |
| | **Total** | **5,5** |

**Fuera del alcance propuesto (a decidir):** excluir los documentos de certificación de
606/607/608 e IT-1 y relajar el constraint de `res_company.py:69`. Ambos obligan a tocar
módulos de producción. Si la certificación se hace en BD/empresa dedicada, no hacen falta.

---

## 9. Decisiones pendientes

1. **¿BD dedicada o misma BD?** (ver §2.1) Determina si hace falta el trabajo extra de
   exclusión en reportes, el cambio en el constraint de entorno y cómo se recupera la
   secuencia inicial de producción tras certificar. **Es la decisión que más condiciona el
   alcance.**
2. **¿Cantidades libres o set DGII fijo?** Si se quiere fidelidad al set oficial (casos con
   ITBIS exento, ISC, propina, retenciones, moneda extranjera), hay que ir a la propuesta C.
3. **¿Módulo satélite o dentro de `l10n_do_ecf_invoicing`?** Recomendado satélite.
4. **¿Quién ejecuta?** Consultor Progressa (grupo restringido) o el propio cliente
   (más visibilidad, más riesgo).
