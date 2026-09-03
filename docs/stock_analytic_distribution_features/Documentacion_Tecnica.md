# `stock_analytic_distribution_features` — Documentación técnica

**Reemplazo de OCA `stock_analytic` en Odoo 19, apoyado en el core**

| | |
|---|---|
| Cliente disparador | Escala Solar (migración 17.0 → 19.0) |
| Módulo | `stock_analytic_distribution_features` (+ puente `stock_analytic_distribution_features_project`) |
| Repo destino | `odoo-pro/store-addons` (submódulo `indexa-git/store-addons`), rama `19.0` |
| Versión | `19.0.1.0.0` |
| Sustituye | `OCA/account-analytic/stock_analytic` (17.0.1.2.1 / 18.0.1.2.0) |
| Estado | **Implementado y probado** — 17 tests propios en verde, 236 tests de `stock_account` + `project_stock_account` sin regresión |
| Manual de usuario | `docs/manuals/stock_analytic_distribution_features/README.md` (12 capturas) |
| Base de pruebas | `./setup_v19_stock_analytic_distribution_features.sh --recreate` |

---

## 1. Problema

Escala Solar usa OCA `stock_analytic` en 17.0 para poner distribución analítica en los conduces (movimientos de inventario) y así ver el costo de las salidas de almacén imputado al proyecto **antes** de facturar (facturan al cierre del proyecto).

`stock_analytic` **no existe en la rama 19.0** de `OCA/account-analytic` (esa rama solo tiene 5 módulos migrados). Existe en 17.0 y en 18.0, lo cual es relevante para el salto intermedio del upgrade.

Hay dos PRs de migración abiertos upstream — #898 (`mergeable: clean`, CI verde, act. 2026-07-29) y #858 (`unstable`) — pero no son apostables para una fecha de producción.

---

## 2. Lo que Odoo 19 ya trae de fábrica

Odoo 19 **ya tiene toda la maquinaria analítica de stock en el core**. No hay que construirla; hay que engancharse a ella.

### 2.1 `stock_account` — motor de líneas analíticas

| Elemento | Ubicación | Qué hace |
|---|---|---|
| `stock.move.analytic_account_line_ids` | `odoo/addons/stock_account/models/stock_move.py:50` | M2M a `account.analytic.line`. Las AAL generadas por el movimiento. |
| `_get_analytic_distribution()` | `stock_move.py:255` | **Hook.** Devuelve `{}` por defecto. Punto de extensión oficial. |
| `_prepare_analytic_lines()` | `stock_move.py:615` | Calcula monto y cantidad, delega el reparto. |
| `_prepare_analytic_line_values()` | `stock_move.py:647` | Plantilla de valores de la AAL. |
| `_create_analytic_move()` | `stock_move.py:223` | Crea/actualiza las AAL. |
| `_perform_analytic_distribution()` | `stock_account/models/analytic_account.py:33` | Reparte el monto entre planes/cuentas, **actualiza o borra** AAL existentes al cambiar la distribución. |

Disparadores que el core ya cablea solo:

- `_action_done()` → `(moves_in | moves_out)._create_analytic_move()` (`stock_move.py:190`)
- `_inverse_picked()` → `_create_analytic_move()` (`stock_move.py:143`) → **AAL estimadas antes de validar**
- `stock.move.line.write()` / `unlink()` → recálculo (`stock_account/models/stock_move_line.py:28`, `:34`)

Cálculo del monto (`_prepare_analytic_lines`, `stock_move.py:615-645`):

- `state == 'done'` → `amount = move.value` (valuación real), `unit_amount = _get_valued_qty()`
- `state != 'done'` y `picked` → estimación: `qty × product.standard_price`
- `_is_out()` → monto negativo
- distribución vacía y `amount == 0` → borra las AAL

Esto último es exactamente lo que pide el cliente: **ver el costo durante la ejecución del proyecto, no al facturar.**

### 2.2 `project_stock_account` — puente proyecto ↔ conduce (CE, `auto_install`)

| Elemento | Ubicación |
|---|---|
| `stock.picking.project_id` | `odoo/addons/project_stock/models/stock_picking.py:9` |
| `stock.picking.type.analytic_costs` | `project_stock_account/models/stock_picking_type.py` |
| `_get_analytic_distribution()` → del proyecto del picking | `project_stock_account/models/stock_move.py:11-15` |
| `category = 'picking_entry'` en la AAL | `project_stock_account/models/stock_move.py:17-22` |
| Bucket "Materiales" en Rentabilidad | `project_stock_account/models/project_project.py:20-31` |
| `business_domain = 'stock_picking'` | `project_stock_account/models/analytic_applicability.py` |

Cubre el caso "un proyecto por conduce" **sin desarrollo**. No cubre: distribución manual arbitraria, split % entre varias cuentas, cuentas analíticas que no sean de un proyecto, scrap.

### 2.3 Filtro que hay que conocer (crítico)

`project_stock_account` **recorta** el conjunto de movimientos que llegan al motor:

```python
# project_stock_account/models/stock_move.py:24-27
def _get_valid_moves_domain(self):
    return ['&', ('picking_id.project_id', '!=', False), ('picking_type_id.analytic_costs', '!=', False)]

def _create_analytic_move(self):
    domain = Domain.OR([[('picking_id', '=', False)], self._get_valid_moves_domain()])
    super(StockMove, self.filtered_domain(domain))._create_analytic_move()
```

Es `auto_install` y se instalará en cualquier DB con `project` + `stock_account`. **Si no se sobreescribe `_get_valid_moves_domain()`, un movimiento con distribución manual pero sin proyecto en el conduce nunca genera AAL.** De ahí el módulo puente de la sección 4.

---

## 3. Diseño

### 3.1 Principio

Una sola fuente de verdad: el hook `_get_analytic_distribution()`. Tanto la distribución manual (nuestra) como la derivada del proyecto (core) entran por el mismo punto, producen **un solo** juego de AAL, y comparten el mismo recálculo. **No puede haber doble conteo por construcción.**

### 3.2 Diferencia de fondo con OCA `stock_analytic`

| | OCA `stock_analytic` | `stock_analytic_distribution_features` (core) |
|---|---|---|
| Cómo llega el analítico | Inyecta `analytic_distribution` en el **apunte contable** de valuación (`_get_account_move_line_vals`) y deja que `account` genere la AAL | Devuelve la distribución por `_get_analytic_distribution()` y el core crea la **AAL directa** |
| AAL resultante | `move_line_id` = apunte de valuación | `move_line_id = False`, ligada a `stock_move.analytic_account_line_ids` |
| Costo visible antes de validar | No | **Sí** (estimado a `standard_price`) |
| Recálculo al cambiar cantidades | No | **Sí** (core lo hace) |
| Monto | Del apunte contable | `move.value` con signo por `_is_out()` |
| Bucket en Rentabilidad de proyecto | Vía contabilidad | `project_account._get_items_from_aal` → "Otros costos" (o "Materiales" con el puente) |
| Código a mantener | ~180 líneas + hack de cuenta de valuación | ~70 líneas, sin tocar la valuación |

**Bug que evitamos:** OCA (17.0, 18.0 y PR #898) decide en qué apunte poner el analítico comparando contra `product.categ_id.property_stock_valuation_account_id`. En v19 la cuenta se resuelve con cadena de fallback (`stock_account/models/product.py:136-140`: categoría → `ir.default` → `company.account_stock_valuation_id`) y además existe `location.valuation_account_id`. Si la categoría no tiene la property puesta —caso normal en v19— la comparación falla, el analítico se escribe en **ambos** apuntes y las dos AAL se anulan → **costo analítico 0**. El enfoque core no toca apuntes, así que el problema no existe.

### 3.3 Contrapartida a documentar al cliente

La distribución **ya no queda marcada en el apunte contable** de valuación. Si algún reporte analítico se arma sobre `account.move.line`, cambia de forma. Las AAL sí siguen apareciendo en la cuenta analítica, en el proyecto y en el reporte de Partidas Analíticas. Odoo se movió a propósito en esa dirección para stock (por eso existe `_create_analytic_move`).

---

## 4. Estructura de los módulos

```
odoo-pro/store-addons/
├── stock_analytic_distribution_features/
│   ├── __init__.py
│   ├── __manifest__.py
│   ├── models/
│   │   ├── __init__.py
│   │   ├── analytic_applicability.py
│   │   ├── stock_move.py
│   │   ├── stock_move_line.py
│   │   ├── stock_picking.py
│   │   ├── stock_rule.py
│   │   └── stock_scrap.py
│   ├── views/
│   │   ├── stock_move_views.xml
│   │   ├── stock_picking_views.xml
│   │   └── stock_scrap_views.xml
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── test_stock_analytic.py
│   │   └── test_stock_scrap.py
│   └── i18n/es_DO.po
└── stock_analytic_distribution_features_project/      # puente, auto_install
    ├── __init__.py
    ├── __manifest__.py
    ├── models/{__init__,stock_move}.py
    └── tests/{__init__,test_project_bridge}.py
```

`store-addons` ya está en el `addons_path` (`conf/odoo.conf`), justo después de `/mnt/extra-addons-pro`.

**Ningún script de migración vive dentro del módulo.** La fusión con el módulo de OCA es una línea en `upgrade-util/src/l10n_do_banks/19.0.1.0.0/pre-module-merge.py` (§6.3), donde están las demás fusiones de la migración a 19.0.

### 4.1 Manifest base

```python
{
    "name": "Stock Analytic Distribution",
    "summary": "Analytic distribution on stock moves, on top of Odoo 19 core analytic engine",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "INDEXA SRL.",
    "website": "https://www.progressa.group/",
    "depends": ["stock_account", "analytic"],
    "data": [
        "views/stock_move_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_scrap_views.xml",
    ],
    "installable": True,
}
```

### 4.2 `models/stock_move.py`

```python
from odoo import models

SYNC_KEY = "skip_stock_analytic_sync"


class StockMove(models.Model):
    _name = "stock.move"
    _inherit = ["stock.move", "analytic.mixin"]

    def _get_analytic_distribution(self):
        """Manual distribution on the move wins over any other source
        (e.g. the project of the picking, added by project_stock_account)."""
        return self.analytic_distribution or super()._get_analytic_distribution()

    def write(self, vals):
        res = super().write(vals)
        if "analytic_distribution" in vals and not self.env.context.get(SYNC_KEY):
            self.move_line_ids.with_context(**{SYNC_KEY: True}).write(
                {"analytic_distribution": vals["analytic_distribution"]}
            )
            self.sudo()._create_analytic_move()
        return res

    def _prepare_procurement_values(self):
        """Carry the distribution to the moves created downstream (MTO chains)."""
        res = super()._prepare_procurement_values()
        if self.analytic_distribution:
            res["analytic_distribution"] = self.analytic_distribution
        return res

    def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
        res = super()._prepare_move_line_vals(quantity=quantity, reserved_quant=reserved_quant)
        if self.analytic_distribution:
            res["analytic_distribution"] = self.analytic_distribution
        return res

    def _action_done(self, cancel_backorder=False):
        for move in self:
            move._validate_distribution(
                product=move.product_id.id,
                business_domain="stock_move",
                company_id=move.company_id.id,
            )
        return super()._action_done(cancel_backorder=cancel_backorder)
```

Notas:

- No se redeclara el campo: se usa el de `analytic.mixin` tal cual (`analytic/models/analytic_mixin.py:16-21`, `store=True`, índice GIN incluido en `init()`).
- `_create_analytic_move()` en `write` es necesario porque el core solo dispara en `_action_done`, `_inverse_picked` y cambios de líneas; cambiar la distribución de un movimiento ya `picked` debe reflejarse. `_perform_analytic_distribution` ya sabe actualizar o borrar las AAL existentes.
- `_validate_distribution` (`analytic_mixin.py:182`) solo actúa si el contexto trae `validate_analytic` y hay planes obligatorios → de ahí el override de `button_validate`.
- `kwargs` útiles en v19: `business_domain` y `company_id` (`analytic/models/analytic_plan.py:446`) más `product` y `account` (`account/models/account_analytic_plan.py:59`). `picking_type` **no** puntúa en ninguna regla — el PR #898 lo pasa y no hace nada.
- Guarda `SYNC_KEY`: sin ella, move → líneas → move → líneas entra en recursión.

### 4.3 `models/stock_move_line.py`

```python
from odoo import models

from .stock_move import SYNC_KEY


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["stock.move.line", "analytic.mixin"]

    def _prepare_stock_move_vals(self):
        res = super()._prepare_stock_move_vals()
        if self.analytic_distribution:
            res["analytic_distribution"] = self.analytic_distribution
        return res

    def write(self, vals):
        res = super().write(vals)
        if "analytic_distribution" in vals and not self.env.context.get(SYNC_KEY):
            self.move_id.with_context(**{SYNC_KEY: True}).write(
                {"analytic_distribution": vals["analytic_distribution"]}
            )
            self.move_id.sudo()._create_analytic_move()
        return res
```

El core genera AAL **a nivel de movimiento**, no de línea. El campo en la línea existe por dos razones: paridad de UX con 17.0 (Operaciones Detalladas) y preservación de la columna existente en la migración. Su valor sube al movimiento, que es quien manda.

### 4.4 `models/stock_picking.py`

```python
from odoo import models


class StockPicking(models.Model):
    _inherit = "stock.picking"

    def button_validate(self):
        """Enable mandatory-plan validation (analytic.mixin._validate_distribution)."""
        return super(StockPicking, self.with_context(validate_analytic=True)).button_validate()
```

### 4.5 `models/stock_rule.py`

```python
from odoo import models


class StockRule(models.Model):
    _inherit = "stock.rule"

    def _get_custom_move_fields(self):
        return super()._get_custom_move_fields() + ["analytic_distribution"]
```

Hook confirmado en `stock/models/stock_rule.py:320`.

### 4.6 `models/stock_scrap.py`

```python
from odoo import models


class StockScrap(models.Model):
    _name = "stock.scrap"
    _inherit = ["stock.scrap", "analytic.mixin"]

    def _prepare_move_values(self):
        res = super()._prepare_move_values()
        res["analytic_distribution"] = self.analytic_distribution
        return res

    def action_validate(self):
        return super(StockScrap, self.with_context(validate_analytic=True)).action_validate()
```

Hook confirmado en `stock/models/stock_scrap.py:125`.

### 4.7 `models/analytic_applicability.py`

```python
from odoo import fields, models


class AccountAnalyticApplicability(models.Model):
    _inherit = "account.analytic.applicability"

    business_domain = fields.Selection(
        selection_add=[("stock_move", "Stock Move")],
        ondelete={"stock_move": "cascade"},
    )
```

Convive sin conflicto con el `stock_picking` que agrega `project_stock_account`.

### 4.8 Vistas

Widget igual al del core (`purchase/views/purchase_views.xml:277-279`):

```xml
<field name="analytic_distribution" widget="analytic_distribution"
       groups="analytic.group_analytic_accounting"
       options="{'product_field': 'product_id', 'business_domain': 'stock_move'}"/>
```

Puntos de inserción en v19 (**difieren de 17.0** — el PR #898 no los revisó):

| Vista | XML ID | Nota v19 |
|---|---|---|
| Formulario de conduce, líneas | `stock.view_picking_form` | El campo es **`move_ids`** con `<list>` inline (`stock_picking_views.xml:265-270`). En 17.0 era `move_ids_without_package`. |
| Formulario de movimiento | `stock.view_move_form` | `stock_move_views.xml:255` |
| Lista de movimientos | `stock.view_move_tree` | `stock_move_views.xml:27` |
| Operaciones detalladas | `stock.view_stock_move_line_detailed_operation_tree` | `stock_move_views.xml:216` |
| Líneas de movimiento | `stock.view_move_line_tree_detailed` | `stock_move_line_views.xml:40` |
| Desecho | `stock.stock_scrap_form_view` | `stock_scrap_views.xml:24` |

Todo el campo va con `groups="analytic.group_analytic_accounting"` y `optional="hide"` en las listas.

### 4.9 Módulo puente `stock_analytic_distribution_features_project`

```python
{
    "name": "Stock Analytic Distribution / Project",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "Indexa",
    "depends": ["stock_analytic_distribution_features", "project_stock_account"],
    "auto_install": True,
    "installable": True,
}
```

```python
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_analytic_distribution(self):
        """Manual distribution wins over the project of the picking.

        `stock_analytic_distribution_features` states the same rule, but it and
        `project_stock_account` are siblings in the dependency graph: which of
        the two overrides runs first depends on the module load order. This
        module depends on both, so it is always last in the MRO and its rule is
        the one that decides.
        """
        return self.analytic_distribution or super()._get_analytic_distribution()

    def _get_valid_moves_domain(self):
        """project_stock_account only lets through moves whose picking has a project
        and an analytic-enabled operation type. Also let through moves carrying a
        manual analytic distribution, otherwise they never produce analytic lines."""
        return ["|", ("analytic_distribution", "!=", False), *super()._get_valid_moves_domain()]
```

Sin este módulo, en cualquier DB con `project` instalado la distribución manual queda muerta. Con él, la precedencia queda explícita: **manual gana; si no hay manual, el proyecto del conduce.**

Dos correcciones respecto al diseño original, ambas verificadas contra el código de v19:

- **La precedencia vive aquí, no sólo en el módulo base.** `stock_analytic_distribution_features` y `project_stock_account` son hermanos en el grafo de dependencias, así que cuál de los dos `_get_analytic_distribution()` corre primero depende del orden de carga de módulos. Se reprodujo el caso: en una DB donde `project_stock_account` se instaló después, el conduce con proyecto **y** distribución manual imputó al proyecto, no a la cuenta manual. El puente depende de los dos, va siempre último en el MRO y cierra la ambigüedad.
- **No hace falta forzar `category = 'picking_entry'`.** `project_stock_account._prepare_analytic_line_values` (`project_stock_account/models/stock_move.py:17-22`) ya lo pone para *cualquier* movimiento con conduce, tenga proyecto o no. Verificado en la DB de pruebas: las partidas de distribución manual salen con `category = picking_entry`.

**Interacción a tener en cuenta:** `project_stock_account._prepare_analytic_lines` lanza `ValidationError` si el proyecto del conduce no tiene los planes marcados obligatorios para el dominio `stock_picking`. Un movimiento con distribución manual en un conduce **sin** proyecto entra igual por ese `super()`. Mientras no se configure una aplicabilidad `stock_picking` = obligatoria no pasa nada; si se configura, hay que ponerla sobre el dominio `stock_move` en su lugar.

---

## 5. Configuración funcional

1. Activar **Contabilidad Analítica** (`analytic.group_analytic_accounting`) en Ajustes → Contabilidad.
2. Plan analítico de Proyectos con una cuenta por proyecto (o usar las que crea `project`).
3. Opcional — obligatoriedad: `account.analytic.applicability` con `business_domain = 'stock_move'`, `applicability = 'mandatory'`, filtrable por categoría de producto. Al validar el conduce, si la distribución no suma 100 % → `ValidationError`.
4. Opcional — flujo nativo por proyecto: `project_id` en el conduce + `analytic_costs = True` en el tipo de operación.
5. Dónde se ve el costo: cuenta analítica → *Partidas Analíticas*; proyecto → *Rentabilidad* (bucket Materiales); movimiento → `analytic_account_line_ids`.

---

## 6. Migración de datos 17.0 (OCA) → 19.0 (nuestro)

### 6.1 Qué hay que preservar

| Modelo | Columna | Tipo | Origen |
|---|---|---|---|
| `stock_move` | `analytic_distribution` | `jsonb` | `stock_analytic` |
| `stock_move_line` | `analytic_distribution` | `jsonb` | `stock_analytic` |
| `stock_scrap` | `analytic_distribution` | `jsonb` | `stock_analytic` |
| `stock_picking` | `analytic_distribution`, `original_analytic_distribution` | `jsonb` | `stock_picking_analytic` (si estaba instalado) |
| `account_analytic_applicability` | filas con `business_domain = 'stock_move'` | — | `stock_analytic` |
| `account_analytic_line` | AAL históricas colgadas de apuntes de valuación | — | flujo OCA |

**Los nombres de campo, modelo y columna son idénticos entre OCA y nuestro módulo.** No hay transformación de datos: si el módulo existe con el nombre técnico correcto en cada salto del upgrade, los `jsonb` sobreviven intactos.

### 6.2 El único problema real: el nombre del módulo

El módulo **no reutiliza el nombre técnico de OCA**: aquél es `stock_analytic`, éste es `stock_analytic_distribution_features` (el porqué, en 6.6). Para Odoo son dos módulos distintos, y ahí está todo el riesgo.

El upgrade va 17.0 → 18.0 → 19.0.

- **Salto 17 → 18:** `stock_analytic` existe upstream en la rama 18.0 (`18.0.1.2.0`). Sin intervención.
- **Salto 18 → 19:** `stock_analytic` no existe en disco. Odoo 19 **no lo desinstala solo**: lo deja en estado inconsistente y en cada arranque escribe
  `Some modules have inconsistent states, some dependencies or manifest may be missing: ['stock_analytic']`.
  La pérdida ocurre cuando alguien lo desinstala para limpiar ese error: `ir.model.data._module_data_uninstall` borra sus `ir.model.fields` y **dropea las tres columnas `analytic_distribution`** (`stock_move`, `stock_move_line`, `stock_scrap`). Verificado: ver 6.7, camino CONTROL.

> Corrección respecto al diseño original, que daba por hecho el auto-desinstalar. La diferencia importa: sin nada hecho, los datos **no** se pierden en el arranque; se pierden más tarde, cuando alguien limpia. Es peor, porque el momento de la pérdida se desacopla del upgrade y nadie lo relaciona.

**La migración la hace `merge_module` desde upgrade-util** (6.3). No hay scripts dentro del módulo: la fusión vive en el árbol de upgrade, junto a los demás merges de la migración a 19.0.

### 6.3 Solución: `merge_module` en upgrade-util

El repo `indexa-git/upgrade-util` ya lleva los scripts de la migración a 19.0 organizados por módulo portador. `l10n_do_banks` es el que agrupa las fusiones de módulos, así que la nuestra es una línea más en su lista:

```python
# upgrade-util/src/l10n_do_banks/19.0.1.0.0/pre-module-merge.py
_MERGES = [
    ("account_auto_transfer_features", "account_transfer_features"),
    ("payment_azul", "payment_azul_webpages"),
    ("account_reconcile_payment", "l10n_do_account_withholding_tax"),
    # OCA stock_analytic has no 19.0 version; store-addons replaces it.
    ("stock_analytic", "stock_analytic_distribution_features"),
]


def migrate(cr, version):
    ...
    for old_module, into_module in _MERGES:
        util.merge_module(cr, old_module, into_module)
```

`util.merge_module` (`upgrade-util/src/util/modules.py:428`) hace todo en una llamada:

| Qué hace | Efecto aquí |
|---|---|
| Reasigna `ir_model_data`, `ir_model_constraint`, `ir_model_relation` y traducciones | Los campos `analytic_distribution` y el valor `stock_move` del dominio pasan a ser nuestros |
| Reescribe `ir_ui_view.key` | Las vistas de OCA dejan de colgar del módulo viejo |
| Rewire de `ir_module_module_dependency` | Cualquier módulo que dependiera de `stock_analytic` apunta al nuevo |
| `DELETE FROM ir_module_module WHERE name='stock_analytic'` | El módulo OCA desaparece: no queda estado inconsistente que nadie tenga que limpiar |
| `force_install_module(into)` si el viejo estaba instalado | `stock_analytic_distribution_features` queda instalado en la misma corrida, y el puente entra por `auto_install` |

Corre en fase **pre**, antes de cargar modelos y vistas. Es no-op si el módulo OCA nunca estuvo instalado: `merge_module` sale con un log y no toca nada.

**No hay transformación de datos.** Nombres de campo, modelo y columna son idénticos entre los dos módulos, así que los `jsonb` no se reescriben. Tampoco se regenera ninguna partida analítica, de modo que el costo histórico de los proyectos no se puede duplicar; las de los conduces abiertos nacen con la primera edición o validación.

Requisito de ejecución: el upgrade tiene que arrancar con `--upgrade-path` apuntando a `upgrade-util/src`, o `from odoo.upgrade import util` no resuelve. Es el mismo requisito que ya tienen los demás scripts de ese árbol.

Si `stock_picking_analytic` estaba instalado, hay que decidir aparte: portarlo o desinstalarlo aceptando la pérdida de la cabecera (6.4).

### 6.4 `stock_picking_analytic` (analítica en la cabecera del conduce)

ACSONE `stock_picking_analytic` no existe ni en 18.0 ni en 19.0. Dos caminos:

**A — Nativo (recomendado).** La cabecera ya existe en v19: `stock.picking.project_id` + `analytic_costs` en el tipo de operación. Si el destino analítico es siempre un proyecto, cubre el caso sin código, y el puente resuelve la precedencia con las distribuciones manuales por línea.

**B — Portar el módulo.** Campo `analytic_distribution` en `stock.picking` con compute SQL sobre las líneas + inverse que baja a los movimientos. Su dependencia `base_view_inheritance_extension` **sí** está en `OCA/server-tools` 19.0. ~4 h extra. Solo si usan cuentas analíticas que no son proyectos y quieren capturarlas desde la cabecera.

Decisión pendiente de la validación en la DB del cliente (fase F0).

### 6.5 Verificación post-upgrade

```sql
-- 1. El módulo quedó instalado con el nombre nuevo, no desinstalado
SELECT name, state, latest_version
  FROM ir_module_module
 WHERE name IN ('stock_analytic', 'stock_analytic_distribution_features');

-- 2. Las columnas sobrevivieron
SELECT table_name, column_name, data_type
  FROM information_schema.columns
 WHERE column_name = 'analytic_distribution'
   AND table_name IN ('stock_move', 'stock_move_line', 'stock_scrap');

-- 3. Conteo de movimientos con distribución (comparar contra el mismo query en 17.0)
SELECT count(*) FILTER (WHERE analytic_distribution IS NOT NULL AND analytic_distribution <> '{}'::jsonb)
  FROM stock_move;

-- 4. Costo analítico por cuenta (comparar contra 17.0: debe ser idéntico)
SELECT account_id, sum(amount)
  FROM account_analytic_line
 GROUP BY account_id
 ORDER BY 1;

-- 5. Sin duplicados nuevos sobre movimientos históricos
SELECT count(*)
  FROM account_analytic_line_stock_move_rel r
  JOIN stock_move m ON m.id = r.stock_move_id
 WHERE m.state = 'done'
   AND m.date < '<fecha de corte del upgrade>';
```

El punto 4 es el control clave: **el total analítico por cuenta no debe moverse ni un peso** con el upgrade.

### 6.6 Alternativa: conservar el nombre `stock_analytic`

Vendorizar con el mismo nombre técnico elimina el paso 0 completo (sin rename, sin scripts de módulo). `addons_path` pone `/mnt/extra-addons-pro` **antes** de `OCA/account-analytic` (`conf/odoo.conf`), así que nuestra copia gana sobre upstream.

Se descarta: nuestra implementación **no** es la de OCA (AAL directa vs apunte contable). Un módulo con nombre de OCA y comportamiento distinto, sombreando silenciosamente al upstream cuando el submódulo suba, es una trampa para el próximo que lo toque. Y el nombre propio no cuesta nada operativamente: la migración de datos sale gratis respetando el orden de 6.3.

### 6.7 Prueba de la migración: `replicate_stock_analytic_migration.sh`

El riesgo aquí es un módulo que desaparece, no una línea de código, así que la prueba es el entregable. El script monta un `stock_analytic` de mentira dentro del contenedor —mismos nombres técnicos que el de OCA: `analytic_distribution` en `stock.move`, `stock.move.line` y `stock.scrap` vía `analytic.mixin`, más el valor `stock_move` del dominio de aplicabilidad—, lo instala junto a `l10n_do_banks`, siembra datos como los de Escala Solar en 17.0/18.0 (conduce con reparto 60/40, desecho, dos partidas analíticas históricas al estilo OCA) y compara dos caminos sobre clones de la misma base.

```bash
./replicate_stock_analytic_migration.sh            # limpia las bases al terminar
./replicate_stock_analytic_migration.sh --keep-dbs
```

- **CONTROL:** alguien desinstala `stock_analytic` a mano para limpiar el estado inconsistente.
- **ARREGLO:** se rebobina `l10n_do_banks` y se actualiza con `--upgrade-path`, que dispara `pre-module-merge.py`.

Resultado:

```
SNAPSHOT ANTES DEL CAMBIO
  stock_move con distribucion   : 1
  stock_move_line               : 1
  stock_scrap                   : 1
  jsonb del movimiento          : [({'1': 60.0, '2': 40.0},)]
  partidas analiticas           : [(-50000.0, 2)]

CONTROL — alguien desinstala stock_analytic a mano
  columnas que sobreviven       : NINGUNA

ARREGLO — upgrade de l10n_do_banks (upgrade-util: merge_module)
  columnas que sobreviven       : stock_scrap, stock_move, stock_move_line
  stock_move con distribucion   : 1
  stock_move_line               : 1
  stock_scrap                   : 1
  jsonb del movimiento          : [({'1': 60.0, '2': 40.0},)]
  partidas analiticas           : [(-50000.0, 2)]
  valor de dominio stock_move   : 1
  aplicabilidad configurada     : 1
  modulos                       : ['stock_analytic_distribution_features=installed',
                                   'stock_analytic_distribution_features_project=installed']
```

`stock_analytic` ya no aparece en la lista de módulos: `merge_module` borró su fila. El `jsonb` sale bit a bit igual al que entró, las partidas históricas no se duplican ni se pierden, y la configuración de aplicabilidad sobrevive. Lo que sigue pendiente es el mismo contraste sobre el dump real (7.4): esto prueba el mecanismo, no el volumen ni las particularidades de los datos del cliente.

---

## 7. Pruebas

### 7.1 Tests automatizados

Base común (`tests/common.py`): `TestStockCommon` + plan «Projects» con dos cuentas, categoría a costo estándar / valoración periódica, producto almacenable a 100 y 100 u de existencia.

`stock_analytic_distribution_features/tests/` — 13 tests:

| Test | Verifica |
|---|---|
| `test_distribution_creates_aal_on_validate` | Salida con distribución 100 % → 1 AAL, `amount = -move.value`, `unit_amount = qty` |
| `test_distribution_split_two_accounts` | 60/40 → 2 AAL de −600 y −400 |
| `test_estimate_before_validation` | `picked = True`, `state = assigned` → AAL estimada a `standard_price` |
| `test_change_distribution_rebalances` | Cambiar la distribución de un movimiento ya `picked` actualiza/borra las AAL, no las duplica |
| `test_move_line_propagates_to_move` | Escribir en la línea sube al movimiento; sin recursión |
| `test_move_propagates_to_move_lines` | Y al revés: el movimiento baja a sus líneas |
| `test_mandatory_plan_blocks_validation` | Applicability `mandatory` + distribución al 50 % → `ValidationError` en `button_validate` |
| `test_mandatory_plan_allows_full_distribution` | Con el 100 % la validación pasa |
| `test_incoming_move_sign` | Entrada → AAL positiva, igual a `move.value` |
| `test_no_distribution_no_aal` | Sin distribución no se genera nada |
| `test_procurement_propagation` | `_prepare_procurement_values` lleva la distribución y `stock.rule` la acepta como campo custom |
| `test_scrap_analytic` | Desecho validado genera AAL de −200 en la cuenta |
| `test_scrap_without_distribution` | Desecho sin distribución no genera AAL |

`stock_analytic_distribution_features_project/tests/` — 4 tests:

| Test | Verifica |
|---|---|
| `test_manual_distribution_without_project` | Conduce sin proyecto pero con distribución manual → sí genera AAL (sin el puente, ninguna) |
| `test_no_double_count_with_project` | Conduce con `project_id` + `analytic_costs` + distribución manual → **un solo** juego de AAL, con la manual, `category = picking_entry` |
| `test_manual_wins_regardless_of_mro` | La precedencia la decide el puente, no el orden de carga |
| `test_project_distribution_still_works` | Sin distribución manual, el flujo nativo por proyecto queda intacto |

Resultado (contenedor `${ODOO_DEVELOPER}_v19`, DB `v19_sad_test`):

```bash
odoo -d <db> -u stock_analytic_distribution_features,stock_analytic_distribution_features_project \
     --test-enable --test-tags '/stock_analytic_distribution_features,/stock_analytic_distribution_features_project'
# 0 failed, 0 error(s)

# Regresión del core, con nuestros módulos instalados:
odoo -d <db> -u project_stock_account,stock_account \
     --test-enable --test-tags '/project_stock_account,/stock_account'
# 0 failed, 0 error(s) — 236 tests
```

### 7.2 Script de entorno

`setup_v19_stock_analytic_distribution_features.sh` (raíz del repo), en la línea de los `setup_v19_*.sh` existentes. Crea `v19_stock_analytic_distribution_features` sin datos demo, instala `stock_analytic_distribution_features` + `project_stock_account` (que dispara el `auto_install` del puente), y siembra seis escenarios:

| | Escenario | Resultado esperado |
|---|---|---|
| A | Conduce validado, 100 % a PROY-001 | 2 AAL: −250,000 y −64,000 |
| B | Conduce `picked` **sin validar**, 60/40 | −108,000 a PROY-001 y −72,000 a PROY-002, **antes de validar** |
| C | Conduce validado sin distribución | sin AAL |
| D | Desecho con distribución | −25,000 a PROY-002 |
| E | Conduce con proyecto (flujo nativo) | −100,000 a PROY-003 |
| F | Conduce con proyecto **y** distribución manual | −90,000 a PROY-001 (gana la manual) |

El script cierra imprimiendo el acumulado por cuenta y un control de duplicados (`Movimientos con partidas duplicadas: ninguno`).

### 7.3 Manual de usuario

`docs/manuals/stock_analytic_distribution_features/README.md`, generado con `tools/manual-generator`:

```bash
cd tools/manual-generator && ./generate-manual.sh --module=stock_analytic_distribution_features
```

12 capturas sobre una base limpia (`configs/stock_analytic_distribution_features.json` + `.seed.py`), en español.

### 7.4 Ensayo de upgrade

Con dump real de Escala Solar: 17 → 18 → 19 con `--upgrade-path` → los cinco queries de 6.5. Antes del salto, snapshot de los queries 3 y 4 sobre la DB 17.0 para comparar. **Pendiente:** requiere el dump del cliente.

---

## 8. Estado y pendientes

| | |
|---|---|
| Módulos implementados en `store-addons` | ✅ |
| Tests propios (13 + 4) y regresión del core (236) | ✅ en verde |
| Base de demo con los seis escenarios | ✅ `setup_v19_stock_analytic_distribution_features.sh` |
| Manual de usuario con capturas | ✅ `docs/manuals/stock_analytic_distribution_features/` |
| Traducción `es_DO` | ✅ `i18n/es_DO.po` (etiqueta «Distribución analítica», dominio «Movimiento de stock») |
| Migración de datos desde OCA `stock_analytic` | ✅ `merge_module` en `upgrade-util/src/l10n_do_banks/19.0.1.0.0/pre-module-merge.py`, probada con `replicate_stock_analytic_migration.sh` |
| Decisión sobre `stock_picking_analytic` (§6.4) | ⏳ pendiente de validar la DB del cliente |
| Ensayo 17 → 18 → 19 con datos de Escala Solar | ⏳ pendiente del dump (el mecanismo ya está probado, falta el volumen real) |
