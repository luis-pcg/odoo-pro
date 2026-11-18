# Manual técnico — Remoción de inventario según la cantidad a despachar

- **Tarea:** #77344 — [NOVOMAT] Sobre Estrategia de Remoción Actual
- **Cliente:** NovoMat
- **Versión objetivo:** Odoo 19.0 Enterprise + `odoo-pro`
- **Módulo a construir:** `stock_removal_quantity_rule`
- **Fecha:** 30 de octubre de 2026

Este documento evalúa la viabilidad del requerimiento y describe cómo se desarrollaría: análisis del
comportamiento estándar, punto de extensión en el core, diseño del módulo con su código base, configuración,
plan de pruebas y checklist de entrega. No incluye estimación de horas.

---

## 1. Veredicto

**Sí es viable con un módulo propio, pequeño y sin tocar el core.**

Odoo 19 no tiene una estrategia de remoción que dependa de la cantidad pedida. Todas las estrategias
estándar (FIFO, LIFO, FEFO, *Ubicación más cercana*, *Menos paquetes*) ordenan los quants siempre igual,
sin importar si el movimiento pide 2 o 2 000 unidades. Por eso no se resuelve con configuración.

El core sí ofrece un punto de extensión limpio: `stock.quant._gather()` recibe la cantidad a reservar
(`qty`) y devuelve los quants en el orden en que se van a reservar. Basta con reordenar (o filtrar) ese
resultado según una regla configurable por rango de cantidad. La solución:

- Es **un override de un método** (`stock.quant._gather`) y **un contexto** en
  `stock.move._update_reserved_quantity_vals`. Ambos son API estable del módulo `stock` desde 17.0.
- **Conserva la estrategia nativa** (FIFO, FEFO, cercanía…) como criterio secundario: la regla sólo decide
  qué grupo de ubicaciones va primero.
- Si no hay regla aplicable, Odoo se comporta exactamente igual que hoy.

---

## 2. Situación actual del cliente

| Elemento | Hoy |
|---|---|
| Estrategia de remoción | *Ubicación más cercana* (`closest`), que ordena los quants por `location_id.complete_name` (orden alfabético) |
| Ubicaciones de despacho rápido | Nombres que empiezan por **A** → quedan primero en el orden alfabético |
| Ubicaciones principales | Resto de ubicaciones → quedan después |
| Problema | Un despacho grande también vacía primero las ubicaciones **A**, que están pensadas para pedidos pequeños. Luego hay que reabastecerlas con movimientos internos y aparecen diferencias entre ubicaciones |

Lo que se busca:

| Cantidad del movimiento | Ubicaciones que deben ir primero |
|---|---|
| Pequeña (ej. 1 – 10 uds.) | Despacho rápido (A) |
| Grande (ej. > 10 uds.) | Principales; las A se evitan o quedan como último recurso |
| Rangos intermedios | Configurables con mínimo y máximo |

---

## 3. Cómo reserva Odoo 19 (código de referencia)

Flujo de reserva al pulsar *Comprobar disponibilidad* o al confirmar el pedido:

```
stock.move._action_assign()                          odoo/addons/stock/models/stock_move.py:2051
  └─ move._update_reserved_quantity(need, location, strict=False)        :1906
       └─ move._update_reserved_quantity_vals(...)                       :1918
            └─ stock.quant._get_reserve_quantity(product, location, need) stock_quant.py:834
                 └─ stock.quant._gather(..., qty=need)                    stock_quant.py:771
                      ├─ _get_removal_strategy()   categoría → ubicación → 'fifo'   :618
                      ├─ _get_removal_strategy_order()                       :741
                      └─ si 'closest': sorted(complete_name)                 :789
```

Puntos clave de `_gather()`:

```python
def _gather(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, qty=0):
    removal_strategy = self._get_removal_strategy(product_id, location_id)
    domain = self._get_gather_domain(product_id, location_id, lot_id, package_id, owner_id, strict)
    if removal_strategy == 'least_packages' and qty:
        domain = self._run_least_packages_removal_strategy_astar(domain, qty)
    order = self._get_removal_strategy_order(removal_strategy)
    ...
    if removal_strategy == "closest":
        res = res.sorted(lambda q: (q.location_id.complete_name, -q.id))
    return res.sorted(lambda q: not q.lot_id)
```

- `_get_reserve_quantity()` recorre los quants **en el orden que devuelve `_gather()`** y reserva hasta
  cubrir la cantidad. Cambiar ese orden cambia de qué ubicación sale la mercancía.
- `qty` llega con valor sólo en la reserva. En `_get_available_quantity()` llega en `0`, así que la regla no
  afecta el cálculo de disponibilidad.
- `qty` es lo que **falta** por reservar (`need`), no la demanda total. Si un movimiento ya está parcialmente
  reservado, `need` es menor que el pedido. Por eso el módulo pasa la demanda total por contexto (sección 5.3)
  para que una reserva parcial no cambie de rango.
- `product_expiry` sobrescribe `_get_removal_strategy_order()` para FEFO. Como el módulo reordena el
  resultado ya ordenado y `sorted()` de Python es estable, FEFO se mantiene dentro de cada grupo.

---

## 4. Diseño de la solución

### 4.1 Idea

Una **regla de remoción por cantidad** dice: *para movimientos que salen de esta ubicación, de este producto
o categoría, con una demanda entre mínimo y máximo, primero estas ubicaciones y evita estas otras*.

Cada quant recibe un rango:

| Rango | Ubicación del quant |
|---|---|
| 0 | Dentro de las **ubicaciones preferidas** de la regla |
| 1 | Neutral (ni preferida ni evitada) |
| 2 | Dentro de las **ubicaciones a evitar** |

Los quants se ordenan por `(no tiene lote, rango)`. Dentro del mismo rango queda el orden de la estrategia
nativa. Si la regla tiene **Excluir ubicaciones evitadas** marcado, los quants de rango 2 no se reservan.

Ejemplo NovoMat con dos reglas en `WH/Existencias`:

| Regla | Mín. | Máx. | Preferidas | Evitar | Excluir |
|---|---|---|---|---|---|
| Despacho pequeño | 0 | 10 | `WH/Existencias/A*` | — | No |
| Despacho grande | 10 | 0 (sin límite) | `WH/Existencias/B*`, `C*`… | `WH/Existencias/A*` | No |

- Pedido de 5 uds. → toma de A; si A no alcanza, completa desde las principales.
- Pedido de 50 uds. → toma de las principales; si no alcanzan, completa desde A (o se queda parcialmente
  disponible si *Excluir* está marcado).

### 4.2 Arquitectura

```
                 ┌───────────────── stock_removal_quantity_rule ─────────────────┐
 stock.move      │  _update_reserved_quantity_vals()                              │
                 │     with_context(removal_rule_demand_qty = move.product_qty)   │
                 │                         │                                      │
 stock.quant     │  _gather()  ── super() ─┴─► quants en orden nativo             │
                 │      │                                                         │
                 │      └─► stock.removal.quantity.rule._find_rule(...)           │
                 │              └─► rule._sort_quants(quants)                     │
                 │                                                                │
 stock.removal.  │  modelo de configuración + vistas en                           │
 quantity.rule   │  Inventario ▸ Configuración ▸ Reglas de remoción por cantidad  │
                 └────────────────────────────────────────────────────────────────┘
```

### 4.3 Estructura del módulo

```
odoo-pro/stock_removal_quantity_rule/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── stock_removal_quantity_rule.py
│   ├── stock_quant.py
│   └── stock_move.py
├── security/
│   ├── ir.model.access.csv
│   └── stock_removal_quantity_rule_security.xml
├── views/
│   └── stock_removal_quantity_rule_views.xml
├── i18n/
│   └── es.po
├── tests/
│   ├── __init__.py
│   └── test_removal_quantity_rule.py
└── readme/
    └── DESCRIPTION.md
```

---

## 5. Código base

### 5.1 Manifest

```python
{
    "name": "Stock Removal Quantity Rule",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "summary": "Choose the source locations of a reservation by the quantity to ship",
    "author": "Progressa Group",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        "security/stock_removal_quantity_rule_security.xml",
        "security/ir.model.access.csv",
        "views/stock_removal_quantity_rule_views.xml",
    ],
    "installable": True,
}
```

### 5.2 Modelo de la regla

```python
from odoo import api, fields, models
from odoo.exceptions import ValidationError


class StockRemovalQuantityRule(models.Model):
    _name = "stock.removal.quantity.rule"
    _description = "Removal Rule by Quantity"
    _order = "sequence, id"
    _check_company_auto = True

    name = fields.Char(required=True, translate=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", required=True, default=lambda self: self.env.company
    )
    location_id = fields.Many2one(
        "stock.location",
        string="Source Location",
        required=True,
        check_company=True,
        domain="[('usage', '=', 'internal')]",
    )
    picking_type_ids = fields.Many2many(
        "stock.picking.type", string="Operation Types", check_company=True
    )
    product_id = fields.Many2one("product.product", check_company=True)
    product_categ_id = fields.Many2one("product.category", string="Product Category")
    min_qty = fields.Float("Minimum Quantity", digits="Product Unit")
    max_qty = fields.Float("Maximum Quantity", digits="Product Unit")
    preferred_location_ids = fields.Many2many(
        "stock.location",
        "stock_removal_qty_rule_preferred_rel",
        string="Preferred Locations",
        check_company=True,
        domain="[('usage', '=', 'internal')]",
    )
    avoided_location_ids = fields.Many2many(
        "stock.location",
        "stock_removal_qty_rule_avoided_rel",
        string="Avoided Locations",
        check_company=True,
        domain="[('usage', '=', 'internal')]",
    )
    exclude_avoided = fields.Boolean("Exclude Avoided Locations")

    @api.constrains("min_qty", "max_qty")
    def _check_quantity_range(self):
        for rule in self:
            if rule.min_qty < 0 or rule.max_qty < 0:
                raise ValidationError(self.env._("Quantities cannot be negative."))
            if rule.max_qty and rule.max_qty <= rule.min_qty:
                raise ValidationError(
                    self.env._("The maximum quantity must be greater than the minimum quantity.")
                )

    @api.constrains("preferred_location_ids", "avoided_location_ids")
    def _check_locations_overlap(self):
        for rule in self:
            if rule.preferred_location_ids & rule.avoided_location_ids:
                raise ValidationError(
                    self.env._("A location cannot be preferred and avoided in the same rule.")
                )

    @api.model
    def _find_rule(self, product, location, demand_qty, picking_type=None):
        candidates = self.search(
            [
                ("company_id", "in", [location.company_id.id, False]),
                ("location_id", "parent_of", location.id),
                "|", ("product_id", "=", False), ("product_id", "=", product.id),
                "|", ("product_categ_id", "=", False),
                ("product_categ_id", "parent_of", product.categ_id.id),
            ]
        )
        return candidates.filtered(
            lambda rule: rule._matches_quantity(demand_qty, product.uom_id)
            and (not rule.picking_type_ids or picking_type in rule.picking_type_ids)
        )[:1]

    def _matches_quantity(self, demand_qty, uom):
        self.ensure_one()
        above_min = uom.compare(demand_qty, self.min_qty) > 0 or (
            not self.min_qty and uom.compare(demand_qty, 0) >= 0
        )
        below_max = not self.max_qty or uom.compare(demand_qty, self.max_qty) <= 0
        return above_min and below_max

    def _location_rank(self, location):
        self.ensure_one()
        if self._contains(self.preferred_location_ids, location):
            return 0
        if self._contains(self.avoided_location_ids, location):
            return 2
        return 1

    @api.model
    def _contains(self, parents, location):
        return any(location.parent_path.startswith(parent.parent_path) for parent in parents)

    def _sort_quants(self, quants):
        self.ensure_one()
        if self.exclude_avoided:
            quants = quants.filtered(
                lambda quant: not self._contains(self.avoided_location_ids, quant.location_id)
            )
        return quants.sorted(lambda quant: (not quant.lot_id, self._location_rank(quant.location_id)))
```

Notas de diseño:

- Los rangos son **(mín, máx]**: con `min_qty = 0` el límite inferior es inclusivo para cubrir cualquier
  cantidad positiva. Así dos reglas `0–10` y `10–0` no se solapan.
- `max_qty = 0` significa *sin límite superior*.
- La búsqueda por `parent_of` permite definir la regla en `WH/Existencias` y que aplique a cualquier
  sububicación desde la que se reserve.
- Las preferidas/evitadas también admiten ubicaciones padre (ej. un padre `WH/Existencias/Rápido` que agrupe
  todas las A). Se compara con `parent_path` para no hacer consultas por quant.
- Si varias reglas aplican, gana la de menor `sequence`; la más específica (producto) debe ir primero.

### 5.3 Demanda total del movimiento

```python
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _update_reserved_quantity_vals(self, need, location_id, lot_id=None, package_id=None, owner_id=None, strict=True):
        return super(
            StockMove,
            self.with_context(
                removal_rule_demand_qty=self.product_qty,
                removal_rule_picking_type_id=self.picking_type_id.id,
            ),
        )._update_reserved_quantity_vals(need, location_id, lot_id, package_id, owner_id, strict)
```

`product_qty` es la demanda del movimiento en la unidad del producto, así que una regla en *Unidades* sigue
funcionando aunque la línea de venta esté en cajas.

### 5.4 Override de `_gather`

```python
from odoo import models


class StockQuant(models.Model):
    _inherit = "stock.quant"

    def _gather(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, qty=0):
        quants = super()._gather(
            product_id, location_id, lot_id=lot_id, package_id=package_id,
            owner_id=owner_id, strict=strict, qty=qty,
        )
        if strict or qty <= 0:
            return quants
        demand_qty = self.env.context.get("removal_rule_demand_qty") or qty
        picking_type = self.env["stock.picking.type"].browse(
            self.env.context.get("removal_rule_picking_type_id")
        )
        rule = self.env["stock.removal.quantity.rule"].sudo()._find_rule(
            product_id, location_id, demand_qty, picking_type
        )
        return rule._sort_quants(quants) if rule else quants
```

Por qué así:

- `strict=True` se usa al validar o editar líneas con un quant concreto; ahí no se debe reordenar nada.
- `qty < 0` es una anulación de reserva; el orden de liberación no se toca.
- `qty == 0` es el cálculo de disponibilidad; no se filtra para que *Disponible* siga mostrando todo el stock.
- Con `least_packages` el core ya restringió el dominio a los paquetes óptimos; la regla sólo reordena
  dentro de ese resultado.

### 5.5 Seguridad

`security/ir.model.access.csv`:

```
id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_stock_removal_quantity_rule_user,stock.removal.quantity.rule user,model_stock_removal_quantity_rule,stock.group_stock_user,1,0,0,0
access_stock_removal_quantity_rule_manager,stock.removal.quantity.rule manager,model_stock_removal_quantity_rule,stock.group_stock_manager,1,1,1,1
```

`security/stock_removal_quantity_rule_security.xml`:

```xml
<odoo>
    <record id="stock_removal_quantity_rule_company_rule" model="ir.rule">
        <field name="name">Removal rule by quantity: multi-company</field>
        <field name="model_id" ref="model_stock_removal_quantity_rule"/>
        <field name="domain_force">[('company_id', 'in', company_ids)]</field>
    </record>
</odoo>
```

### 5.6 Vistas y menú

```xml
<odoo>
    <record id="stock_removal_quantity_rule_view_list" model="ir.ui.view">
        <field name="name">stock.removal.quantity.rule.list</field>
        <field name="model">stock.removal.quantity.rule</field>
        <field name="arch" type="xml">
            <list editable="bottom">
                <field name="sequence" widget="handle"/>
                <field name="name"/>
                <field name="location_id"/>
                <field name="picking_type_ids" widget="many2many_tags" optional="show"/>
                <field name="product_categ_id" optional="show"/>
                <field name="product_id" optional="hide"/>
                <field name="min_qty"/>
                <field name="max_qty"/>
                <field name="preferred_location_ids" widget="many2many_tags"/>
                <field name="avoided_location_ids" widget="many2many_tags"/>
                <field name="exclude_avoided"/>
                <field name="company_id" groups="base.group_multi_company" optional="show"/>
                <field name="active" column_invisible="True"/>
            </list>
        </field>
    </record>

    <record id="stock_removal_quantity_rule_view_search" model="ir.ui.view">
        <field name="name">stock.removal.quantity.rule.search</field>
        <field name="model">stock.removal.quantity.rule</field>
        <field name="arch" type="xml">
            <search>
                <field name="name"/>
                <field name="location_id"/>
                <field name="product_categ_id"/>
                <field name="product_id"/>
                <filter name="archived" string="Archived" domain="[('active', '=', False)]"/>
            </search>
        </field>
    </record>

    <record id="stock_removal_quantity_rule_action" model="ir.actions.act_window">
        <field name="name">Removal Rules by Quantity</field>
        <field name="res_model">stock.removal.quantity.rule</field>
        <field name="view_mode">list</field>
    </record>

    <menuitem
        id="stock_removal_quantity_rule_menu"
        action="stock_removal_quantity_rule_action"
        parent="stock.menu_warehouse_config"
        groups="stock.group_stock_manager,stock.group_stock_multi_locations"
        sequence="45"/>
</odoo>
```

El menú exige *Ubicaciones de almacenamiento* activadas (`stock.group_stock_multi_locations`), que el
cliente ya usa.

---

## 6. Configuración en NovoMat

1. Instalar `stock_removal_quantity_rule`.
2. Recomendado: agrupar las ubicaciones de despacho rápido bajo un padre (ej. `WH/Existencias/Rápido`) y las
   principales bajo otro (`WH/Existencias/Principal`). No es obligatorio; también se pueden seleccionar una a
   una, pero con padres las nuevas ubicaciones quedan cubiertas solas.
3. Mantener la estrategia de remoción actual (*Ubicación más cercana*) o cambiarla a FIFO/FEFO: será el
   criterio secundario dentro de cada grupo.
4. *Inventario ▸ Configuración ▸ Reglas de remoción por cantidad*, crear:

| Secuencia | Nombre | Ubicación origen | Tipo de operación | Mín. | Máx. | Preferidas | Evitar | Excluir |
|---|---|---|---|---|---|---|---|---|
| 10 | Despacho pequeño | WH/Existencias | Órdenes de entrega / Picking | 0 | 10 | WH/Existencias/Rápido | — | No |
| 20 | Despacho grande | WH/Existencias | Órdenes de entrega / Picking | 10 | 0 | WH/Existencias/Principal | WH/Existencias/Rápido | No |

5. Reabastecer las ubicaciones rápidas con la herramienta nativa: reglas de reabastecimiento (mín./máx.)
   sobre cada sububicación rápida con ruta interna desde `WH/Existencias/Principal`. Esto ya existe en Odoo y
   queda fuera del módulo.

En entregas de varios pasos (Pick → Pack → Ship) la reserva ocurre en el **Pick**, que sale de
`WH/Existencias`; por eso la regla se define ahí y con el tipo de operación *Pick*.

---

## 7. Plan de pruebas

### 7.1 Tests automatizados (`tests/test_removal_quantity_rule.py`)

Base: `odoo.tests.TransactionCase`, `@tagged("post_install", "-at_install")`. `setUpClass` crea un almacén,
`Rápido/A-01`, `Principal/B-01`, un producto almacenable y stock con `stock.quant._update_available_quantity`
(20 uds. en A-01, 100 en B-01), y las dos reglas de la sección 6.

| # | Caso | Resultado esperado |
|---|---|---|
| 1 | Entrega de 5 uds. | Una línea de 5 desde A-01 |
| 2 | Entrega de 50 uds. | Una línea de 50 desde B-01 |
| 3 | Entrega de 8 uds. con sólo 3 en A-01 | 3 desde A-01 + 5 desde B-01 |
| 4 | Entrega de 110 uds., *Excluir* = No | 100 desde B-01 + 10 desde A-01 |
| 5 | Entrega de 110 uds., *Excluir* = Sí | 100 desde B-01, movimiento parcialmente disponible |
| 6 | Sin reglas activas | Reserva idéntica a la nativa (A-01 primero por orden alfabético) |
| 7 | Reserva parcial: 50 uds. con 30 en B-01, luego entra stock y se vuelve a reservar | La segunda reserva sigue usando la regla "grande" aunque `need` = 20 |
| 8 | Regla con tipo de operación *Entrega* y movimiento interno | La regla no aplica |
| 9 | Regla por producto (sec. 5) y por categoría (sec. 10) | Gana la de producto |
| 10 | Línea en cajas de 12, demanda 1 caja | Se evalúa como 12 uds. → regla "grande" |
| 11 | Producto con lotes | Quants con lote siguen primero; dentro, se respeta la regla |
| 12 | Constraint: mín. ≥ máx., preferida = evitada | `ValidationError` |
| 13 | Multi-compañía | La regla de la compañía B no afecta reservas de la A |
| 14 | `Disponible` del producto con *Excluir* = Sí | Muestra 120 uds. (la regla no afecta la disponibilidad) |

Si `product_expiry` está instalado, un caso adicional verifica que FEFO se mantiene dentro de cada grupo
(dos lotes en B-01 con distinta fecha de remoción → sale primero el que vence antes).

Ejecución:

```bash
docker exec -it lfernandez_v19 odoo -d <db_test> -i stock_removal_quantity_rule \
  --test-tags /stock_removal_quantity_rule --stop-after-init --http-port=8070
```

### 7.2 Pruebas funcionales con el cliente

1. Pedido de venta pequeño → confirmar → la entrega toma de A.
2. Pedido de venta grande → confirmar → la entrega toma de las principales.
3. Pedido grande con principales sin stock suficiente → completa desde A.
4. App *Código de barras*: el operario ve las ubicaciones sugeridas por la regla.
5. Reabastecimiento de A con reglas mín./máx. sigue funcionando.

---

## 8. Riesgos y compatibilidad

| Tema | Análisis |
|---|---|
| Migración de versión | Sólo depende de `stock.quant._gather(…, qty)` y `stock.move._update_reserved_quantity_vals()`. Ambas firmas existen igual en 17.0 y 19.0. En una migración se revisan dos métodos |
| Otras estrategias | FIFO/LIFO/FEFO/cercanía quedan como orden secundario. `least_packages` se respeta (la regla reordena dentro de los paquetes elegidos) |
| Rendimiento | Una búsqueda de reglas por reserva; el ranking usa `parent_path` en memoria, sin consultas por quant |
| Reserva manual | El usuario puede seguir cambiando la ubicación en *Operaciones detalladas*; la regla sólo sugiere en la reserva automática |
| Movimientos encadenados | Si el movimiento se reserva desde un movimiento anterior (`move_orig_ids`), la ubicación ya viene definida y la regla no interviene, igual que la estrategia nativa |
| Otros módulos que sobrescriban `_gather` | En 19.0 sólo `stock_owner_restriction` (OCA, en `odoo-pro`) lo sobrescribe y filtra por propietario; es compatible porque la regla trabaja sobre el resultado de `super()`. Validar los módulos instalados en la base del cliente antes de instalar |

---

## 9. Checklist de entrega

- [ ] Módulo en `odoo-pro` rama `19.0`, versión `19.0.1.0.0`.
- [ ] Sin comentarios en código, `ruff`/`pylint-odoo` limpios.
- [ ] Traducción `i18n/es.po` completa.
- [ ] Tests 7.1 en verde.
- [ ] Pruebas 7.2 validadas en staging del cliente.
- [ ] Reglas iniciales del cliente cargadas (manual o por importación CSV).
- [ ] Manual de usuario generado con `tools/manual-generator`.
- [ ] PR enlazado en la tarea #77344.
