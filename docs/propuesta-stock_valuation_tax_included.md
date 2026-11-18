# Spec técnica — `stock_valuation_tax_included`

**Fecha:** 2026-09-18
**Rama base:** `17.0` (`odoo-pro`)
**Módulo nuevo:** `stock_valuation_tax_included`
**Versión:** `17.0.1.0.0`
**Depends:** `stock_account`
**Modelos intervenidos:** `stock.quant`, `res.company`, `res.config.settings`

---

## 1. Objetivo

Añadir al reporte de existencias (`stock.quant`, vista `stock.view_stock_quant_tree`) dos columnas calculadas: el importe de impuesto correspondiente al valor a mano y el valor con impuesto incluido. Ambas columnas se activan desde Inventario → Ajustes → Valoración y no alteran la valoración contable.

### 1.1 Fuera de alcance

- Valoración contable, asientos, SVL, `standard_price`, AVCO/FIFO.
- Campos almacenados, ordenables o filtrables (ver §12.4).
- Reporte QWeb/PDF propio.
- `stock.valuation.layer` y el informe de Valoración.

---

## 2. Base técnica

`value` de `stock.quant` lo define `stock_account/models/stock_quant.py:13` y lo calcula `:44-48`:

```python
quantity = quant.product_id.with_company(quant.company_id).quantity_svl
if float_is_zero(quantity, precision_rounding=quant.product_id.uom_id.rounding):
    quant.value = 0.0
    continue
quant.value = quant.quantity * quant.product_id.with_company(
    quant.company_id).value_svl / quantity
```

La base proviene de `stock.valuation.layer`, que es siempre base imponible en todos los flujos que la generan (compra, ajuste, producción, landed cost). Por tanto el impuesto no se "recupera" de ningún dato existente: hay que calcularlo sobre `value` con `account.tax.compute_all()` (`account/models/account_tax.py:671`).

---

## 3. Estructura del módulo

```
stock_valuation_tax_included/
├── __init__.py                 → from . import models
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── stock_quant.py          → campos + cálculo + agregados
│   ├── res_company.py          → juego de impuestos por compañía
│   └── res_config_settings.py  → interruptor en Ajustes
├── security/
│   └── stock_valuation_tax_included_groups.xml
├── views/
│   ├── res_config_settings_views.xml
│   └── stock_quant_views.xml
├── i18n/
│   └── es_DO.po
├── readme/
│   ├── DESCRIPTION.md
│   ├── CONFIGURE.md
│   └── USAGE.md
└── tests/
    ├── __init__.py
    └── test_stock_quant_tax_included.py
```

```python
# __manifest__.py
{
    "name": "Inventory Valuation with Taxes",
    "author": "INDEXA SRL",
    "website": "https://www.progressa.group/",
    "license": "Other proprietary",
    "category": "Operations/Inventory",
    "version": "17.0.1.0.0",
    "depends": ["stock_account"],
    "data": [
        "security/stock_valuation_tax_included_groups.xml",
        "views/res_config_settings_views.xml",
        "views/stock_quant_views.xml",
    ],
    "installable": True,
    "application": False,
}
```

`stock_account` ya arrastra `account`; no se declara.

---

## 4. Grupo técnico

```xml
<!-- security/stock_valuation_tax_included_groups.xml -->
<odoo>
    <record id="group_stock_valuation_tax_included" model="res.groups">
        <field name="name">Show Inventory Value with Taxes</field>
        <field name="category_id" ref="base.module_category_hidden"/>
    </record>
</odoo>
```

- XML ID: `stock_valuation_tax_included.group_stock_valuation_tax_included`.
- Categoría oculta: es un interruptor de función, no un rol. No entra en el selector de la categoría Inventario y no altera el radio button de esa categoría (`res.users.get_groups_by_application()`).
- Sin `implied_ids`: se concede exclusivamente desde el ajuste de §6.

---

## 5. `res.company`

```python
# models/res_company.py
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    stock_valuation_tax_type = fields.Selection(
        [("supplier", "Vendor Taxes"), ("customer", "Customer Taxes")],
        string="Taxes used on inventory value",
        default="supplier",
        help="Tax set taken from the product to compute the inventory value "
        "including taxes. Vendor taxes match the cost side of the valuation.",
    )
```

Campo por compañía, no `ir.config_parameter`: el juego de impuestos aplicable es un dato de negocio y difiere entre compañías de una misma base. Default `supplier`, que es el lado del costo.

---

## 6. Ajuste en Inventario

```python
# models/res_config_settings.py
from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    group_stock_valuation_tax_included = fields.Boolean(
        "Inventory value with taxes",
        implied_group="stock_valuation_tax_included."
        "group_stock_valuation_tax_included",
    )
    stock_valuation_tax_type = fields.Selection(
        related="company_id.stock_valuation_tax_type", readonly=False
    )
```

Se inserta en el bloque `valuation_setting_container` que ya crea `stock_account` (`stock_account/views/res_config_settings_views.xml:10`), es decir Inventario → Ajustes → Valoración.

```xml
<!-- views/res_config_settings_views.xml -->
<odoo>
    <record id="res_config_settings_view_form" model="ir.ui.view">
        <field name="name">res.config.settings.view.form.inherit.stock.valuation.tax</field>
        <field name="model">res.config.settings</field>
        <field name="inherit_id" ref="stock_account.res_config_settings_view_form"/>
        <field name="arch" type="xml">
            <xpath expr="//block[@name='valuation_setting_container']" position="inside">
                <setting id="stock_valuation_tax_included_setting"
                         help="Show an extra column with the on hand value including the product
                               taxes. Accounting valuation is not affected.">
                    <field name="group_stock_valuation_tax_included"/>
                    <div class="content-group"
                         invisible="not group_stock_valuation_tax_included">
                        <div class="row mt16">
                            <label for="stock_valuation_tax_type" class="col-lg-4 o_light_label"/>
                            <field name="stock_valuation_tax_type"/>
                        </div>
                    </div>
                </setting>
            </xpath>
        </field>
    </record>
</odoo>
```

El selector de impuestos solo se renderiza con la casilla activa.

---

## 7. Campos en `stock.quant`

| Campo | Tipo | Grupo | Contenido |
|---|---|---|---|
| `tax_amount` | `Monetary`, compute, no store | `stock.group_stock_manager` | Impuesto correspondiente al valor a mano |
| `value_tax_included` | `Monetary`, compute, no store | `stock.group_stock_manager` | `value` + `tax_amount`; sin impuestos aplicables iguala a `value` |

Ambos replican el `groups` de `value` (`stock_account/models/stock_quant.py:13`): son datos de costo y no deben quedar legibles para usuarios sin `stock.group_stock_manager`.

---

## 8. Cálculo

```python
# models/stock_quant.py
from odoo import api, fields, models
from odoo.tools import float_is_zero


class StockQuant(models.Model):
    _inherit = "stock.quant"

    tax_amount = fields.Monetary(
        "Taxes",
        compute="_compute_value_tax_included",
        groups="stock.group_stock_manager",
    )
    value_tax_included = fields.Monetary(
        "Value (Tax Incl.)",
        compute="_compute_value_tax_included",
        groups="stock.group_stock_manager",
        help="On hand value plus the taxes set on the product.",
    )

    def _get_valuation_taxes(self):
        """Hook: tax set used to gross up the inventory value."""
        self.ensure_one()
        company = self.company_id or self.env.company
        if company.stock_valuation_tax_type == "customer":
            taxes = self.product_id.taxes_id
        else:
            taxes = self.product_id.supplier_taxes_id
        return taxes.filtered(lambda tax: tax.company_id == company)

    @api.depends(
        "value",
        "quantity",
        "product_id.taxes_id",
        "product_id.supplier_taxes_id",
        "company_id.stock_valuation_tax_type",
    )
    def _compute_value_tax_included(self):
        for quant in self:
            company = quant.company_id or self.env.company
            rounding = quant.product_id.uom_id.rounding or 0.01
            taxes = quant._get_valuation_taxes() if quant.product_id else False
            if not taxes or float_is_zero(quant.quantity, precision_rounding=rounding):
                quant.tax_amount = 0.0
                quant.value_tax_included = quant.value
                continue
            res = taxes.compute_all(
                quant.value / quant.quantity,
                currency=company.currency_id,
                quantity=quant.quantity,
                product=quant.product_id,
                handle_price_include=False,
            )
            quant.value_tax_included = res["total_included"]
            quant.tax_amount = res["total_included"] - res["total_excluded"]
```

`_get_valuation_taxes()` es el punto de extensión del módulo: posición fiscal, categoría de producto o ubicación se resuelven sobrescribiendo ese método, sin tocar el `compute`.

---

## 9. Agregados en vistas agrupadas

Un campo compute sin store no se agrega en SQL: al agrupar, los totales saldrían en cero. `stock_account` resuelve esto para `value` interceptando `_read_group` (`stock_account/models/stock_quant.py:50-71`). Se replica el mecanismo para los campos nuevos.

```python
# models/stock_quant.py (continuación)
import itertools

    @api.model
    def _read_group(self, domain, groupby=(), aggregates=(), having=(),
                    offset=0, limit=None, order=None):
        """Totals of computed fields in grouped list, same trick as stock_account."""
        SPECIAL = {"value_tax_included:sum", "tax_amount:sum"}
        if SPECIAL.isdisjoint(aggregates):
            return super()._read_group(
                domain, groupby, aggregates, having, offset, limit, order
            )

        base_aggregates = [
            *(agg for agg in aggregates if agg not in SPECIAL), "id:recordset"
        ]
        base_result = super()._read_group(
            domain, groupby, base_aggregates, having, offset, limit, order
        )
        result = []
        for *other, records in base_result:
            for index, spec in enumerate(itertools.chain(groupby, aggregates)):
                if spec in SPECIAL:
                    other.insert(index, sum(records.mapped(spec.split(":")[0])))
            result.append(tuple(other))
        return result

    @api.model
    def read_group(self, domain, fields, *args, **kwargs):
        mapping = {
            "value_tax_included": "value_tax_included:sum",
            "tax_amount": "tax_amount:sum",
        }
        fields = [mapping.get(field, field) for field in fields]
        return super().read_group(domain, fields, *args, **kwargs)
```

El encadenamiento con la capa de `stock_account` es seguro: cada capa retira solo sus propios agregados especiales y delega el resto, de modo que `value:sum` se sigue resolviendo abajo.

---

## 10. Vista del reporte

Se hereda de la vista que ya inyecta `value` (`stock_account/views/stock_quant_views.xml:3-13`) para que las columnas queden contiguas.

```xml
<!-- views/stock_quant_views.xml -->
<odoo>
    <record model="ir.ui.view" id="view_stock_quant_tree_tax_included">
        <field name="name">stock.quant.tree.tax.included</field>
        <field name="model">stock.quant</field>
        <field name="inherit_id" ref="stock_account.view_stock_quant_tree_inherit"/>
        <field name="groups_id"
               eval="[(4, ref('group_stock_valuation_tax_included'))]"/>
        <field name="arch" type="xml">
            <xpath expr="//field[@name='value']" position="after">
                <field name="tax_amount" optional="hidden" sum="Total Taxes"/>
                <field name="value_tax_included" optional="show"
                       sum="Total Value (Tax Incl.)"/>
            </xpath>
        </field>
    </record>
</odoo>
```

El `groups_id` en el registro de la vista es lo que implementa el interruptor: sin el grupo, la herencia no se aplica y el árbol queda idéntico al estándar.

Opcional, misma herencia sobre `stock_account.view_stock_quant_tree_editable_inherit`, si se quiere la columna también en Ajustes de inventario.

---

## 11. Cambios por archivo

Todo es código nuevo; no se modifica ningún archivo existente del repo.

| Archivo | Contenido |
|---|---|
| `__manifest__.py` | §3 |
| `models/stock_quant.py` | 2 campos, `_get_valuation_taxes()`, `_compute_value_tax_included()`, `_read_group()`, `read_group()` |
| `models/res_company.py` | `stock_valuation_tax_type` |
| `models/res_config_settings.py` | `group_stock_valuation_tax_included`, `stock_valuation_tax_type` (related) |
| `security/stock_valuation_tax_included_groups.xml` | `res.groups` técnico |
| `views/res_config_settings_views.xml` | herencia de `stock_account.res_config_settings_view_form` |
| `views/stock_quant_views.xml` | herencia de `stock_account.view_stock_quant_tree_inherit` |
| `tests/test_stock_quant_tax_included.py` | §14 |
| `i18n/es_DO.po` | etiquetas de campos, grupo y ajuste |
| `readme/*.md` | DESCRIPTION, CONFIGURE, USAGE |

Sin `security/ir.model.access.csv`: no hay modelos nuevos.

---

## 12. Trampas de implementación

| # | Severidad | Trampa |
|---|---|---|
| 1 | Crítica | `handle_price_include=False` obligatorio en `compute_all()` |
| 2 | Alta | Valor unitario con `quantity=`, no valor total con `quantity=1` |
| 3 | Alta | Filtrar impuestos por compañía |
| 4 | Media | Campos sin store: no ordenables ni filtrables |
| 5 | Media | Producto sin impuesto debe devolver el valor neto, no cero |

**12.1 `handle_price_include=False`.** Con el default (`True`), `compute_all()` asume que el monto recibido ya trae el impuesto cuando el impuesto es `price_include`. Devolvería `total_included == value` y la columna nueva saldría idéntica a `value`: falla silenciosa, sin traza en log. La base que se pasa viene de la SVL y siempre es neta, así que debe forzarse el tratamiento como base imponible. Lo cubre el test §14 #2.

**12.2 Valor unitario.** Pasar el valor total con `quantity=1.0` calcula mal los impuestos `amount_type="fixed"` (monto fijo por unidad): se aplicarían una sola vez sobre el total. Dividir entre la cantidad y pasarla como parámetro deja correctos porcentuales y fijos.

**12.3 Multicompañía.** `product.supplier_taxes_id` y `taxes_id` pueden contener impuestos de varias compañías. Sin el `filtered(...)`, un quant sumaría impuestos de una compañía ajena.

**12.4 Sin store — consecuencia aceptada.** No se puede ordenar ni filtrar por las columnas nuevas, y en listas grandes el cálculo recorre `value_svl` por producto. Almacenarlos obligaría a recomputar ante cada SVL, cambio de impuesto y ajuste de inventario, con invalidaciones costosas y riesgo permanente de desfase.

**12.5 Producto sin impuestos y cantidad cero.** Cubiertos por el `continue` del `compute`, que devuelve `value` tal cual y `tax_amount = 0.0`.

---

## 13. Instalación, desinstalación y migración

- **Sin script de migración:** ambos campos son compute sin store; no se crean columnas en base de datos.
- **Sin autoinstalación:** el módulo se instala a mano y el grupo nace sin usuarios, de modo que hasta activar el ajuste el comportamiento es idéntico al estándar.
- **Apagar el ajuste** retira el grupo y con él la herencia de vista; el reporte vuelve al estado original sin desinstalar.
- **Desinstalar** elimina grupo, campos y vistas sin residuo en datos de negocio.

---

## 14. Tests

Archivo: `stock_valuation_tax_included/tests/test_stock_quant_tax_included.py`, `TransactionCase` sobre un producto con valoración manual, costo 100 y 10 unidades a mano.

| # | Caso | Configuración | Esperado |
|---|---|---|---|
| 1 | Impuesto no incluido en precio | 18 %, `price_include=False` | `value_tax_included == 1180.00` |
| 2 | Impuesto incluido en precio | 18 %, `price_include=True` | `value_tax_included == 1180.00` (cubre §12.1) |
| 3 | Impuesto fijo | `amount_type="fixed"`, 5 por unidad | `value_tax_included == 1050.00` |
| 4 | Producto sin impuestos | sin `supplier_taxes_id` | `value_tax_included == value` |
| 5 | Cantidad cero | quant vaciado | `tax_amount == 0.0` |
| 6 | Multicompañía | impuesto de otra compañía en el producto | se ignora |
| 7 | Selector de impuestos | `stock_valuation_tax_type="customer"` | usa `taxes_id` |
| 8 | Total agrupado | `_read_group` por `location_id` | suma de los quants del grupo |
| 9 | Permisos | usuario con solo `stock.group_stock_user` | los campos no son legibles |

⚠️ `run_tests.sh` marca PASS aunque falle `setUpClass`. Verificar siempre con `grep -E 'FAIL|ERROR' test_logs/modules/stock_valuation_tax_included.log`.

---

## 15. Traducción

`i18n/es_DO.po` con las cadenas del módulo:

| Origen | `msgstr` |
|---|---|
| `Show Inventory Value with Taxes` | Mostrar valor de inventario con impuestos |
| `Inventory value with taxes` | Valor de inventario con impuestos |
| `Taxes used on inventory value` | Impuestos usados en el valor de inventario |
| `Vendor Taxes` / `Customer Taxes` | Impuestos de proveedor / Impuestos de cliente |
| `Taxes` | Impuestos |
| `Value (Tax Incl.)` | Valor (imp. incl.) |
| `Total Taxes` / `Total Value (Tax Incl.)` | Total impuestos / Valor total (imp. incl.) |
