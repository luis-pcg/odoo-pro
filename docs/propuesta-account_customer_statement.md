# Estado de Cuenta del Cliente — documento técnico

**Plataforma:** Odoo 17 Enterprise · **Localización:** República Dominicana (l10n_do)
**Módulo propuesto:** `account_customer_statement` · **Fecha:** 2026-08-13

Personalización del Informe de Seguimiento en Contabilidad para consultar, por cliente:
facturas en borrador, facturas publicadas, pagos recibidos con su método de pago, notas de
crédito y notas de débito.

---

## 1. Viabilidad

**Viable, riesgo técnico bajo.** Toda la información solicitada ya existe en la base de datos
(`account.move`, `account.move.line`, `account.payment`). No hace falta capturar datos nuevos ni
integrar sistemas externos. El trabajo es de consulta, consolidación y presentación.

La restricción no es de datos sino de **diseño del reporte estándar**: el Informe de Seguimiento
se alimenta exclusivamente de apuntes por cobrar *publicados y no conciliados*. Por eso nunca
muestra borradores (no están publicados) y las notas de crédito y pagos desaparecen del informe
en cuanto quedan conciliados contra la factura.

Lo solicitado no es una variante del informe de cobranza: es un **estado de cuenta por
movimientos**, que en Odoo es un reporte distinto. Se construye como módulo nuevo sin alterar el
motor del informe de seguimiento, que además dispara los correos de cobranza y el flujo de
niveles de recordatorio.

---

## 2. Por qué el reporte estándar no muestra lo pedido

Verificado directamente sobre el código de la versión instalada.

Fuente de datos del informe — `enterprise/account_followup/models/account_followup_report.py:57`:

```python
for l in partner.unreconciled_aml_ids.sorted().filtered(
        lambda aml: not aml.currency_id.is_zero(aml.amount_residual_currency)):
    if l.company_id in ... and not l.blocked:
```

El informe recorre `partner.unreconciled_aml_ids`, campo calculado en
`enterprise/account_followup/models/res_partner.py:29` a partir de una consulta que exige
`parent_state = 'posted'` y cuenta de tipo `asset_receivable`.

| Documento pedido | ¿Aparece hoy? | Causa técnica |
|---|---|---|
| Facturas borrador | **No** | Sus apuntes están en `parent_state = 'draft'`; el filtro exige `posted`. Además no tienen saldo pendiente contable. |
| Facturas publicadas | Sí, parcial | Solo mientras tengan saldo. Una factura cobrada al 100 % sale del informe. |
| Pagos y su método | **No** | Solo aparecen anticipos sin conciliar. El informe no imprime diario ni `payment_method_line_id`. |
| Notas de crédito | Solo si no conciliadas | Al conciliarse contra la factura, `amount_residual = 0` y deja de listarse. |
| Notas de débito | Sí, indistinguibles | Son `move_type = 'out_invoice'` con `debit_origin_id`; se muestran como una factura más, sin etiqueta propia. |

El informe de seguimiento responde *"¿qué me deben hoy?"*. Lo pedido es *"¿qué pasó con este
cliente?"*. Son dos reportes con reglas de saldo distintas: el segundo debe listar documentos ya
conciliados, que por definición el primero oculta.

---

## 3. Personalización local existente

Ya existe en el repositorio el módulo `account_followup_extra_features` (versión `17.0.1.1.6`,
INDEXA SRL) que **sobrescribe el informe de seguimiento para compañías con
`country_code == 'DO'`**:

- Redefine `_get_followup_report_columns_name()` y `_get_followup_report_lines()` con columnas
  propias: Referencia, Fecha, Días de emitida, Vencimiento, **NCF**, Excluido, Total Neto,
  Total Adeudado.
- Oculta columnas en modo impresión y correo.
- Reemplaza el árbol de `unreconciled_aml_ids` en `account_followup.customer_statements_form_view`.

**Riesgo de regresión.** Incorporar borradores, notas de crédito y pagos **dentro** de ese mismo
informe choca con este override, con la lógica de niveles de cobranza (`followup_line_id`), con
los totales `total_due` / `total_overdue` y con las cartas y correos de recordatorio que usan la
misma plantilla. Es una modificación de alto impacto sobre un flujo que hoy funciona en
producción.

---

## 4. Decisión de arquitectura

| Opción | Descripción | Riesgo | Veredicto |
|---|---|---|---|
| **A.** Extender el informe de seguimiento | Inyectar secciones nuevas en `account.followup.report`. | Alto: afecta cobranza, correos, niveles y totales; conflicto directo con el override DO existente. | Descartada |
| **B.** Reporte sobre el motor `account.report` | Reporte dinámico estilo Libro Mayor de Partners. | Medio-alto: el motor consulta `account_move_line` con `parent_state = 'posted'`; incluir borradores exige forzar el query base y romper supuestos del engine. | No recomendada |
| **C.** Módulo nuevo, lectura directa sobre `account.move` / `account.payment` | Modelo de reporte propio + asistente de filtros + salidas pantalla y PDF. | Bajo: sin acoplamiento al motor de cobranza, control total del layout. | **Recomendada** |

Se accede desde los mismos lugares donde el usuario lo busca hoy: botón en la ficha del cliente,
botón en la pantalla de Seguimiento, y menú *Contabilidad › Clientes › Estado de cuenta*.

---

## 5. Alcance funcional

Reporte por cliente, acotado por rango de fechas y compañía, con una sección por tipo de
documento solicitado:

| Sección | Columnas | Afecta saldo |
|---|---|---|
| 1. Facturas borrador | Referencia, fecha, vencimiento, origen, moneda, total | No — informativo |
| 2. Facturas publicadas | Nº, NCF, fecha, vencimiento, origen, total, pagado, pendiente, estado de pago | Sí |
| 3. Pagos recibidos | Nº, fecha, **diario**, **método de pago**, referencia, documentos aplicados, monto, sin aplicar | Sí (resta) |
| 4. Notas de crédito | Nº, NCF, factura revertida, fecha, motivo, total, aplicado, disponible | Sí (resta) |
| 5. Notas de débito | Nº, NCF, documento de origen, fecha, motivo, total, pendiente | Sí |
| 6. Totales | Total por sección, saldo contable y saldo proyectado con borradores | — |

**Salidas:** vista en pantalla con enlace directo a cada documento y reporte PDF QWeb con
encabezado fiscal (RNC/Cédula, razón social, período), siguiendo el patrón estándar de reportes
de Odoo.

---

## 6. Diseño técnico

### 6.1 Módulo

```python
{
    "name": "Customer Statement Report",
    "version": "17.0.1.0.0",
    "author": "INDEXA SRL",
    "license": "Other proprietary",
    "category": "Accounting/Accounting",
    "depends": ["account", "account_followup"],
    "installable": True,
}
```

La columna NCF se resuelve por dependencia blanda, para que el módulo siga siendo instalable
fuera de la localización dominicana:

```python
has_ncf = "l10n_do_fiscal_number" in self.env["account.move"]._fields
```

### 6.2 Modelos

| Modelo | Tipo | Responsabilidad |
|---|---|---|
| `customer.statement.wizard` | TransientModel | Filtros: `partner_id`, `date_from`, `date_to`, `company_ids`, consolidar contactos hijos. |
| `customer.statement.report` | AbstractModel | Motor de datos: `_get_statement(partner, options) → dict` con secciones, líneas y totales. Sin lógica de presentación. |

Regla de diseño: **un solo motor de datos, dos renderizadores**. La vista y el PDF nunca
recalculan por su cuenta; así ambos siempre cuadran entre sí.

### 6.3 Consultas por sección

Documentos — `account.move`:

```python
base = [
    ("commercial_partner_id", "=", partner.commercial_partner_id.id),
    ("company_id", "in", company_ids),
    ("date", ">=", date_from),
    ("date", "<=", date_to),
]
drafts   = base + [("state", "=", "draft"),
                   ("move_type", "in", ("out_invoice", "out_refund"))]
invoices = base + [("state", "=", "posted"),
                   ("move_type", "in", ("out_invoice", "out_receipt")),
                   ("debit_origin_id", "=", False)]
credits  = base + [("state", "=", "posted"),
                   ("move_type", "=", "out_refund")]
debits   = base + [("state", "=", "posted"),
                   ("move_type", "=", "out_invoice"),
                   ("debit_origin_id", "!=", False)]
```

Se filtra por `date` y no por `invoice_date`: en borradores `invoice_date` puede venir vacío,
mientras que `date` siempre está calculado. Para mostrar se usa `invoice_date or date`.

Pagos — `account.payment`:

```python
payments = [
    ("partner_id", "child_of", partner.commercial_partner_id.id),
    ("partner_type", "=", "customer"),
    ("is_internal_transfer", "=", False),
    ("state", "=", "posted"),          # heredado de account.move vía _inherits
    ("date", ">=", date_from), ("date", "<=", date_to),
    ("company_id", "in", company_ids),
]
```

Se incluyen `payment_type = 'inbound'` (cobros) y `'outbound'` con `partner_type = 'customer'`
(devoluciones de dinero al cliente), estas últimas con signo invertido usando `amount_signed`.

| Dato pedido | Campo Odoo 17 |
|---|---|
| Método de pago | `payment_method_line_id.name` |
| Medio / cuenta | `journal_id.name` |
| Monto en moneda de la compañía | `amount_company_currency_signed` |
| Monto en moneda del pago | `amount_signed`, `currency_id` |
| Documentos aplicados | `reconciled_invoice_ids` |
| Anticipo sin aplicar | saldo de las líneas por cobrar del pago (`is_matched` = False) |

### 6.4 Cálculo de saldos

Se publican **dos totales explícitamente rotulados**, para que el reporte no contradiga la
contabilidad:

- **Saldo contable** — suma de `amount_residual` de los apuntes por cobrar publicados. Cuadra
  exactamente con Libro Mayor de Partners y con el informe de seguimiento.
- **Saldo proyectado** — saldo contable + total de borradores. Marcado como informativo, nunca
  como cifra contable, porque un borrador no genera asiento.

### 6.5 Interfaz y seguridad

- Botón *Estado de cuenta* en la ficha de contacto y en `account_followup.customer_statements_form_view`.
- Menú *Contabilidad › Clientes › Estado de cuenta*.
- Acceso limitado a `account.group_account_invoice` y `account.group_account_readonly`.
- Multicompañía por `allowed_company_ids`; el asistente nunca consulta fuera de las compañías permitidas.
- Traducciones `es_DO` incluidas.

---

## 7. Reglas de negocio y casos límite

| Caso | Tratamiento |
|---|---|
| Borradores sin NCF ni vencimiento | Columnas vacías; sección propia; excluidos del saldo contable. |
| Factura cancelada | Excluida: `state = 'cancel'` no representa un documento vigente. |
| Nota de crédito usada como pago | Aparece en su sección y en "documentos aplicados" del pago; nunca se cuenta dos veces. |
| Anticipos sin aplicar | Listados en pagos con la columna "sin aplicar"; restan del saldo. |
| Multi-moneda | Agrupación por moneda, igual que el informe de seguimiento actual. |
| Contactos hijos del cliente | Consolidación por `commercial_partner_id`, criterio estándar de Odoo para estados de cuenta. |
| Multicompañía y sucursales | Filtro por compañía; totales separados por compañía si se selecciona más de una. |
| Ventas de Punto de Venta | Se incluyen cuando generan `account.move` de cliente, por el mismo dominio que las facturas. |
| Volumen alto de documentos | Consultas agrupadas con `_read_group` y lectura por lotes. |

---

## 8. Plan de pruebas

Pruebas unitarias en `tests/test_customer_statement.py` sobre base con localización dominicana
instalada:

1. Factura borrador aparece en su sección y **no** altera el saldo contable.
2. Factura publicada y cobrada al 100 % aparece en el estado de cuenta (y no en el informe de seguimiento).
3. Pago muestra diario y método de pago correctos.
4. Pago parcialmente aplicado reporta el remanente sin aplicar.
5. Nota de crédito conciliada aparece con su factura de origen.
6. Nota de débito se clasifica por `debit_origin_id` y no como factura.
7. Saldo contable del reporte == suma de `amount_residual` por cobrar == `partner.total_due`.
8. Cliente con documentos en dos monedas produce dos bloques de totales.
9. Documentos de otra compañía no se filtran hacia el reporte.
10. El PDF se genera sin excepción y con los mismos totales que la pantalla.

**Nota del entorno:** `run_tests.sh` puede reportar PASS aunque falle `setUpClass`. Verificar
siempre con `grep` de FAIL/ERROR sobre `test_logs/modules/<módulo>.log`.

---

## 9. Estructura de archivos

```
account_customer_statement/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── customer_statement_report.py   # motor de datos
│   └── res_partner.py                 # botón de acceso
├── wizard/
│   ├── customer_statement_wizard.py
│   └── customer_statement_wizard_views.xml
├── report/
│   ├── customer_statement_templates.xml   # QWeb PDF
│   └── customer_statement_reports.xml     # ir.actions.report
├── views/
│   ├── res_partner_views.xml
│   ├── account_followup_views.xml     # botón en pantalla de Seguimiento
│   └── menus.xml
├── security/ir.model.access.csv
├── i18n/es_DO.po
└── tests/test_customer_statement.py
```

---

Verificado contra el código instalado de `account_followup` (Enterprise 17.0) y
`account_followup_extra_features 17.0.1.1.6`.
