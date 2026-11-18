# Tasa del dólar en la pantalla de facturas (`account_invoice_rate` 19.0)

> Documento técnico para la tarea [#77752](https://www.progressa.group/odoo/project.task/77752)
> "Tasa de dólar en pantalla de facturas" (TDP Dominicana).
>
> Módulo: `account_invoice_rate`. Rama: 19.0. Estado: propuesta, sin implementar.

---

## 1. Lo que pide el cliente

En una factura en dólares, Odoo 19 muestra debajo de la moneda:

```
1 DOP = 0.016694 USD
```

El cliente necesita la lectura inversa, que es como se cotiza la tasa en República Dominicana:

```
1 USD = 59.90 DOP
```

Es un cambio de presentación. La contabilidad, los importes y la tasa que se guarda no cambian.

---

## 2. De dónde sale lo que se ve hoy

La línea es nativa de `account`, en `account.view_move_form`
(`odoo/addons/account/views/account_move_views.xml`, `div[@name='currency_conversion_div']`):

```xml
<div name="currency_conversion_div"
     class="d-flex gap-1 text-muted"
     invisible="currency_id == company_currency_id">
    <span>1</span>
    <field name="company_currency_id" readonly="True" options="{'no_open': True}" class="w-auto"/>
    <span>=</span>
    <field name="invoice_currency_rate" digits="[12,6]" readonly="state != 'draft'" style="max-width: 21ch;"/>
    <field name="currency_id" readonly="True" options="{'no_open': True}" class="w-auto"/>
    ...
</div>
```

`invoice_currency_rate` (`account.move`) es un `Float` almacenado, editable en borrador, que
expresa **moneda de la compañía → moneda del documento**. Con compañía en DOP y factura en USD
vale `0.016694`. Es la tasa con la que se generan los apuntes, así que no se debe cambiar su
significado: solo cómo se muestra.

---

## 3. ¿Ya existe un módulo que lo haga?

No en 19.0. Lo revisado:

| Módulo | Dónde | Resultado |
|---|---|---|
| `account` (nativo) | `19.0/odoo` | Muestra la tasa, pero en sentido compañía → documento. Sin opción para invertirla. |
| `account_invoice_rate` | `17.0/odoo-pro` | **Hace lo que se pide, pero solo existe en 17.0.** Botón estadístico "Rate" con la tasa en pesos por dólar y línea en el PDF. No está migrado a 19.0. |
| `sale_order_rate`, `purchase_order_rate` | `19.0/odoo-pro` | Tasa en cotizaciones y órdenes de compra, en el mismo sentido que el nativo (`1 DOP = x USD`). No tocan facturas. |
| `l10n_do_currency_update` | `19.0/odoo-pro` | Descarga tasas de bancos dominicanos. No afecta la presentación. |
| `currency_rate_live` | `19.0/enterprise` | Igual: solo actualiza tasas. |
| OCA en `19.0/odoo-pro/OCA` | — | Nada relacionado (`sale_company_currency` es otra cosa). |

`res.currency.rate` sí tiene nativamente `inverse_company_rate` ("DOP por unidad"), pero solo
se ve en la lista de tasas de la moneda, no en la factura.

**Conclusión:** hay que llevar `account_invoice_rate` a 19.0. No conviene migrarlo tal cual;
ver la sección siguiente.

---

## 4. Por qué reescribirlo en vez de migrarlo

El módulo de 17.0 nació cuando la factura no guardaba su tasa. Por eso:

- busca la tasa en `res.currency.rate` con una búsqueda propia (`get_invoice_rate`);
- guarda dos campos (`rate`, `last_date`) y trae un `pre_init_hook` y un recálculo masivo;
- necesitó un arreglo (commit `350306a8`) para mostrar la tasa realmente contabilizada y no la
  de la tabla.

En 19.0 `invoice_currency_rate` ya es la tasa contabilizada y ya es editable. Todo lo anterior
sobra: basta un campo calculado que sea su inverso y un cambio de vista.

Se conserva el nombre técnico `account_invoice_rate` para que las bases que vienen de 17.0 lo
actualicen en lugar de quedar con un módulo huérfano.

---

## 5. Diseño

### 5.1 Estructura

```
account_invoice_rate/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   └── account_move.py
├── views/
│   └── account_move_views.xml
├── migrations/
│   └── 19.0.1.0.0/
│       └── pre-migrate.py
├── i18n/
│   └── es.po
└── tests/
    ├── __init__.py
    └── test_invoice_inverse_rate.py
```

### 5.2 Manifest

```python
{
    "name": "Account Invoice Rate",
    "author": "INDEXA SRL",
    "website": "https://www.progressa.group/",
    "license": "Other proprietary",
    "category": "Accounting",
    "summary": "Show the invoice currency rate as company currency per document currency",
    "version": "19.0.1.0.0",
    "depends": ["account"],
    "data": [
        "views/account_move_views.xml",
    ],
    "installable": True,
}
```

### 5.3 Modelo

Un solo campo nuevo, no almacenado, con inverso para que siga siendo editable en borrador:

```python
from odoo import api, fields, models


class AccountMove(models.Model):
    _inherit = "account.move"

    invoice_currency_inverse_rate = fields.Float(
        string="Inverse Currency Rate",
        compute="_compute_invoice_currency_inverse_rate",
        inverse="_inverse_invoice_currency_inverse_rate",
        digits=0,
        help="Currency rate from document currency to company currency.",
    )

    @api.depends("invoice_currency_rate")
    def _compute_invoice_currency_inverse_rate(self):
        for move in self:
            rate = move.invoice_currency_rate
            move.invoice_currency_inverse_rate = 1 / rate if rate else 0.0

    def _inverse_invoice_currency_inverse_rate(self):
        for move in self:
            inverse_rate = move.invoice_currency_inverse_rate
            if inverse_rate:
                move.invoice_currency_rate = 1 / inverse_rate

    @api.onchange("invoice_currency_inverse_rate")
    def _onchange_invoice_currency_inverse_rate(self):
        self._inverse_invoice_currency_inverse_rate()
```

Decisiones:

- **No almacenado.** La única fuente de verdad sigue siendo `invoice_currency_rate`. No hay
  datos que migrar ni que puedan desincronizarse.
- **`digits=0`**, igual que el campo nativo: el valor se guarda con toda la precisión del
  float. Escribir `59.90` deja `invoice_currency_rate = 0.01669449...` y al recalcular vuelve a
  dar `59.90`. La cantidad de decimales visibles se fija en la vista.
- **Valor cero o vacío se ignora** en el inverso: evita la división por cero y evita dejar la
  factura sin tasa.
- El `onchange` hace que los importes en pesos se recalculen en pantalla al teclear la tasa,
  sin esperar a guardar.

### 5.4 Vista

Se hereda `account.view_move_form` y se reordena la línea. El campo nativo queda oculto en vez
de eliminarse, porque el botón de refrescar lo usa en su condición `invisible`.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<odoo>

    <record id="view_move_form" model="ir.ui.view">
        <field name="name">account.move.form.inverse.rate</field>
        <field name="model">account.move</field>
        <field name="inherit_id" ref="account.view_move_form"/>
        <field name="arch" type="xml">
            <xpath expr="//div[@name='currency_conversion_div']/field[@name='company_currency_id']" position="replace">
                <field name="currency_id" readonly="True" options="{'no_open': True}" class="w-auto"/>
            </xpath>
            <xpath expr="//div[@name='currency_conversion_div']/field[@name='invoice_currency_rate']" position="attributes">
                <attribute name="invisible">1</attribute>
            </xpath>
            <xpath expr="//div[@name='currency_conversion_div']/field[@name='invoice_currency_rate']" position="after">
                <field name="invoice_currency_inverse_rate"
                       digits="[12,4]"
                       readonly="state != 'draft'"
                       style="max-width: 21ch;"/>
            </xpath>
            <xpath expr="//div[@name='currency_conversion_div']/field[@name='currency_id']" position="replace">
                <field name="company_currency_id" readonly="True" options="{'no_open': True}" class="w-auto"/>
            </xpath>
        </field>
    </record>

</odoo>
```

Resultado: `1 USD = 59.9000 DOP`.

A validar al implementar:

- Tras el primer `xpath` hay dos `field[@name='currency_id']` dentro del div. El último
  `xpath` debe apuntar al segundo (`field[@name='currency_id'][2]` o `[last()]`); ajustar la
  expresión y comprobar el orden final en pantalla.
- Decimales visibles: `[12,4]` es una propuesta. Confirmar con el cliente si prefiere 2
  (`59.90`) o 4 (`59.9017`). Con 2 decimales, una tasa del día como `59.9017` se vería
  redondeada, aunque internamente se conserva exacta mientras no se edite.

### 5.5 Migración desde 17.0

Las bases que traen el módulo viejo tienen columnas y parámetros que ya no existen
(`account_move.rate`, `account_move.last_date`, `res_company.account_show_rate`, la vista de
ajustes y la plantilla del PDF). `migrations/19.0.1.0.0/pre-migrate.py` debe eliminarlos con
`odoo.upgrade.util` (`remove_field`, `remove_view`), como ya hace
`l10n_do_currency_update/migrations/19.0.1.0.0/pre-migrate.py`.

Antes de quitar `res.company.account_show_rate` hay que resolver una dependencia:
`sale_pos_backend/report/invoice_cashier_template.xml` lee `o.session_id.account_show_rate`.
Revisar de dónde sale ese campo en 19.0 y que no dependa del que se elimina.

En instalaciones nuevas de 19.0 (caso de esta tarea) la migración no se ejecuta.

---

## 6. Alcance

Incluido:

- Formulario de facturas de cliente, facturas de proveedor, notas de crédito y recibos
  (todo lo que usa `account.view_move_form` con moneda distinta a la de la compañía).

No incluido, a confirmar con el cliente:

- **PDF de la factura.** La tarea habla de "pantalla". El módulo de 17.0 imprimía además una
  línea "Total (RD$59.90 = US$ 1)" con el total en pesos, activable por compañía. Si se quiere,
  es una segunda entrega: plantilla heredada de `account.report_invoice_document` más el ajuste
  `account_show_rate`.
- **Cotizaciones y órdenes de compra.** `sale_order_rate` y `purchase_order_rate` siguen
  mostrando `1 DOP = x USD`. Si el cliente los usa verá los dos sentidos según el documento;
  conviene alinearlos en una tarea aparte.
- **Asientos manuales** (`move_type = 'entry'`): el div nativo ya está oculto para ellos.

---

## 7. Pruebas

`tests/test_invoice_inverse_rate.py`, sobre `AccountTestInvoicingCommon`, etiquetado
`post_install`:

| Caso | Se comprueba |
|---|---|
| Factura en moneda extranjera con tasa del día `0.016694` | `invoice_currency_inverse_rate` ≈ `59.9018` |
| Escribir `invoice_currency_inverse_rate = 59.90` en borrador | `invoice_currency_rate` ≈ `1 / 59.90` y los apuntes en moneda de la compañía = importe × 59.90 |
| Mismo cambio a través de `Form` | El `onchange` recalcula los totales sin guardar |
| Escribir `0` | `invoice_currency_rate` no cambia |
| Factura en moneda de la compañía | Inverso = `1.0` |
| Factura publicada | La tasa mostrada coincide con la contabilizada (`amount_total_signed / amount_total`) |
| `refresh_invoice_currency_rate` tras una edición manual | El inverso vuelve a la tasa de la fecha |

Prueba manual en staging: factura en USD, comprobar el texto `1 USD = … DOP`, editar la tasa,
confirmar y revisar los apuntes.

---

## 8. Riesgos

- **Herencia de vista frágil.** Si Odoo cambia `currency_conversion_div` en una versión menor,
  los `xpath` fallan al actualizar. Queda cubierto por la carga del módulo en CI.
- **Otros módulos que hereden el mismo div.** Hoy ninguno en `odoo-pro` 19.0 lo toca en
  `account.move` (verificado con `grep`).
- **Redondeo al editar.** Quien teclea `59.90` fija exactamente esa tasa; el valor nativo pasa
  a ser un decimal periódico. No afecta importes porque Odoo opera con el float completo.

---

## 9. Estimación

Estimación propia, pendiente de validar:

| Parte | Horas |
|---|---|
| Módulo (modelo, vista, traducción) | 2 |
| Pruebas automáticas | 2 |
| Script de migración desde 17.0 | 1 |
| PR, revisión y validación en staging | 1 |
| **Total** | **6** |

El PDF, si se pide, suma unas 3 horas.

---

## 10. Pendiente de confirmar

1. Versión de la base de TDP Dominicana. El síntoma descrito coincide con el formulario nativo
   de 18/19; no se verificó contra su instancia.
2. Decimales visibles (2 o 4).
3. Si también quieren la tasa en el PDF.
