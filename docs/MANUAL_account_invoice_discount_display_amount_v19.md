# Manual técnico — Descuento total en facturas (Odoo 19)

Migración / reimplementación de `account_invoice_discount_display_amount` (OCA) para Odoo 19.0.

Fecha: 2026-09-10 · Autor: INDEXA SRL · Estado: análisis previo al desarrollo

---

## 1. Veredicto de viabilidad

**Viable. Riesgo bajo-medio.**

El módulo existe en las ramas `17.0` y `18.0` de `OCA/account-invoicing` y **no** en `19.0`. El código de 18.0 es idéntico al de 17.0 salvo por una fila del PDF. Todas las APIs que usa siguen vivas en Odoo 19, así que el port compila casi textual.

El trabajo real no está en el port sino en tres puntos:

1. Modernizar el cálculo del descuento a la API de impuestos nueva de v18/19 (`compute_all` quedó como legacy y redondea por línea).
2. Resolver el choque con `l10n_do_accounting`, que **reemplaza** la plantilla de totales del PDF de factura. Sin puente, la fila de descuento no sale en facturas fiscales DO.
3. Decidir dónde va la fila. El módulo OCA la pone *después* del bloque completo de totales (debajo del Total). El requerimiento del cliente dice "debajo del subtotal", que es otro xpath y otra semántica.

No hay bloqueadores. No hace falta esperar a que OCA migre.

---

## 2. Estado del arte (evidencia)

| Hecho | Comprobación |
|---|---|
| `account_invoice_discount_display_amount` existe en `OCA/account-invoicing` 17.0 y 18.0 | `git ls-tree origin/17.0`, `origin/18.0` |
| **No** existe en `OCA/account-invoicing` 19.0 | rama 19.0 tiene 49 módulos de los 91 de 18.0 |
| 18.0.1.0.0 == 17.0.1.0.0 salvo que el PDF de 18 ya no imprime la fila "Without Discount" | diff de las dos ramas |
| `sale_discount_display_amount` (contraparte de ventas, OCA/sale-workflow) **tampoco** está en 19.0 | `ls OCA/sale-workflow \| grep discount` |
| `odoo-pro/sale_pos_backend_discount_display_amount` (17.0) depende de ambos y hoy está `installable: False` | `sale_pos_backend_discount_display_amount/__manifest__.py` |

**Implicación de alcance:** si el cliente también muestra el descuento en el presupuesto/pedido de venta, hace falta migrar además `sale_discount_display_amount`. Confirmar antes de estimar.

---

## 3. Qué hace el módulo original

### `account.move.line`

| Campo | Tipo | Cálculo |
|---|---|---|
| `discount_total` | Monetary, store | `total_included(sin descuento) - price_total` |
| `price_total_no_discount` | Monetary, store | `tax_ids.compute_all(price_unit, ...)['total_included']` |

Sólo líneas con `display_type == 'product'`; el resto a 0.

### `account.move`

| Campo | Tipo | Cálculo |
|---|---|---|
| `discount_total` | Monetary, store | `sum(invoice_line_ids.discount_total)` |
| `price_total_no_discount` | Monetary, store | `sum(invoice_line_ids.price_total_no_discount)` |

Sólo si `is_invoice()`; el resto a 0.

### Vistas

```xml
<xpath expr="//field[@name='tax_totals']" position="after">
    <field name="price_total_no_discount"/>
    <field name="discount_total"/>
</xpath>
```

### Reporte

```xml
<xpath expr="//t[@t-call='account.document_tax_totals']" position="after">
    <tr t-if="display_discount" class="border-black">
        <td><strong>Discount</strong></td>
        <td class="text-end"><span t-field="o.discount_total"/></td>
    </tr>
</xpath>
```

Ambos importes son **con impuestos incluidos**. Ojo con esto: si la fila se coloca debajo del Subtotal (que es base sin impuestos), la aritmética visible no cierra.

---

## 4. Compatibilidad con Odoo 19, API por API

Rutas relativas a `odoo/addons/account/`.

| API usada | ¿Vive en 19? | Referencia |
|---|---|---|
| `account.move.line.discount` (Float, %) | Sí | `models/account_move_line.py:414` |
| `display_type == 'product'` | Sí | `models/account_move.py:1817` |
| `account.move.is_invoice()` | Sí | `models/account_move.py:6573` |
| `account.tax.compute_all()` | Sí, pero **legacy** | `models/account_tax.py:4972` |
| `//field[@name='tax_totals']` en `account.view_move_form` | Sí | `views/account_move_views.xml:1361` |
| `t-call="account.document_tax_totals"` en `account.report_invoice_document` | Sí | `views/report_invoice.xml:373` |
| variable `display_discount` en scope del reporte | Sí | `views/report_invoice.xml:169` |

**Conclusión:** un copy-paste del módulo 18.0 con `"version": "19.0.1.0.0"` arranca. Pero ver riesgos.

---

## 5. Riesgos y puntos de choque

### R1 — `l10n_do_accounting` reemplaza la plantilla de totales · **alto**

`l10n_do_accounting/views/report_invoice.xml:338-343`:

```xml
<xpath expr="//div[@id='total']/div/table/t[@t-call='account.document_tax_totals']"
       position="replace">
    <t t-if="o.tax_totals" t-call="l10n_do_accounting.document_tax_totals">
```

`l10n_do_accounting.document_tax_totals` (línea 141) es una plantilla **independiente**, no hereda de `account.document_tax_totals_template`. Consecuencias:

- La fila del módulo OCA no aparece en ninguna factura de una BD con `l10n_do_accounting` instalado.
- El xpath del módulo OCA (`//t[@t-call='account.document_tax_totals']`) puede reventar en instalación según el orden de combinación de vistas, porque el nodo ya no existe.

**Solución:** módulo puente `l10n_do_accounting_invoice_discount_display_amount` con `auto_install: True`, que hereda `l10n_do_accounting.document_tax_totals`. El módulo base no debe depender de `l10n_do_accounting`.

### R2 — `compute_all` redondea por línea · **medio**

Odoo 18 introdujo el pipeline `_prepare_base_line_for_taxes_computation` → `_add_tax_details_in_base_lines` → `_round_base_lines_tax_details` → `_get_tax_totals_summary`. `price_total` de la línea y el `tax_totals` de la factura salen de ahí; `compute_all` es la vía vieja y redondea línea a línea.

Efecto: `price_total_no_discount - price_total` puede desviarse céntimos del descuento real en facturas con muchas líneas o impuestos incluidos en precio. En un documento fiscal eso es una incidencia. Ver §6.3 para el cálculo nativo v19.

### R3 — El backend no queda dentro de la tabla de totales · **bajo**

En v19 el bloque de totales del formulario es el widget OWL `account-tax-totals-field` (`views/account_move_views.xml:1361`). Los `<field>` que añade el módulo OCA se pintan **debajo** de la tabla del widget, como pares etiqueta/valor sueltos, no como una fila más.

Para que salga como fila dentro de la tabla hay que parchear la plantilla OWL `account.TaxTotalsField` (`static/src/components/tax_totals/tax_totals.xml`) con `t-inherit`. Es trabajo extra; decidir si se paga.

### R4 — Otras plantillas de factura en el repo · **medio**

`store-addons/professional_templates/invoice/` también sustituye plantillas de factura (`switch_templates.xml`, `odoo_template.xml`). Si el cliente imprime con esas plantillas hace falta otro puente. Verificar qué plantilla usa el cliente **antes** de estimar.

### R5 — "Debajo del subtotal" no es donde lo pone OCA · **bajo, pero define el diseño**

El xpath de OCA inserta *después de todo el bloque de totales*, o sea debajo del Total. Para ponerlo debajo del Subtotal hay que insertar dentro de `account.document_tax_totals`, después del bucle `t-foreach="tax_totals['subtotals']"`.

Y si va debajo del Subtotal (base sin impuestos), el importe mostrado debería ser el **descuento sin impuestos**, no el `total_included` de OCA, o los números no cuadran a la vista. Punto a confirmar con el cliente contra la imagen de referencia.

### R6 — Recompute masivo al instalar · **medio**

Cuatro campos `store=True` nuevos, dos de ellos sobre `account_move_line`, que en una BD de producción con años de historia son millones de filas. La instalación dispara el recompute completo.

**Solución:** `pre_init_hook` que crea las columnas por SQL y `post_init_hook` que rellena por lote (patrón exacto de `sale_discount_display_amount/hooks.py`). Sin esto, la instalación en producción puede tardar horas.

---

## 6. Diseño propuesto

### 6.1 Nombre y licencia

Conservar el nombre OCA `account_invoice_discount_display_amount`, versión `19.0.1.0.0`, licencia AGPL-3, autor `Sygel, Odoo Community Association (OCA), INDEXA SRL`. Motivos:

- `sale_pos_backend_discount_display_amount` ya depende de ese nombre.
- Permite subirlo como PR de migración a `OCA/account-invoicing` 19.0 y dejar de mantenerlo nosotros.

### 6.2 Estructura de archivos

```
account_invoice_discount_display_amount/
├── __init__.py
├── __manifest__.py
├── hooks.py                        # pre/post init (R6)
├── models/
│   ├── __init__.py
│   ├── account_move.py
│   └── account_move_line.py
├── views/
│   └── account_move_views.xml
├── report/
│   └── report_invoice.xml
├── i18n/
│   ├── account_invoice_discount_display_amount.pot
│   └── es_DO.po
├── tests/
│   ├── __init__.py
│   └── test_invoice_discount_display_amount.py
└── readme/
    ├── DESCRIPTION.md
    ├── CONFIGURE.md
    └── USAGE.md

l10n_do_accounting_invoice_discount_display_amount/     # puente (R1)
├── __init__.py
├── __manifest__.py                 # auto_install: True
└── report/
    └── report_invoice.xml
```

### 6.3 Cálculo nativo v19 (recomendado sobre `compute_all`)

Se construyen las líneas base de la factura, se les pone `discount = 0`, y se pasa el juego por el mismo pipeline que usa el core para `tax_totals`. Así el "sin descuento" sale redondeado con las mismas reglas que el Total impreso.

```python
# models/account_move.py
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    discount_total = fields.Monetary(
        string="Discount Total",
        compute="_compute_discount_totals",
        currency_field="currency_id",
        store=True,
    )
    untaxed_discount_total = fields.Monetary(
        string="Untaxed Discount Total",
        compute="_compute_discount_totals",
        currency_field="currency_id",
        store=True,
    )
    price_total_no_discount = fields.Monetary(
        string="Total Without Discount",
        compute="_compute_discount_totals",
        currency_field="currency_id",
        store=True,
    )

    @api.depends(
        "invoice_line_ids.discount",
        "invoice_line_ids.price_unit",
        "invoice_line_ids.quantity",
        "invoice_line_ids.tax_ids",
        "currency_id",
    )
    def _compute_discount_totals(self):
        AccountTax = self.env["account.tax"]
        for move in self:
            if not move.is_invoice(include_receipts=True):
                move.discount_total = 0.0
                move.untaxed_discount_total = 0.0
                move.price_total_no_discount = 0.0
                continue

            product_lines = move.invoice_line_ids.filtered(
                lambda line: line.display_type == "product"
            )
            base_lines = []
            for line in product_lines:
                base_line = move._prepare_product_base_line_for_taxes_computation(line)
                base_line["discount"] = 0.0
                base_lines.append(base_line)

            AccountTax._add_tax_details_in_base_lines(base_lines, move.company_id)
            AccountTax._round_base_lines_tax_details(base_lines, move.company_id)
            totals = AccountTax._get_tax_totals_summary(
                base_lines=base_lines,
                currency=move.currency_id,
                company=move.company_id,
            )

            move.price_total_no_discount = totals["total_amount_currency"]
            move.discount_total = totals["total_amount_currency"] - move.amount_total
            move.untaxed_discount_total = (
                totals["base_amount_currency"] - move.amount_untaxed
            )
```

`untaxed_discount_total` es el que se imprime si la fila va debajo del Subtotal (R5). `discount_total` mantiene la semántica OCA (con impuestos) para no romper `sale_pos_backend_discount_display_amount`.

Referencias del core: `_prepare_product_base_line_for_taxes_computation` en `models/account_move.py:1591`, `_add_tax_details_in_base_lines` en `models/account_tax.py:1811`, `_round_base_lines_tax_details` en `models/account_tax.py:2182`, `_get_tax_totals_summary` en `models/account_tax.py:2724`.

### 6.4 Campos de línea (paridad OCA)

Se mantienen `account.move.line.discount_total` y `price_total_no_discount` por compatibilidad con módulos que ya los leen, pero calculados con `_prepare_base_line_for_taxes_computation` sobre la línea suelta, no con `compute_all`.

Si nadie los consume, **eliminarlos**: quita dos columnas `store` de `account_move_line` y con ello el riesgo R6 casi entero. Decisión de alcance.

### 6.5 Reporte PDF

Fila debajo del Subtotal, dentro de la plantilla de totales:

```xml
<!-- report/report_invoice.xml -->
<template id="document_tax_totals_discount"
          inherit_id="account.document_tax_totals">
    <xpath expr="//t[@t-foreach='tax_totals[&quot;subtotals&quot;]']" position="after">
        <tr t-if="o.untaxed_discount_total" name="discount_total">
            <td><span>Descuento</span></td>
            <td class="text-end">
                <span t-out="o.untaxed_discount_total"
                      t-options='{"widget": "monetary", "display_currency": currency}'/>
            </td>
        </tr>
    </xpath>
</template>
```

Se hereda `account.document_tax_totals` (el hijo `primary="True"` de `views/report_invoice.xml:602`), no `account.document_tax_totals_template`, porque este último lo comparten venta y compra y la fila aparecería también en presupuestos y órdenes de compra.

Puente DO, mismo bloque contra `l10n_do_accounting.document_tax_totals`.

### 6.6 Backend

**Opción A (mínima, patrón OCA):** dos `<field>` después del widget. Se ven, pero fuera de la tabla de totales.

**Opción B (fiel a la imagen):** parche OWL.

```javascript
// static/src/components/tax_totals/tax_totals.js
import { patch } from "@web/core/utils/patch";
import { TaxTotalsField } from "@account/components/tax_totals/tax_totals";
```

```xml
<!-- static/src/components/tax_totals/tax_totals.xml -->
<t t-name="account_invoice_discount_display_amount.TaxTotalsField"
   t-inherit="account.TaxTotalsField" t-inherit-mode="extension">
    <xpath expr="//t[@t-foreach='totals.subtotals']" position="after">
        <tr t-if="props.record.data.untaxed_discount_total">
            <td class="o_td_label">
                <label class="o_form_label o_tax_total_label">Descuento</label>
            </td>
            <td class="o_list_monetary">
                <span t-out="formatMonetary(props.record.data.untaxed_discount_total)"/>
            </td>
        </tr>
    </xpath>
</t>
```

Recomendación: empezar por A, ofrecer B como mejora si el cliente lo pide al ver la pantalla.

### 6.7 Hooks de instalación

```python
# hooks.py
from odoo.tools.sql import column_exists, create_column

COLUMNS = (
    ("account_move", "discount_total"),
    ("account_move", "untaxed_discount_total"),
    ("account_move", "price_total_no_discount"),
)


def pre_init_hook(env):
    for table, column in COLUMNS:
        if not column_exists(env.cr, table, column):
            create_column(env.cr, table, column, "numeric")


def post_init_hook(env):
    env.cr.execute("""
        UPDATE account_move am
        SET discount_total = 0.0,
            untaxed_discount_total = 0.0,
            price_total_no_discount = am.amount_total
        WHERE NOT EXISTS (
            SELECT 1 FROM account_move_line aml
            WHERE aml.move_id = am.id AND aml.discount != 0.0
        )
    """)
    env.cr.execute("""
        SELECT DISTINCT move_id FROM account_move_line WHERE discount != 0.0
    """)
    moves = env["account.move"].browse([r[0] for r in env.cr.fetchall()])
    moves._compute_discount_totals()
```

En BDs grandes, recorrer `moves` por lotes de 1.000 con commit intermedio.

---

## 7. Decisiones pendientes del cliente

| # | Pregunta | Impacto |
|---|---|---|
| D1 | ¿La fila va debajo del **Subtotal** o debajo del **Total**? | xpath y semántica del importe |
| D2 | ¿El descuento se muestra **con** o **sin** impuestos? | campo a imprimir (§6.3) |
| D3 | ¿La BD tiene `l10n_do_accounting`? | +1 módulo puente (R1) |
| D4 | ¿Usa las plantillas de `store-addons/professional_templates`? | +1 puente (R4) |
| D5 | ¿Necesita también el descuento en presupuestos de venta? | + migración de `sale_discount_display_amount` |
| D6 | ¿Alguien consume `account.move.line.discount_total`? | permite quitar 2 campos store y bajar R6 |
| D7 | ¿Volumen de `account_move` en producción? | dimensiona la ventana de instalación |

---

## 8. Plan de pruebas

**Unitarias** (`tests/test_invoice_discount_display_amount.py`):

1. Factura sin descuento → `discount_total == 0`, `price_total_no_discount == amount_total`.
2. Descuento en una línea, impuesto excluido de precio → descuento esperado exacto.
3. Descuento con **impuesto incluido en precio** (caso DO: hay ITBIS incluido en el plan de cuentas local).
4. Varias líneas, descuentos distintos, comprobar que no hay desvío de céntimo contra la suma manual.
5. Líneas `line_section` / `line_note` → no aportan.
6. Nota de crédito (`out_refund`) → signo correcto.
7. Factura en moneda extranjera → importes en moneda del documento.
8. Asiento que no es factura (`entry`) → los tres campos a 0.

**Funcionales:**

9. PDF estándar: la fila sale, en la posición acordada, sólo si hay descuento.
10. PDF DO con NCF y con e-CF: la fila sale (verifica el puente).
11. Formulario: los importes coinciden con el PDF.
12. Instalación sobre copia de la BD del cliente: medir tiempo del hook.
13. Regresión: comparar 20 PDFs antes/después, cero diferencias fuera de la fila nueva.

---

## 9. Entregables

1. `account_invoice_discount_display_amount` 19.0.1.0.0 en `odoo-pro`, rama `19.0-mig-account_invoice_discount_display_amount-<iniciales>`.
2. Módulo puente DO, si aplica.
3. Tests automatizados, en verde en CI.
4. Traducción es_DO generada con `tools/i18n-generator/generate-po.sh`.
5. Script de BD de demostración (`setup_v19_account_invoice_discount.sh`) siguiendo el patrón del repo.
6. PR de migración a `OCA/account-invoicing` 19.0, opcional, para dejar de mantenerlo internamente.
