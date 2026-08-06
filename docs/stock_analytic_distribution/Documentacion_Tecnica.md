# `stock_analytic_distribution` — Documentación técnica

**Reemplazo de OCA `stock_analytic` en Odoo 19, apoyado en el core**

| | |
|---|---|
| Cliente disparador | Escala Solar (migración 17.0 → 19.0) |
| Módulo propuesto | `stock_analytic_distribution` (+ puente `stock_analytic_distribution_project`) |
| Repo destino | `odoo-pro` (raíz), rama `19.0` |
| Versión | `19.0.1.0.0` |
| Sustituye | `OCA/account-analytic/stock_analytic` (17.0.1.2.1 / 18.0.1.2.0) |
| Estado | Diseño / pendiente de aprobación |

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

| | OCA `stock_analytic` | `stock_analytic_distribution` (core) |
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
odoo-pro/
├── stock_analytic_distribution/
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
│   ├── migrations/19.0.1.0.0/
│   │   ├── pre-migrate.py
│   │   └── post-migrate.py
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── common.py
│   │   ├── test_stock_analytic.py
│   │   └── test_stock_scrap.py
│   └── i18n/es_DO.po
└── stock_analytic_distribution_project/      # puente, auto_install
    ├── __init__.py
    ├── __manifest__.py
    └── models/{__init__,stock_move}.py
```

### 4.1 Manifest base

```python
{
    "name": "Stock Analytic Distribution",
    "summary": "Analytic distribution on stock moves, on top of Odoo 19 core analytic engine",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "Indexa",
    "website": "https://github.com/indexa-git/odoo-pro",
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
from odoo import api, models

from .stock_move import SYNC_KEY


class StockMoveLine(models.Model):
    _name = "stock.move.line"
    _inherit = ["stock.move.line", "analytic.mixin"]

    @api.model
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

### 4.9 Módulo puente `stock_analytic_distribution_project`

```python
{
    "name": "Stock Analytic Distribution / Project",
    "version": "19.0.1.0.0",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "author": "Indexa",
    "depends": ["stock_analytic_distribution", "project_stock_account"],
    "auto_install": True,
    "installable": True,
}
```

```python
from odoo import models


class StockMove(models.Model):
    _inherit = "stock.move"

    def _get_valid_moves_domain(self):
        """project_stock_account only lets through moves whose picking has a project
        and an analytic-enabled operation type. Also let through moves carrying a
        manual analytic distribution, otherwise they never produce analytic lines."""
        return ["|", ("analytic_distribution", "!=", False), *super()._get_valid_moves_domain()]

    def _prepare_analytic_line_values(self, account_field_values, amount, unit_amount):
        res = super()._prepare_analytic_line_values(account_field_values, amount, unit_amount)
        if self.analytic_distribution and self.picking_id:
            # Manual distribution: keep the picking category so the cost lands in the
            # "Materials" bucket of project profitability, same as the native flow.
            res["category"] = "picking_entry"
        return res
```

Sin este módulo, en cualquier DB con `project` instalado la distribución manual queda muerta. Con él, la precedencia queda explícita: **manual gana; si no hay manual, el proyecto del conduce.**

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

El upgrade va 17.0 → 18.0 → 19.0.

- **Salto 17 → 18:** `stock_analytic` existe upstream en la rama 18.0 (`18.0.1.2.0`). Sin intervención.
- **Salto 18 → 19:** `stock_analytic` no existe. Odoo lo marca para desinstalar → **borra los campos de `ir_model_fields` y dropea las columnas `analytic_distribution`**. Pérdida silenciosa de toda la imputación analítica de los conduces.

Solución: renombrar el módulo instalado antes de arrancar el 19.0, de forma que Odoo lo vea como **actualización** de `stock_analytic_distribution` en lugar de baja de `stock_analytic`.

### 6.3 Paso 0 — rename previo al arranque de 19.0

Debe ejecutarse **después** de terminar el salto 18.0 y **antes** de lanzar Odoo 19 con `-u all`. No puede vivir dentro del propio módulo: cuando corren sus scripts, la desinstalación de `stock_analytic` ya ocurrió.

```sql
-- migration/19.0/pre_rename_stock_analytic.sql
BEGIN;

UPDATE ir_module_module
   SET name = 'stock_analytic_distribution'
 WHERE name = 'stock_analytic';

UPDATE ir_module_module_dependency
   SET name = 'stock_analytic_distribution'
 WHERE name = 'stock_analytic';

UPDATE ir_model_data
   SET module = 'stock_analytic_distribution'
 WHERE module = 'stock_analytic';

UPDATE ir_model_data
   SET name = 'module_stock_analytic_distribution'
 WHERE name = 'module_stock_analytic'
   AND module = 'base'
   AND model = 'ir.module.module';

-- Views carry the module name in their key
UPDATE ir_ui_view
   SET key = replace(key, 'stock_analytic.', 'stock_analytic_distribution.')
 WHERE key LIKE 'stock_analytic.%';

COMMIT;
```

Equivalente con upgrade-util (ya está en el entorno): `util.rename_module(cr, "stock_analytic", "stock_analytic_distribution")` — `upgrade-util/src/util/modules.py:388`. Hace exactamente estos UPDATEs más el manejo de traducciones y autodiscovery. Preferible si el runbook del upgrade ya usa `--upgrade-path`.

Si `stock_picking_analytic` estaba instalado, hay que decidir: renombrarlo a un módulo propio equivalente, o desinstalarlo aceptando la pérdida de la cabecera (ver 6.6).

### 6.4 `migrations/19.0.1.0.0/pre-migrate.py`

Limpieza de residuos de la implementación OCA que nuestro módulo no define.

```python
from odoo.tools.sql import column_exists


def migrate(cr, version):
    # OCA views we do not ship: drop the xmlids so the ORM does not try to
    # reload records that no longer exist in the module.
    cr.execute(
        """
        DELETE FROM ir_ui_view
         WHERE id IN (
               SELECT res_id FROM ir_model_data
                WHERE module = 'stock_analytic_distribution'
                  AND model = 'ir.ui.view'
         )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
         WHERE module = 'stock_analytic_distribution'
           AND model = 'ir.ui.view'
        """
    )

    # stock_picking_analytic technical field, unused by the core-based flow.
    if column_exists(cr, "stock_picking", "original_analytic_distribution"):
        cr.execute("ALTER TABLE stock_picking DROP COLUMN original_analytic_distribution")
```

### 6.5 `migrations/19.0.1.0.0/post-migrate.py`

**Regla dura: no regenerar AAL de movimientos históricos.**

Las AAL de 17.0 nacieron de los apuntes de valuación (`account_analytic_line.move_line_id IS NOT NULL`) y siguen vivas después del upgrade. Si además llamamos `_create_analytic_move()` sobre movimientos `done` antiguos, el core crea una **segunda** AAL por movimiento → **todo el costo histórico se duplica en los proyectos.**

Solo se regenera para conduces **aún no validados**, donde el core nunca creó nada y el usuario espera ver la estimación:

```python
from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    moves = env["stock.move"].search(
        [
            ("state", "not in", ("done", "cancel", "draft")),
            ("picked", "=", True),
            ("analytic_distribution", "!=", False),
        ]
    )
    moves.sudo()._create_analytic_move()
```

Si el equipo funcional prefiere arranque limpio, este script se omite: la primera edición o validación del conduce genera las AAL sola.

### 6.6 `stock_picking_analytic` (analítica en la cabecera del conduce)

ACSONE `stock_picking_analytic` no existe ni en 18.0 ni en 19.0. Dos caminos:

**A — Nativo (recomendado).** La cabecera ya existe en v19: `stock.picking.project_id` + `analytic_costs` en el tipo de operación. Si el destino analítico es siempre un proyecto, cubre el caso sin código, y el puente resuelve la precedencia con las distribuciones manuales por línea.

**B — Portar el módulo.** Campo `analytic_distribution` en `stock.picking` con compute SQL sobre las líneas + inverse que baja a los movimientos. Su dependencia `base_view_inheritance_extension` **sí** está en `OCA/server-tools` 19.0. ~4 h extra. Solo si usan cuentas analíticas que no son proyectos y quieren capturarlas desde la cabecera.

Decisión pendiente de la validación en la DB del cliente (fase F0).

### 6.7 Verificación post-upgrade

```sql
-- 1. El módulo quedó instalado con el nombre nuevo, no desinstalado
SELECT name, state, latest_version
  FROM ir_module_module
 WHERE name IN ('stock_analytic', 'stock_analytic_distribution');

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

### 6.8 Alternativa: conservar el nombre `stock_analytic`

Vendorizar con el mismo nombre técnico elimina el paso 0 completo (sin rename, sin scripts de módulo). `addons_path` pone `/mnt/extra-addons-pro` **antes** de `OCA/account-analytic` (`conf/odoo.conf`), así que nuestra copia gana sobre upstream.

Se descarta: nuestra implementación **no** es la de OCA (AAL directa vs apunte contable). Un módulo con nombre de OCA y comportamiento distinto, sombreando silenciosamente al upstream cuando el submódulo suba, es una trampa para el próximo que lo toque. El rename es 20 líneas de SQL una sola vez.

---

## 7. Pruebas

### 7.1 Tests automatizados (`tests/`)

| Test | Verifica |
|---|---|
| `test_distribution_creates_aal_on_validate` | Salida con distribución 100 % → 1 AAL, `amount = -move.value`, `unit_amount = qty` |
| `test_distribution_split_two_accounts` | 60/40 → 2 AAL con los montos correctos |
| `test_estimate_before_validation` | `picked = True`, `state = assigned` → AAL estimada a `standard_price` |
| `test_change_distribution_rebalances` | Cambiar la distribución de un movimiento ya `picked` actualiza/borra las AAL, no las duplica |
| `test_move_line_propagates_to_move` | Escribir en la línea sube al movimiento; sin recursión |
| `test_mandatory_plan_blocks_validation` | Applicability `mandatory` + distribución al 50 % → `ValidationError` en `button_validate` |
| `test_procurement_propagation` | Cadena MTO propaga la distribución al movimiento generado |
| `test_scrap_analytic` | Desecho validado genera AAL |
| `test_no_double_count_with_project` | Conduce con `project_id` + `analytic_costs` + distribución manual → **un solo** juego de AAL, con la manual |
| `test_incoming_move_sign` | Entrada → AAL positiva |

### 7.2 Script de entorno

`setup_v19_stock_analytic_distribution.sh`, en la línea de los `setup_v19_*.sh` existentes: DB nueva, `stock_account` + `project` + módulos nuestros, plan analítico con 2 proyectos, productos valorados a costo estándar y FIFO, conduces de prueba (una cuenta / split 60-40 / sin distribución), un desecho.

### 7.3 Ensayo de upgrade

Con dump real de Escala Solar: 17 → 18 → SQL de rename → 19 → los cinco queries de 6.7. Antes del salto, snapshot de los queries 3 y 4 sobre la DB 17.0 para comparar.

---
