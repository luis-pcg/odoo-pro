# Plan de implementación — Generador de comprobantes de certificación

**Módulo:** `l10n_do_ecf_invoicing`
**Fecha:** 2026-09-16
**Alcance:** exactamente el requerimiento. Sin modelos de seguimiento, sin BD dedicada.

---

## 0. Alcance

| Requerimiento | Solución |
|---|---|
| Disponible solo en modo "Certificación" | Guarda en vista (`invisible`) **y** en servidor (`UserError`) |
| Un botón visible | Ajustes (admin) + menú + acción en lista de facturas |
| Ejecutable varias veces | El wizard calcula lo que falta al abrirse, leyendo las facturas ya generadas |
| Levantar un wizard | `l10n_do.ecf.certification.wizard` (transitorio) |
| Elegir qué transacciones crear | Una línea por tipo de e-CF, con casilla y cantidad |
| Elegir nivel de automatización | Borrador / Validar / Enviar |

**Nada persistente nuevo.** Los comprobantes son `account.move` normales; lo único que se añade al
modelo es **un booleano** para reconocerlos.

---

## 1. Qué se crea

### 1.1 `account.move` — un campo

```python
l10n_do_is_certification_doc = fields.Boolean(
    "Documento de certificación",
    copy=False,
    index=True,
    readonly=True,
)
```

Sin lógica añadida a `account.move`. Sirve para tres cosas: filtrar la lista, calcular lo que falta
al reabrir el wizard, y separar la numeración (§5).

### 1.2 `l10n_do.ecf.certification.wizard` — el wizard (transitorio)

```python
_name = "l10n_do.ecf.certification.wizard"
_description = "Generate DGII certification test documents"

company_id          = Many2one("res.company", required, default=lambda self: self.env.company)
journal_sale_id     = Many2one("account.journal", domain="[('type','=','sale'),('l10n_latam_use_documents','=',True)]")
journal_purchase_id = Many2one("account.journal", domain="[('type','=','purchase'),('l10n_latam_use_documents','=',True)]")
invoice_date        = Date(default=fields.Date.context_today)
automation          = Selection([("draft", "Crear borrador"),
                                 ("post",  "Validar (firma el e-CF)"),
                                 ("send",  "Validar y enviar a DGII")], default="send", required=True)
include_notes       = Boolean("Incluir notas de crédito y débito", default=True)
line_ids            = One2many("l10n_do.ecf.certification.wizard.line", "wizard_id")
```

### 1.3 `l10n_do.ecf.certification.wizard.line` — una línea por tipo (transitoria)

```python
wizard_id                   = Many2one(..., required, ondelete="cascade")
l10n_latam_document_type_id = Many2one("l10n.latam.document.type", required, readonly=True)
selected   = Boolean(default=True)
qty        = Integer("Cantidad", default=1)
partner_id = Many2one("res.partner")
product_id = Many2one("product.product")
price_unit = Float(default=1000.0)

# solo informativos, calculados en default_get sobre las facturas ya marcadas
existing_accepted = Integer("Aceptadas", readonly=True)
existing_pending  = Integer("Pendientes", readonly=True)
existing_refused  = Integer("Rechazadas", readonly=True)
```

Ambos son `TransientModel`: los limpia el vacuum de Odoo, no dejan rastro.

---

## 2. Repetibilidad sin modelo de seguimiento

Al abrir el wizard, `default_get` hace **un `read_group`** sobre las facturas ya marcadas:

```python
data = self.env["account.move"].read_group(
    domain=[
        ("l10n_do_is_certification_doc", "=", True),
        ("company_id", "=", self.env.company.id),
    ],
    fields=["id:count"],
    groupby=["l10n_latam_document_type_id", "l10n_do_ecf_send_state"],
    lazy=False,
)
```

Con eso arma cada línea:

- `existing_accepted` ← `delivered_accepted`, `conditionally_accepted`
- `existing_pending` ← `to_send`, `sending`, `signed_pending`, `delivered_pending`
- `existing_refused` ← `delivered_refused`, `not_sent`
- `qty` sugerida ← `1` la primera vez; en reaperturas, el número de **rechazadas sin reponer**

El usuario ve en la misma tabla cuánto lleva y cuánto pide. Ejecutar de nuevo solo crea
documentos nuevos, con **NCF nuevo**: los rechazados por DGII ya quedaron cancelados por
`l10n_do_signed_pending()` (`l10n_do_ecf_invoicing/models/account_move.py:1437`) y nunca se reusan.

---

## 3. Generación

```
action_generate()
├─ _check_environment()
│    company.l10n_do_ecf_service_env != 'CerteCF' → UserError
│    company.l10n_do_ecf_issuer == False          → UserError
├─ partners = _ensure_certification_partners()     # §4
├─ product  = _ensure_certification_product()      # §4
├─ moves = env['account.move']
├─ para cada línea con selected y qty > 0:
│    para i en range(qty):
│        moves |= env['account.move'].create(
│            self._prepare_move_vals(line) | {"l10n_do_is_certification_doc": True})
├─ si include_notes: moves |= _generate_notes(moves)      # §3.2
├─ _apply_automation(moves)                                # §4… ver §6
└─ return acción → lista de facturas filtrada por los documentos creados
```

### 3.1 Matriz por tipo de e-CF

| Tipo | `move_type` | Diario | Partner (tipo contribuyente) | Impuestos de línea | Extras obligatorios |
|---|---|---|---|---|---|
| **E31** Crédito Fiscal | `out_invoice` | venta | `taxpayer` | ITBIS 18% venta | — |
| **E32** Consumo | `out_invoice` | venta | `non_payer` | ITBIS 18% venta | si < 250k genera el XML extra de certificación (`l10n_do_ecf_cert_file`) |
| **E33** Nota de Débito | `out_invoice` con `debit_origin_id` | venta | el del origen | ITBIS 18% venta | requiere factura origen **posteada** |
| **E34** Nota de Crédito | `out_refund` | venta | el del origen | ITBIS 18% venta | requiere factura origen **posteada** |
| **E41** Compras | `in_invoice` | compra | `non_payer` | ITBIS 18% compra + ret. 100% ITBIS + ret. 10% ISR | `l10n_do_expense_type`; **no se firma al validar** (`_do_immediate_sign`) |
| **E43** Gasto Menor | `in_invoice` | compra | `non_payer` | ITBIS 18% compra | `l10n_do_expense_type` |
| **E44** Régimen Especial | `out_invoice` | venta | `special` | **sin impuestos** | — |
| **E45** Gubernamental | `out_invoice` | venta | `governmental` | ITBIS 18% venta | — |
| **E46** Exportación | `out_invoice` | venta | `foreigner` | **sin ITBIS** | producto tipo **bien** (`dgii_reports` rechaza servicios) |
| **E47** Pago al Exterior | `in_invoice` | compra | `foreigner` | retención ISR exterior | `l10n_do_expense_type` + `l10n_do_service_type` y su detalle |

La lógica de impuestos por tipo ya está resuelta en `l10n_do_accounting/tests/common.py:205`
(`_create_l10n_do_invoice`): los casos `special` (limpia impuestos) e `informal` (ITBIS compra +
retenciones) salen de ahí. **Se porta a un helper reutilizable**, no se reescribe.

En la tabla del wizard solo aparecen los tipos **E** habilitados en los diarios de la empresa
(`l10n_do.account.journal.document_type` con `l10n_do_enable_ecf = True`).

Nunca se usa `l10n_latam_manual_document_number`: con numeración manual, `_post`
(`l10n_do_ecf_invoicing/models/account_move.py:1239`) excluye el documento de la firma y no se
emite e-CF.

### 3.2 Notas de crédito y débito

Se generan al final, sobre facturas **ya posteadas** de la misma tanda:

- **E34** → `account.move.reversal`
- **E33** → `account.debit.note` (`l10n_do_accounting/wizard/account_debit_note.py`)

Si el nivel de automatización es "Crear borrador" no hay origen posteado: las notas se saltan y se
avisa en el mensaje final. No se aborta el resto.

---

## 4. Partners y producto de prueba

Se crean **on demand** (no como `demo/` del módulo), con `ref` reconocible:

| `ref` | Nombre | RNC/Cédula | Tipo contribuyente | Usado por |
|---|---|---|---|---|
| `ECF_CERT_TAXPAYER` | ITERATIVO SRL | 131566332 | `taxpayer` | E31, E33, E34 |
| `ECF_CERT_NON_PAYER` | JOSE LUIS LOPEZ | 22400559690 | `non_payer` | E32, E41, E43 |
| `ECF_CERT_SPECIAL` | ZONA FRANCA INDUSTRIAL DE LAS AMERICAS S A | 101168481 | `special` | E44 |
| `ECF_CERT_GOV` | MINISTERIO DE INDUSTRIA Y COMERCIO Y MIPYMES | 401007355 | `governmental` | E45 |
| `ECF_CERT_FOREIGN` | Azure Interior (US) | 847898798 | `foreigner` | E46, E47 |

RNC reales, tomados de `l10n_do_accounting/tests/common.py:47` — **`l10n_do_rnc_validation` rechaza
RNC inventados**. El usuario puede cambiarlos en el wizard por los del set que le entregue DGII.

Producto `ECF_CERT_PRODUCT`: tipo `consu` (bien, por el requisito de E46), sin impuestos propios —
los pone el generador según el tipo.

---

## 5. Numeración: bloque aparte (implementado dentro de `l10n_do_ecf_invoicing`)

El entorno **no** separa la numeración: `_get_last_sequence_domain`
(`l10n_do_accounting/models/account_move.py:276`) filtra por tipo de documento, grupo de
empresas y numeración manual, y nunca mira `l10n_do_ecf_service_env`.

Además, el NCF es **único por empresa**: `l10n_do_accounting` crea el índice
`account_move_unique_l10n_do_name_sales` sobre `(name, company_id)` para documentos fiscales
posteados. Por eso un segundo contador que arranque en 1 choca con las facturas reales.

Solución, toda dentro de `l10n_do_ecf_invoicing`:

1. **Corte del contador** por el campo marcador, igual que el módulo ya hace con la
   numeración manual:

```python
def _get_last_sequence_domain(self, relaxed=False):
    where_string, param = super()._get_last_sequence_domain(relaxed)
    if self.l10n_latam_use_documents and self.country_code == "DO":
        where_string += " AND COALESCE(l10n_do_is_certification_doc, FALSE) = %(l10n_do_is_cert)s"
        param["l10n_do_is_cert"] = bool(self.l10n_do_is_certification_doc)
    return where_string, param
```

2. **Bloque de numeración propio**: `L10N_DO_CERTIFICATION_SEQUENCE_START = 1000000001`
   (→ E311000000001). Hay que fijarlo en `_get_next_sequence_format`, porque el mixin
   fuerza `seq = 0` cuando no hay documento previo y `_get_starting_sequence` solo aporta
   el formato. El valor cabe en `sequence_number`, que es `int4`.

3. **Diarios dedicados** `CRTS` / `CRTP`, creados a demanda. No son los que separan la
   numeración (eso lo hace el marcador), sino los que evitan chocar con el índice
   `(name, journal_id)` del núcleo.

**No se toca ningún otro módulo.** `l10n_do_document_pools` no interfiere: sus rutinas solo
actúan cuando el tipo de documento del diario tiene un pool en estado `valid`, y los diarios
de certificación no lo tienen; además el bloque 1.000.000.001+ queda fuera de cualquier
rango autorizado, así que no consume pool.

Efecto conocido y aceptado: tras certificar, `l10n_do_enable_first_sequence`
(`l10n_do_accounting/models/account_move.py:545`) queda apagado para los tipos usados, porque
cuenta todos los documentos posteados. Para arrancar producción en un número autorizado se usa
`l10n_do_document_pools`.

---

## 6. Niveles de automatización

| Nivel | Ejecuta | Estado final | Notas |
|---|---|---|---|
| **Crear borrador** | `create()` | `draft` | Para revisar antes de firmar |
| **Validar** | `action_post()` | `signed_pending` | `_post` firma el XML solo y deja el `.xml` + código de seguridad en la factura |
| **Validar y enviar** | `action_post()` + `l10n_do_signed_pending()` | `delivered_pending` + `trackId` | Una llamada HTTP **por documento** |

El estado final lo cierran los crons que ya existen (15 min), o el botón "Update ECF Now" de la
factura. No se añade consulta de estado al wizard.

Avisos en el wizard:

- **E41 no queda firmado al validar** (`_do_immediate_sign` devuelve `False` para el tipo 41):
  se queda en `to_send` hasta que lo tome el cron.
- Con "Validar y enviar", 20 documentos = 20 llamadas HTTP. Por encima de ~25 se procesa en lotes
  con commit intermedio para no agotar el worker.

---

## 7. Dónde aparece el botón

### 7.1 Ajustes → Contabilidad → República Dominicana *(perfil administrador)*

Heredar `l10n_do_ecf_invoicing.res_config_settings_view_form` — la vista que **crea** el ancla; si
se hereda la de `l10n_do_accounting`, el `xpath` no encuentra nada.

```xml
<xpath expr="//button[@name='l10n_do_show_ecf_doc_types']/.." position="after">
    <setting invisible="country_code != 'DO' or l10n_do_ecf_service_env != 'CerteCF'"
             groups="account.group_account_manager"
             help="Genera de forma masiva los comprobantes del set de pruebas de DGII">
        <div class="text-muted">Entorno de Certificación activo.</div>
        <button name="l10n_do_open_certification_wizard" icon="fa-arrow-right"
                type="object" string="Generar comprobantes de prueba" class="btn-link"/>
    </setting>
</xpath>
```

### 7.2 Lista de facturas *(para que el usuario se certifique solo)*

Server action con `binding_model_id = account.move`, `binding_view_types = "list"` → abre el mismo
wizard, sin depender de los registros seleccionados:

```
Acciones ▸ Generar comprobantes de certificación
```

Más un filtro en la vista de búsqueda:

```xml
<filter string="Documentos de certificación" name="certification_docs"
        domain="[('l10n_do_is_certification_doc','=',True)]"/>
```

Con ese filtro + *Agrupar por ▸ Estado de envío* (que ya existe) se ve el avance completo, sin
pantalla nueva.

### 7.3 Menú

```xml
<menuitem id="menu_ecf_certification" name="Comprobantes de certificación"
          parent="account.menu_finance_configuration" sequence="90"
          action="action_ecf_certification_wizard"
          groups="account.group_account_manager"/>
```

---

## 8. Seguridad

1. `ir.model.access.csv` para los dos modelos transitorios → `account.group_account_manager`.
2. **Guarda de servidor** en `action_generate()` y en la server action:

```python
if self.company_id.l10n_do_ecf_service_env != "CerteCF":
    raise UserError(_("Esta acción solo está disponible en el entorno de Certificación."))
```

Obligatoria: la condición de la vista no protege de un cambio de entorno a mitad del proceso ni de
una llamada RPC.

---

## 9. Archivos

```
l10n_do_ecf_invoicing/
├── models/
│   ├── account_move.py                              (M) + 1 campo, + override de numeración (§5)
│   └── res_config_settings.py                       (M) + l10n_do_open_certification_wizard()
├── wizard/
│   ├── __init__.py                                  (N)
│   ├── l10n_do_ecf_certification_wizard.py          (N) wizard + wizard.line + helper de construcción
│   └── l10n_do_ecf_certification_wizard_views.xml   (N) form + acción + menú
├── views/
│   ├── res_config_settings_views.xml                (M) botón
│   └── account_views.xml                            (M) filtro
├── data/server_action_data.xml                      (M) acción de lista
├── security/ir.model.access.csv                     (N)
├── tests/test_certification.py                      (N)
└── i18n/es_DO.po                                    (M) regenerado con odoo i18n export
```

`__manifest__.py` → versión `19.0.1.1.0` y ficheros nuevos en `data`.

**Fuera de este módulo:** los dos ajustes de §5 en `l10n_do_accounting` y `l10n_do_document_pools`.

---

## 10. Fases

| # | Fase | Contenido | Días |
|---|---|---|---|
| 1 | Helper de construcción | Portar de `tests/common.py` la lógica de partner/impuestos por tipo; semillas de partners y producto | 1,0 |
| 2 | Wizard | Modelos, `default_get` con el `read_group` de avance, `action_generate`, matriz §3.1, NC/ND | 1,5 |
| 3 | Automatización | Los 3 niveles + proceso por lotes | 0,5 |
| 4 | UI | Botón en Ajustes, server action, menú, filtro | 0,5 |
| 5 | Numeración | Override + los 2 puntos colaterales | 0,5 |
| 6 | Tests + traducción | `TransactionCase` con `l10n_do_active_test`; `odoo i18n export` | 1,0 |
| | | **Total** | **5,0** |

---

## 11. Tests

| Test | Qué valida |
|---|---|
| `test_blocked_outside_certification` | `UserError` con `TesteCF` y con `eCF` |
| `test_generate_all_types_draft` | Una línea por tipo habilitado → N borradores con el tipo de documento correcto y el flag puesto |
| `test_taxes_per_type` | E44 sin impuestos, E41 con ITBIS compra + 2 retenciones, E46 sin ITBIS |
| `test_post_signs_ecf` | Con `post`: `signed_pending` y `l10n_do_ecf_edi_file` presente |
| `test_notes_need_posted_origin` | En nivel borrador, las líneas E33/E34 se saltan sin romper la generación |
| `test_reopen_wizard_shows_progress` | Tras generar, el wizard reabierto muestra los contadores correctos por tipo |
| `test_certification_sequence_isolated` | 3 E31 de certificación no mueven el NCF de la siguiente E31 real |
| `test_first_sequence_still_editable` | `l10n_do_enable_first_sequence` sigue en `True` tras certificar |

---

## 12. Fuera de alcance

- Excluir los documentos de certificación de 606/607/608 e IT-1 (siguen siendo asientos reales).
- Relajar el constraint de `res_company.py:69`, que bloquea el paso a Producción cuando ya hay
  timbres emitidos en otro entorno.
- Descarga masiva de los XML en zip (se bajan uno a uno desde la factura, en modo desarrollador).
