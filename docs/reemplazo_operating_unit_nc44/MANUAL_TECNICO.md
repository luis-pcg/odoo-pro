# Manual técnico — Unidades Operativas propias de Progressa (reemplazo de `pos_operating_unit` y `stock_operating_unit`)

- **Tarea:** #76295 — Reemplazo de módulos `pos_operating_unit` y `stock_operating_unit` (Cliente NC44)
- **Versión objetivo:** Odoo 19.0 Enterprise + `odoo-pro`
- **Módulos a construir:** `operating_unit_base`, `stock_operating_unit_segregation`, `pos_operating_unit_visibility`
- **Fecha:** 27 de octubre de 2026

Este documento describe cómo se desarrollaría la solución propia que reemplaza a los módulos de terceros que
hoy usa NC44 para separar Inventario y Punto de Venta por unidad operativa (UO). Cubre el análisis de lo que
existe, la arquitectura, el diseño de cada módulo con su código base, las correcciones sobre el comportamiento
actual, la migración de datos sin pérdida, el plan de pruebas y el checklist de entrega.

---

## 1. Resumen

| Hoy (terceros) | Origen | Reemplazo propuesto |
|---|---|---|
| `operating_unit` | OCA/operating-unit (ForgeFlow, Serpent CS) | `operating_unit_base` |
| `stock_operating_unit` | OCA, portado por nosotros a 19.0 en `store-addons` | `stock_operating_unit_segregation` |
| `pos_operating_unit` | OCA (Ilyas, Ooops404), portado por nosotros a 19.0 en `store-addons` | `pos_operating_unit_visibility` |

Los nombres describen lo que hace cada módulo y no coinciden con ningún módulo de OCA ni de la tienda de
Odoo: `operating_unit_base` define la unidad operativa y el acceso de los usuarios,
`stock_operating_unit_segregation` separa el inventario por UO y `pos_operating_unit_visibility` limita la
visibilidad del PdV por UO.

Decisiones de diseño que sostienen todo el documento:

1. **Se reemplaza también el módulo base, por eso son tres módulos y no dos.** Hoy NC44 tiene instalados
   tres módulos de terceros, no dos: `stock_operating_unit` y `pos_operating_unit` dependen de
   `operating_unit` (OCA), que es el que crea el modelo de UO, los campos del usuario, los grupos y el
   contexto de las reglas. Si sólo se reescriben los dos primeros, la dependencia de OCA se queda. El módulo
   base es pequeño (un modelo, tres campos en el usuario, dos grupos y un contexto para reglas), así que se
   absorbe completo. Se mantiene separado de los otros dos para que inventario no obligue a instalar PdV ni
   al revés.
2. **Se conservan los nombres técnicos de modelo, campos y tablas** (`operating.unit`,
   `operating_unit_id`, `operating_unit_ids`, `operating_unit_users_rel`, `pos_config_operating_unit_rel`, …).
   La migración se reduce a renombrar módulos en `ir_module_module` / `ir_model_data`: los datos no se
   copian ni se transforman.
3. **Los módulos nuevos se excluyen mutuamente con los de OCA** (`"excludes"` en el manifiesto), porque
   declaran el mismo modelo `operating.unit`. Nunca pueden estar instalados a la vez.
4. **Mismo comportamiento funcional que hoy**, más las correcciones de la sección 7. La contabilidad de NC44
   sigue centralizada: no se propaga la UO a asientos, facturas ni valoración.

---

## 2. Análisis de lo existente

### 2.1 Código fuente revisado

| Módulo | Ubicación revisada | Versión |
|---|---|---|
| `operating_unit` | `odoo-pro/OCA/operating-unit/operating_unit` (submódulo OCA, rama 19.0) | 19.0.1.0.1 |
| `operating_unit_access_all` | `odoo-pro/OCA/operating-unit/operating_unit_access_all` | 19.0.1.0.0 |
| `stock_operating_unit` | `odoo-pro/store-addons/stock_operating_unit` (port 19.0, commit `031fc2e`) | 19.0.1.0.0 |
| `pos_operating_unit` | `odoo-pro/store-addons/pos_operating_unit` (port 19.0, commit `031fc2e`) | 19.0.1.0.0 |

Manuales de usuario existentes del comportamiento actual (sirven como especificación funcional y como base
de las pruebas de aceptación):

- `docs/manuals/stock_operating_unit/README.md` (+ `manual.pdf`)
- `docs/manuals/pos_operating_unit/README.md` (+ `manual.pdf`)

### 2.2 Qué hace `operating_unit` (base)

| Elemento | Detalle |
|---|---|
| Modelo `operating.unit` | `name`, `code`, `active`, `company_id` (obligatoria, por defecto la actual), `partner_id` (obligatorio), `user_ids` (M2M `operating_unit_users_rel`). Únicos `(code, company_id)` y `(name, company_id)`. `display_name = "[code] name"`. |
| `res.users` | `assigned_operating_unit_ids` (M2M almacenada), `operating_unit_ids` (calculada: todas las UO si el usuario es gerente, si no las asignadas, filtradas por compañías activas), `default_operating_unit_id`. |
| Grupos | `group_multi_operating_unit` (*Multiple Operating Unit*) y `group_manager_operating_unit` (*Manager of Operating Units*, implica el anterior). Privilegio *Operating Units Group* en la categoría *Operating Units*. |
| Reglas | Multi-compañía sobre `operating.unit` y regla de lectura `[('id','in',operating_unit_ids)]`. |
| `ir.rule._eval_context` | Inyecta `operating_unit_ids` y `operating_unit_id` en el contexto de evaluación de todas las reglas. |
| Datos | UO principal `main_operating_unit` (código `OU1`) asignada a `base.user_root` y `base.user_admin`. |
| Vistas | Menú *Ajustes → Usuarios y compañías → Operating Units*; bloque *Operating Units* en la pestaña *Permisos de acceso* del usuario. |

### 2.3 Qué hace `stock_operating_unit`

| Modelo | Campo / lógica |
|---|---|
| `stock.warehouse` | `operating_unit_id`; por defecto la UO por defecto del usuario si es de la compañía, si no la primera permitida de esa compañía. |
| `stock.location` | `operating_unit_id`. Restricciones: sólo ubicaciones internas; misma UO que la ubicación padre interna; las ubicaciones de entrada/existencias/salida de un almacén deben tener la UO del almacén. |
| `stock.picking` | `operating_unit_id` (*UO solicitante*) calculada y almacenada desde `picking_type_id.warehouse_id.operating_unit_id`, editable en borrador; restricción: debe coincidir con la del almacén del tipo de operación. |
| `stock.move` | `operating_unit_id` / `operating_unit_dest_id` relacionados con las ubicaciones; restricción: origen o destino debe ser de la UO del picking. |
| `stock.quant` | `operating_unit_id` relacionado y almacenado desde la ubicación. |
| `stock.rule` | `operating_unit_id` relacionado con el almacén (sin regla de acceso). |
| `stock.warehouse.orderpoint` | Restricción: UO del almacén = UO de la ubicación. |
| Reglas (globales, sólo lectura) | `stock.warehouse`, `stock.picking.type`, `stock.location`, `stock.move`, `stock.move.line`, `stock.picking` (dos reglas), `stock.quant`. Criterio: "sin UO o UO permitida". |
| Datos | Almacén `stock.warehouse0` y ubicación `stock.stock_location_stock` a la UO principal. |

### 2.4 Qué hace `pos_operating_unit`

| Modelo | Campo / lógica |
|---|---|
| `pos.config` | `operating_unit_ids` (M2M `pos_config_operating_unit_rel`), editable sólo por gerentes de UO. |
| `res.config.settings` | `pos_operating_unit_ids` relacionado con el PdV seleccionado (bloque *Unidades Operativas* en Ajustes de PdV). |
| `pos.session`, `pos.order`, `pos.order.line`, `pos.payment` | `operating_unit_ids` propio (M2M, una tabla `*_operating_unit_rel` por modelo) copiado del PdV en `create()`; no se recalcula después. |
| `pos.payment` | `config_id` relacionado (no almacenado) con `session_id.config_id`. |
| Reglas (globales, sólo lectura) | `pos.config`, `pos.session`, `pos.order`, `pos.order.line`, `pos.payment`, `report.pos.order` (este por `config_id.operating_unit_ids`). |
| Vistas | Columnas *Punto de venta* y *Unidades Operativas* en órdenes y pagos. |
| Fuera de alcance (declarado por el autor) | No propaga UO a asientos, facturas ni movimientos de inventario del PdV. |

### 2.5 Requerimientos de la tarea contra el código actual

| # | Requerimiento | Cubierto hoy por | Cubierto en la solución por |
|---|---|---|---|
| 1.a | Partición de datos por UO, acceso por usuario | `operating_unit` + reglas de cada módulo | `operating_unit_base` (motor) + reglas de stock y PdV |
| 1.b | Esquemas de secuencia, productos, clientes, P&L y balance por UO | Otros módulos OCA (`account_operating_unit`, `product_operating_unit`, `res_partner_operating_unit`), **no** los dos a reemplazar | Fuera de alcance para NC44 (contabilidad centralizada). Ver sección 11. |
| 1.c | Grupo *Multi Operating Unit*, creación de UO desde Ajustes | `operating_unit` | `operating_unit_base` |
| 1.d | UO por defecto y permitidas por usuario; gerente ve todas | `operating_unit` | `operating_unit_base` |
| 2.a | UO en almacén | `stock_operating_unit` | `stock_operating_unit_segregation` |
| 2.b | UO en ubicación | `stock_operating_unit` | `stock_operating_unit_segregation` |
| 2.c | UO solicitante en transferencias | `stock_operating_unit` | `stock_operating_unit_segregation` |
| 2.d | Reglas de acceso por usuario | `stock_operating_unit` | `stock_operating_unit_segregation` (+ reglas faltantes) |
| 2.e | Consistencia de UO entre modelos | `stock_operating_unit` (restricciones) | `stock_operating_unit_segregation` (restricciones corregidas) |
| 2.f | Error del gerente con reglas de inventario de otras UO | Limitación conocida (ROADMAP del módulo) | Corregido, sección 7.1 |
| 3.a | UO en configuración del PdV, sólo visibilidad | `pos_operating_unit` | `pos_operating_unit_visibility` |
| 3.b | Restricción en sesiones, órdenes y pagos | `pos_operating_unit` | `pos_operating_unit_visibility` |
| 3.c | Campo *Punto de venta* en órdenes y pagos | `pos_operating_unit` | `pos_operating_unit_visibility` |
| 3.d | Varias UO autorizadas por PdV | `pos_operating_unit` | `pos_operating_unit_visibility` |
| 3.e | No propagar UO a contabilidad / inventario del PdV | Fuera de alcance del módulo | Se mantiene fuera de alcance |

### 2.6 Alternativa descartada: sucursales nativas (`res.company` con `parent_id`)

Odoo 17+ trae sucursales como compañías hijas. Se descarta porque:

- cada sucursal es una compañía: cambia `company_id` en almacenes, PdV, órdenes, pickings, diarios y
  secuencias, lo que obliga a una migración de datos masiva y riesgosa;
- afecta la numeración fiscal (NCF / e-CF) y los reportes DGII, que hoy trabajan por compañía;
- NC44 quiere inventario y contabilidad unificados; las sucursales empujan a separarlos.

La UO, en cambio, sólo agrega una dimensión de visibilidad encima de una compañía única.

---

## 3. Prerrequisitos

### 3.1 Inventario de módulos UO instalados en NC44 (bloqueante)

Antes de codificar hay que confirmar en la base de NC44 qué módulos de la familia UO están instalados.
El checkout local de NC44 trae en `OCA/operating-unit` muchos más módulos (`account_operating_unit`,
`purchase_operating_unit`, `sale_stock_operating_unit`, `hr_operating_unit`, …); si alguno está instalado,
también depende de `operating_unit` y debe resolverse antes de quitar el módulo base.

```sql
SELECT name, state, latest_version
  FROM ir_module_module
 WHERE name LIKE '%operating_unit%'
   AND state IN ('installed', 'to upgrade', 'to install')
 ORDER BY name;
```

| Resultado | Acción |
|---|---|
| Sólo `operating_unit`, `stock_operating_unit`, `pos_operating_unit` (y opcionalmente `operating_unit_access_all`) | Se sigue este manual tal cual. |
| Además `sale_operating_unit`, `purchase_operating_unit`, `account_operating_unit`, etc. | Decidir por módulo: desinstalar (si no se usa) o ampliar el alcance con un módulo propio equivalente. No se puede quitar la base mientras existan. |
| `operating_unit_access_all` instalado | Se absorbe en `operating_unit_base` (grupo *Access all Operating Units*, sección 4.4). |

Consultas complementarias para dimensionar los datos a validar después de la migración:

```sql
SELECT count(*) FROM operating_unit;
SELECT count(*) FROM operating_unit_users_rel;
SELECT count(*) FROM stock_warehouse WHERE operating_unit_id IS NOT NULL;
SELECT count(*) FROM stock_location  WHERE operating_unit_id IS NOT NULL;
SELECT count(*) FROM stock_picking   WHERE operating_unit_id IS NOT NULL;
SELECT count(*) FROM pos_config_operating_unit_rel;
SELECT count(*) FROM pos_order_operating_unit_rel;
SELECT count(*) FROM pos_order_line_operating_unit_rel;
SELECT count(*) FROM pos_payment_operating_unit_rel;
```

### 3.2 Entorno

- Contenedor `lfernandez_v19`, Postgres en `odoo-db`.
- Una copia anonimizada de la base de NC44 para ensayar la migración (sección 8).
- Base de pruebas limpia con `stock` y `point_of_sale` para desarrollar y correr la suite.

### 3.3 Conocimiento técnico

| Área | Nivel |
|---|---|
| ORM: herencia, campos calculados almacenados, `@api.constrains` | medio |
| `ir.rule`: reglas globales, contexto de evaluación, caché de dominios | **imprescindible** |
| Seguridad 19.0: `res.groups.privilege`, `group_ids` en usuarios | medio |
| Stock: almacenes, rutas/reglas, ubicaciones, quants | medio |
| PdV: `pos.config`, sesiones, `pos.load.mixin` | básico |
| SQL de migración sobre `ir_module_module` / `ir_model_data` | medio |

---

## 4. Módulo `operating_unit_base`

### 4.1 Estructura

```
operating_unit_base/
├── __init__.py
├── __manifest__.py
├── data/operating_unit_data.xml
├── i18n/es.po
├── models/
│   ├── __init__.py
│   ├── ir_rule.py
│   ├── operating_unit.py
│   └── res_users.py
├── security/
│   ├── ir.model.access.csv
│   └── operating_unit_security.xml
├── tests/
│   ├── __init__.py
│   ├── common.py
│   ├── test_operating_unit.py
│   └── test_res_users.py
└── views/
    ├── operating_unit_views.xml
    └── res_users_views.xml
```

### 4.2 Manifiesto

```python
{
    "name": "Operating Units",
    "summary": "Operating units inside a company and per-user access to them",
    "version": "19.0.1.0.0",
    "author": "Progressa",
    "website": "https://www.progressa.group",
    "category": "Hidden/Tools",
    "license": "LGPL-3",
    "depends": ["base"],
    "excludes": ["operating_unit", "operating_unit_access_all"],
    "data": [
        "security/operating_unit_security.xml",
        "security/ir.model.access.csv",
        "data/operating_unit_data.xml",
        "views/operating_unit_views.xml",
        "views/res_users_views.xml",
    ],
}
```

`excludes` impide instalar el módulo junto a los de OCA: en la migración los registros pasan de un módulo a
otro, nunca conviven.

### 4.3 Modelos

**`operating.unit`** — mismo `_name` y mismas columnas que OCA para no migrar datos.

```python
from odoo import api, fields, models


class OperatingUnit(models.Model):
    _name = "operating.unit"
    _description = "Operating Unit"
    _order = "code, name"
    _rec_names_search = ["name", "code"]

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        required=True,
        readonly=True,
        default=lambda self: self.env.company,
    )
    partner_id = fields.Many2one("res.partner", required=True)
    user_ids = fields.Many2many(
        "res.users",
        "operating_unit_users_rel",
        "operating_unit_id",
        "user_id",
        string="Users Allowed",
    )

    _code_company_uniq = models.Constraint(
        "unique (code, company_id)",
        "The code of the operating unit must be unique per company.",
    )
    _name_company_uniq = models.Constraint(
        "unique (name, company_id)",
        "The name of the operating unit must be unique per company.",
    )

    @api.depends("name", "code")
    def _compute_display_name(self):
        for unit in self:
            unit.display_name = f"[{unit.code}] {unit.name}"

    @api.model_create_multi
    def create(self, vals_list):
        units = super().create(vals_list)
        units.user_ids |= self.env.user
        self.env.registry.clear_cache()
        return units

    def write(self, vals):
        result = super().write(vals)
        if {"user_ids", "active", "company_id"} & vals.keys():
            self.env.registry.clear_cache()
        return result
```

Diferencias con OCA: el caché sólo se limpia cuando cambia algo que afecta el dominio de las reglas
(usuarios, activo, compañía), no en cada `write`.

**`res.users`**

| Campo | Tipo | Detalle |
|---|---|---|
| `assigned_operating_unit_ids` | M2M almacenado, tabla `operating_unit_users_rel` | Lo que el administrador asigna. |
| `operating_unit_ids` | M2M calculado (`compute_sudo`), con inverso | Lo que el usuario puede usar: todas las UO de las compañías activas si es gerente (o tiene *Access all*), si no las asignadas filtradas por compañías activas. Depende de `group_ids`, `assigned_operating_unit_ids` y del contexto `allowed_company_ids`. |
| `default_operating_unit_id` | M2O almacenado | Dominio: dentro de `operating_unit_ids` y de la compañía actual. |

```python
from odoo import api, fields, models
from odoo.fields import Domain


class ResUsers(models.Model):
    _inherit = "res.users"

    assigned_operating_unit_ids = fields.Many2many(
        "operating.unit",
        "operating_unit_users_rel",
        "user_id",
        "operating_unit_id",
        string="Operating Units",
        default=lambda self: self._default_operating_unit(),
    )
    operating_unit_ids = fields.Many2many(
        "operating.unit",
        compute="_compute_operating_unit_ids",
        inverse="_inverse_operating_unit_ids",
        string="Allowed Operating Units",
        compute_sudo=True,
    )
    default_operating_unit_id = fields.Many2one(
        "operating.unit",
        string="Default Operating Unit",
        default=lambda self: self._default_operating_unit(),
        domain="[('id', 'in', operating_unit_ids), ('company_id', '=', current_company_id)]",
    )

    def _has_all_operating_units(self):
        self.ensure_one()
        return self.has_group(
            "operating_unit_base.group_manager_operating_unit"
        ) or self.has_group("operating_unit_base.group_all_operating_unit")

    @api.depends("group_ids", "assigned_operating_unit_ids")
    @api.depends_context("allowed_company_ids")
    def _compute_operating_unit_ids(self):
        company_ids = self.env.context.get("allowed_company_ids")
        domain = (
            Domain("company_id", "in", company_ids) if company_ids else Domain.TRUE
        )
        all_units = self.env["operating.unit"].search(domain)
        for user in self:
            user.operating_unit_ids = (
                all_units
                if user._has_all_operating_units()
                else user.assigned_operating_unit_ids.filtered_domain(domain)
            )

    def _inverse_operating_unit_ids(self):
        for user in self:
            user.assigned_operating_unit_ids = user.operating_unit_ids
        self.env.registry.clear_cache()

    @api.model
    def _default_operating_unit(self):
        user = self.env.user
        if user.default_operating_unit_id.sudo().company_id in self.env.companies:
            return user.default_operating_unit_id
        units = user.assigned_operating_unit_ids.sudo()
        return (
            units.filtered(lambda unit: unit.company_id == self.env.company)[:1]
            or units.filtered(lambda unit: unit.company_id in self.env.companies)[:1]
        )

    @api.onchange("operating_unit_ids")
    def _onchange_operating_unit_ids(self):
        for user in self:
            if user.default_operating_unit_id not in user.operating_unit_ids._origin:
                user.default_operating_unit_id = False

    def operating_units(self):
        return self.env.user.operating_unit_ids
```

Se conserva `operating_units()` porque la usa el contexto de reglas y facilita portar extensiones futuras.

También se conserva el `default_get` de OCA que copia las UO del usuario plantilla
(`base.default_user`) cuando *Derechos de acceso por defecto* está activo.

**`ir.rule`**

```python
from odoo import api, models


class IrRule(models.Model):
    _inherit = "ir.rule"

    @api.model
    def _eval_context(self):
        context = super()._eval_context()
        context.update(
            operating_unit_ids=self.env.user.operating_units().ids,
            operating_unit_id=self.env.user.default_operating_unit_id.id,
        )
        return context
```

`_compute_domain` está en `ormcache` por `uid` + `allowed_company_ids`; por eso todo cambio en las UO de un
usuario, en los grupos de UO o en las UO mismas debe limpiar el caché del registro. Sin esa limpieza el
usuario sigue viendo con los permisos anteriores hasta reiniciar el servidor. Esto se cubre con un test
(sección 9).

### 4.4 Seguridad

`security/operating_unit_security.xml` — se conservan **los mismos ids XML** que OCA para que, al renombrar
el módulo, los registros existentes (grupos, reglas, categoría) se reconozcan y no se dupliquen:

| id XML | Tipo | Nota |
|---|---|---|
| `module_operating_units` | `ir.module.category` | *Operating Units* |
| `res_groups_privilege_operating_units` | `res.groups.privilege` | |
| `group_multi_operating_unit` | `res.groups` | *Multiple Operating Unit* |
| `group_manager_operating_unit` | `res.groups` | implica el anterior; root y admin |
| `operating_unit_comp_rule` | `ir.rule` | multi-compañía |
| `ir_rule_operating_unit_allowed_operating_units` | `ir.rule` | `[('id','in',operating_unit_ids)]` |
| `group_all_operating_unit` | `res.groups` | absorbe `operating_unit_access_all`: ve todas las UO sin ser gerente |

Con `group_all_operating_unit` incluido en `_has_all_operating_units`, la regla
`ir_rule_operating_unit_allowed_operating_units` no necesita el `write` de dominio que hace OCA en
`operating_unit_access_all`.

`ir.model.access.csv`: lectura para `base.group_user` y `group_multi_operating_unit`, CRUD para
`group_manager_operating_unit` (igual que hoy).

### 4.5 Vistas y menús

- Lista, formulario y búsqueda de `operating.unit`; menú *Ajustes → Usuarios y compañías → Unidades
  operativas*, visible para `group_manager_operating_unit`.
- Bloque *Unidades operativas* en la pestaña *Permisos de acceso* de `res.users`
  (`//page[@name='access_rights']/group[1]`), con `operating_unit_ids` (`many2many_tags`) y
  `default_operating_unit_id`, visible para `group_multi_operating_unit`.
- Traducción `i18n/es.po` completa desde el primer commit (hoy las pantallas base salen en inglés).

### 4.6 Datos

`data/operating_unit_data.xml` (`noupdate="1"`): `main_operating_unit` (`OU1`, partner `base.main_partner`)
asignada a `base.user_root` y `base.user_admin`. Mismo id XML que OCA; en NC44 el registro ya existe y
`noupdate` evita sobreescribir el nombre que le hayan puesto.

---

## 5. Módulo `stock_operating_unit_segregation`

### 5.1 Manifiesto

```python
{
    "name": "Inventory by Operating Unit",
    "version": "19.0.1.0.0",
    "author": "Progressa",
    "website": "https://www.progressa.group",
    "category": "Inventory/Inventory",
    "license": "LGPL-3",
    "depends": ["stock", "operating_unit_base"],
    "excludes": ["stock_operating_unit", "stock_operating_unit_access_all"],
    "data": [
        "security/stock_security.xml",
        "data/stock_data.xml",
        "views/stock_warehouse_views.xml",
        "views/stock_location_views.xml",
        "views/stock_picking_views.xml",
        "views/stock_move_views.xml",
        "views/stock_quant_views.xml",
    ],
}
```

### 5.2 Modelos

**`stock.warehouse`**

```python
from odoo import api, fields, models


class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    operating_unit_id = fields.Many2one(
        "operating.unit",
        default=lambda self: self._default_operating_unit(),
        check_company=True,
        index=True,
    )

    @api.model
    def _default_operating_unit(self, company=None):
        company = company or self.env.company
        user = self.env.user
        default_unit = user.default_operating_unit_id.sudo()
        if default_unit.company_id == company:
            return default_unit
        return user.operating_unit_ids.sudo().filtered(
            lambda unit: unit.company_id == company
        )[:1]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if "operating_unit_id" not in vals and vals.get("company_id"):
                company = self.env["res.company"].browse(vals["company_id"])
                vals["operating_unit_id"] = self._default_operating_unit(company).id
        warehouses = super().create(vals_list)
        warehouses._sync_operating_unit_to_locations()
        return warehouses

    def write(self, vals):
        result = super().write(vals)
        if "operating_unit_id" in vals:
            self._sync_operating_unit_to_locations()
        return result

    def _sync_operating_unit_to_locations(self):
        for warehouse in self:
            internal_locations = self.env["stock.location"].search(
                [
                    ("id", "child_of", warehouse.view_location_id.id),
                    ("usage", "=", "internal"),
                ]
            )
            internal_locations.write({"operating_unit_id": warehouse.operating_unit_id.id})
```

`_sync_operating_unit_to_locations` es nuevo: hoy, al crear un almacén con UO, sus ubicaciones internas
quedan sin UO (visibles para todos) hasta que alguien las edita una por una. Al propagar desde el almacén
desaparece ese hueco y la restricción de la 5.3 deja de dispararse al cambiar la UO de un almacén.

**`stock.location`**

| Campo | Detalle |
|---|---|
| `operating_unit_id` | M2O, `check_company`, `index=True`. Por defecto la del padre si el padre es interno. |

Restricciones (con `ValidationError`, no `UserError` como hoy):

1. Sólo ubicaciones `internal` llevan UO. OCA sólo prohíbe `supplier` y `customer`; se amplía a todo uso
   distinto de `internal` (tránsito, inventario, producción, vista) para que esas ubicaciones sigan
   compartidas.
2. Una ubicación interna con padre interno debe tener la misma UO que el padre.
3. Las ubicaciones `lot_stock_id`, `wh_input_stock_loc_id`, `wh_output_stock_loc_id` de un almacén con UO
   deben tener la UO del almacén. Se corrige el error de OCA, que buscaba con `rec.ids[0]` en vez de
   `rec.id` y validaba mal al escribir varias ubicaciones a la vez.

```python
@api.constrains("operating_unit_id")
def _check_warehouse_operating_unit(self):
    warehouses = self.env["stock.warehouse"].search(
        [
            "|", "|",
            ("lot_stock_id", "in", self.ids),
            ("wh_input_stock_loc_id", "in", self.ids),
            ("wh_output_stock_loc_id", "in", self.ids),
        ]
    )
    for warehouse in warehouses.filtered("operating_unit_id"):
        own_locations = (
            warehouse.lot_stock_id
            | warehouse.wh_input_stock_loc_id
            | warehouse.wh_output_stock_loc_id
        ) & self
        if own_locations.filtered(
            lambda location: location.operating_unit_id != warehouse.operating_unit_id
        ):
            raise ValidationError(
                self.env._(
                    "Location %(locations)s belongs to warehouse %(warehouse)s, "
                    "whose operating unit is %(unit)s.",
                    locations=", ".join(own_locations.mapped("complete_name")),
                    warehouse=warehouse.display_name,
                    unit=warehouse.operating_unit_id.display_name,
                )
            )
```

**`stock.picking`**

| Campo | Detalle |
|---|---|
| `operating_unit_id` | *UO solicitante*. Calculado y almacenado desde `picking_type_id.warehouse_id.operating_unit_id`, `readonly=False`, `index=True`, `check_company`. |

```python
@api.depends("picking_type_id")
def _compute_operating_unit_id(self):
    for picking in self:
        picking.operating_unit_id = picking.picking_type_id.warehouse_id.operating_unit_id
```

Corrección: OCA no asigna nada cuando no hay tipo de operación; en un campo calculado almacenado eso deja el
valor indefinido. Aquí siempre se asigna.

Restricción: si el almacén del tipo de operación tiene UO, la del picking debe ser igual.

**`stock.move` / `stock.move.line`**

| Campo | Detalle |
|---|---|
| `operating_unit_id` | Relacionado `location_id.operating_unit_id` (*UO de origen*). |
| `operating_unit_dest_id` | Relacionado `location_dest_id.operating_unit_id` (*UO de destino*). |

Restricción en `stock.move`: si el picking tiene UO, el origen o el destino del movimiento debe ser de esa
UO, salvo que ambas ubicaciones sean compartidas (sin UO). Se conserva la semántica de OCA y se escribe sin
la comparación cruzada ambigua:

```python
@api.constrains("picking_id", "location_id", "location_dest_id")
def _check_stock_move_operating_unit(self):
    for move in self.filtered("picking_id.operating_unit_id"):
        picking_unit = move.picking_id.operating_unit_id
        move_units = move.operating_unit_id | move.operating_unit_dest_id
        if move_units and picking_unit not in move_units:
            raise ValidationError(
                self.env._(
                    "Move %(move)s must leave from or arrive at a location of "
                    "operating unit %(unit)s.",
                    move=move.display_name,
                    unit=picking_unit.display_name,
                )
            )
```

**`stock.quant`**: `operating_unit_id` relacionado y almacenado desde `location_id.operating_unit_id`,
`index=True` (lo usa la regla de acceso sobre tablas grandes).

**`stock.rule`**: `operating_unit_id` relacionado con `warehouse_id.operating_unit_id`, almacenado e
indexado para poder filtrarlo en la regla de la 7.1.

**`stock.warehouse.orderpoint`**: `operating_unit_id` relacionado con `warehouse_id.operating_unit_id`,
almacenado. Restricción: UO del almacén = UO de la ubicación, sólo cuando ambos tienen UO (OCA falla cuando
la ubicación es compartida).

### 5.3 Reglas de acceso

Todas globales y de **lectura**, criterio "sin UO o UO permitida". Mismos ids XML que OCA (sección 8).

| id XML | Modelo | Dominio |
|---|---|---|
| `ir_rule_stock_warehouse_allowed_operating_units` | `stock.warehouse` | `['|', ('operating_unit_id','=',False), ('operating_unit_id','in',operating_unit_ids)]` |
| `ir_rule_stock_picking_type_allowed_operating_units` | `stock.picking.type` | `['|', ('warehouse_id.operating_unit_id','=',False), ('warehouse_id.operating_unit_id','in',operating_unit_ids)]` |
| `ir_rule_stock_location_allowed_operating_units` | `stock.location` | `['|', ('operating_unit_id','=',False), ('operating_unit_id','in',operating_unit_ids)]` |
| `ir_rule_stock_move_allowed_operating_units` | `stock.move` | origen sin UO o permitida **y** destino sin UO o permitido (igual que hoy) |
| `ir_rule_stock_move_line_allowed_operating_units` | `stock.move.line` | idem |
| `ir_rule_stock_picking_allowed_operating_units` | `stock.picking` | `['|', ('operating_unit_id','=',False), ('operating_unit_id','in',operating_unit_ids)]` |
| `ir_rule_stock_picking_allowed_picking_type_operating_units` | `stock.picking` | por `picking_type_id.warehouse_id.operating_unit_id` |
| `ir_rule_stock_quant_allowed_operating_units` | `stock.quant` | por `operating_unit_id` |
| **nueva** `ir_rule_stock_rule_allowed_operating_units` | `stock.rule` | `['|', ('operating_unit_id','=',False), ('operating_unit_id','in',operating_unit_ids)]` |
| **nueva** `ir_rule_stock_orderpoint_allowed_operating_units` | `stock.warehouse.orderpoint` | por `operating_unit_id` |

Nota sobre `stock.picking.type`: en el dominio de OCA `('warehouse_id','=',False)` sobra, porque
`warehouse_id.operating_unit_id = False` ya es verdadero cuando no hay almacén. Se simplifica.

Nota sobre `stock.move` y transferencias entre UO: un usuario de la UO A no ve un movimiento A→B si no tiene
acceso a B. Es el comportamiento actual y el manual de usuario lo documenta; no se cambia sin pedido
explícito de NC44.

### 5.4 Datos

`data/stock_data.xml` (`noupdate="1"`): `stock.warehouse0` y `stock.stock_location_stock` a
`operating_unit_base.main_operating_unit`. En NC44 estos registros ya tienen UO; `noupdate` los respeta.

### 5.5 Vistas

Mismo alcance que hoy, con el grupo `operating_unit_base.group_multi_operating_unit`:

- Almacén: formulario (tras `company_id`) y lista.
- Ubicación: formulario (grupo `additional_info`), lista y búsqueda.
- Transferencia: lista (tras `origin`), formulario (grupo `other_infos`, sólo editable en borrador),
  búsqueda (campo + agrupar por UO).
- Movimientos: `view_move_tree`, `view_picking_move_tree`, `view_move_tree_receipt_picking`,
  `view_move_form`, con UO de origen y destino.
- Nuevo: columna y filtro de UO en `stock.quant` (*Inventario físico*) y en reglas de abastecimiento.

---

## 6. Módulo `pos_operating_unit_visibility`

### 6.1 Manifiesto

```python
{
    "name": "Point of Sale by Operating Unit",
    "version": "19.0.1.0.0",
    "author": "Progressa",
    "website": "https://www.progressa.group",
    "category": "Sales/Point of Sale",
    "license": "LGPL-3",
    "depends": ["point_of_sale", "operating_unit_base"],
    "excludes": ["pos_operating_unit"],
    "data": [
        "security/pos_security.xml",
        "views/pos_config_views.xml",
        "views/pos_order_views.xml",
        "views/pos_payment_views.xml",
        "views/res_config_settings_views.xml",
    ],
}
```

No depende de `stock_operating_unit_segregation`: el PdV de NC44 descarga de un inventario centralizado, como
pide la tarea.

### 6.2 Modelos

| Modelo | Campo | Diseño |
|---|---|---|
| `pos.config` | `operating_unit_ids` | M2M almacenado, tabla `pos_config_operating_unit_rel` (igual que hoy). |
| `res.config.settings` | `pos_operating_unit_ids` | Relacionado `pos_config_id.operating_unit_ids`, `readonly=False`. |
| `pos.session` | `operating_unit_ids` | M2M almacenado, tabla `pos_session_operating_unit_rel`. Se copia del PdV al abrir la sesión y no cambia después. |
| `pos.order` | `operating_unit_ids` | M2M almacenado, tabla `pos_order_operating_unit_rel`. Calculado almacenado desde `session_id.operating_unit_ids` (no desde el PdV), sin dependencia hacia el PdV. |
| `pos.order.line` | `operating_unit_ids` | **Relacionado** `order_id.operating_unit_ids`, no almacenado. |
| `pos.payment` | `operating_unit_ids` | **Relacionado** `pos_order_id.operating_unit_ids`, no almacenado. |
| `pos.payment` | `config_id` | Relacionado `session_id.config_id`, **almacenado** e indexado (columna *Punto de venta*, filtros y agrupaciones). |

```python
from odoo import Command, api, fields, models


class PosSession(models.Model):
    _inherit = "pos.session"

    operating_unit_ids = fields.Many2many(
        "operating.unit",
        "pos_session_operating_unit_rel",
        string="Operating Units",
        readonly=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        configs = self.env["pos.config"].sudo().browse(
            [vals["config_id"] for vals in vals_list if vals.get("config_id")]
        )
        units_by_config = {config.id: config.operating_unit_ids.ids for config in configs}
        for vals in vals_list:
            if vals.get("config_id"):
                vals["operating_unit_ids"] = [
                    Command.set(units_by_config[vals["config_id"]])
                ]
        return super().create(vals_list)


class PosOrder(models.Model):
    _inherit = "pos.order"

    operating_unit_ids = fields.Many2many(
        "operating.unit",
        "pos_order_operating_unit_rel",
        string="Operating Units",
        compute="_compute_operating_unit_ids",
        store=True,
    )

    @api.depends("session_id")
    def _compute_operating_unit_ids(self):
        for order in self:
            order.operating_unit_ids = order.session_id.operating_unit_ids
```

Por qué cambia el diseño de líneas y pagos respecto de OCA:

- OCA guarda una fila por línea de orden en `pos_order_line_operating_unit_rel` y otra por pago en
  `pos_payment_operating_unit_rel`. En un PdV con volumen esas tablas crecen tanto como las líneas, y cada
  `create` hace un `browse` por línea.
- La UO de una línea o de un pago siempre es la de su orden, que ya está "congelada" desde la sesión. Un
  campo relacionado da el mismo resultado de visibilidad sin duplicar datos.
- Las reglas de líneas y pagos filtran por `order_id.operating_unit_ids` / `pos_order_id.operating_unit_ids`
  (JOIN indexado).

La sesión es el punto de congelamiento: si se cambian las UO de un PdV, las sesiones y órdenes ya creadas
conservan las suyas, igual que hoy.

### 6.3 Reglas de acceso

Globales, de lectura, mismos ids XML que OCA.

| id XML | Modelo | Dominio |
|---|---|---|
| `ir_rule_pos_config_allowed_operating_units` | `pos.config` | `['|', ('operating_unit_ids','=',False), ('operating_unit_ids','in',operating_unit_ids)]` |
| `ir_rule_pos_session_allowed_operating_units` | `pos.session` | idem |
| `ir_rule_pos_order_allowed_operating_units` | `pos.order` | idem |
| `ir_rule_pos_order_line_allowed_operating_units` | `pos.order.line` | por `order_id.operating_unit_ids` |
| `ir_rule_pos_payment_allowed_operating_units` | `pos.payment` | por `pos_order_id.operating_unit_ids` |
| `ir_rule_report_pos_order_allowed_operating_units` | `report.pos.order` | por `config_id.operating_unit_ids` |

### 6.4 Vistas

- `pos.config`: ajuste *Unidades operativas* antes de `other_devices` (`many2many_tags`, `no_create`),
  visible y editable sólo con `group_manager_operating_unit`.
- *Punto de venta → Configuración → Ajustes*: bloque *Unidades operativas* antes de `pos_payment_section`.
- `pos.order`: columnas *Punto de venta* (`config_id`) y *Unidades operativas* en lista y formulario; filtro y
  agrupar por UO.
- `pos.payment`: columnas *Punto de venta* y *Unidades operativas* en lista y formulario; agrupar por PdV.

### 6.5 Interfaz del PdV (frontend)

No se requiere código JS. La sesión del PdV carga sus datos con `pos.load.mixin`, que respeta las reglas del
usuario: un cajero sólo puede abrir los PdV que ve. Se verifica con un tour (sección 9).

---

## 7. Correcciones respecto del comportamiento actual

### 7.1 Error del gerente con reglas de inventario de otras UO

**Síntoma (ROADMAP de `stock_operating_unit`):** un responsable de inventario ve en *Rutas* las reglas
(`stock.rule`) de otras UO; al abrir una recibe un error de acceso.

**Causa:** `stock.rule` no tiene regla de acceso por UO, pero los registros que referencia sí:
`location_src_id`, `location_dest_id`, `picking_type_id` y `warehouse_id` son de otra UO y el usuario no
puede leerlos. La lista se muestra; el formulario falla al leer esos campos. Lo mismo ocurre con
`stock.warehouse.orderpoint` de otras UO.

**Corrección:**

1. `stock.rule.operating_unit_id` pasa a almacenado e indexado.
2. Nuevas reglas globales sobre `stock.rule` y `stock.warehouse.orderpoint` (tabla 5.3): el usuario deja de
   ver lo que no puede abrir.
3. `stock.route` sigue compartida (una ruta puede servir a varios almacenes); su `one2many` de reglas se
   filtra solo por la nueva regla.
4. Los gerentes de UO (`group_manager_operating_unit`) ven todas las UO, así que ven y editan todo.
5. Test que reproduce el error (abrir con `web_read` una regla de otra UO) y queda en verde con la
   corrección.

### 7.2 Lista de correcciones técnicas

| # | Dónde | Hoy | Corregido |
|---|---|---|---|
| 1 | `stock.location._check_warehouse_operating_unit` | Busca con `rec.ids[0]`: valida mal en escrituras múltiples | Busca con `self.ids` y compara por almacén |
| 2 | `stock.location._check_required_operating_unit` | Sólo prohíbe UO en proveedor/cliente | Sólo `internal` lleva UO |
| 3 | `stock.picking._compute_operating_unit_id` | No asigna valor sin tipo de operación | Siempre asigna |
| 4 | `stock.warehouse.orderpoint._check_location` | Falla con ubicación compartida | Sólo valida si ambos tienen UO |
| 5 | Restricciones de stock | `UserError` | `ValidationError` con nombres de los registros |
| 6 | Almacén nuevo con UO | Ubicaciones internas quedan sin UO | Se propaga a ubicaciones internas |
| 7 | `operating.unit.write` | Limpia el caché del registro en cada escritura | Sólo si cambian usuarios, activo o compañía |
| 8 | `pos.order.line` / `pos.payment` | M2M propio por línea y pago | Relacionado con la orden |
| 9 | `pos.payment.config_id` | No almacenado: no se puede agrupar | Almacenado e indexado |
| 10 | `operating_unit_access_all` | Módulo aparte que reescribe una regla | Grupo dentro del módulo base |
| 11 | Pantallas base | Sin traducción al español | `es.po` completo en los tres módulos |

---

## 8. Migración de NC44 (de OCA/store-addons a los módulos propios)

Como el modelo, los campos, las tablas y los ids XML son los mismos, la migración consiste en **renombrar
los módulos** en la base y actualizar. No se copian datos.

### 8.1 Mapa de módulos

| Antes | Después |
|---|---|
| `operating_unit` | `operating_unit_base` |
| `operating_unit_access_all` (si está) | se fusiona en `operating_unit_base` |
| `stock_operating_unit` | `stock_operating_unit_segregation` |
| `pos_operating_unit` | `pos_operating_unit_visibility` |

### 8.2 Script de renombrado

Se entrega como `odoo-pro/scripts/migrate_operating_unit_to_own_modules.sql` y se ejecuta **una sola vez**,
con el servidor detenido, después del respaldo. Reproduce lo que hace `util.rename_module` de
`upgrade-util` sin depender del entorno del upgrade.

Antes de correrlo, si los módulos nuevos ya aparecen en *Aplicaciones* (por *Actualizar lista de
aplicaciones*), se elimina su fila `uninstalled`; si no, el `UPDATE` choca con el índice único de
`ir_module_module.name`.

```sql
BEGIN;

DELETE FROM ir_module_module
 WHERE name IN ('operating_unit_base',
                'stock_operating_unit_segregation',
                'pos_operating_unit_visibility')
   AND state = 'uninstalled';

CREATE TEMP TABLE ou_module_map (old varchar, new varchar) ON COMMIT DROP;
INSERT INTO ou_module_map VALUES
    ('operating_unit', 'operating_unit_base'),
    ('stock_operating_unit', 'stock_operating_unit_segregation'),
    ('pos_operating_unit', 'pos_operating_unit_visibility');

UPDATE ir_module_module m
   SET name = map.new
  FROM ou_module_map map
 WHERE m.name = map.old;

UPDATE ir_module_module_dependency d
   SET name = map.new
  FROM ou_module_map map
 WHERE d.name = map.old;

UPDATE ir_model_data d
   SET module = map.new
  FROM ou_module_map map
 WHERE d.module = map.old;

UPDATE ir_model_data d
   SET name = 'module_' || map.new
  FROM ou_module_map map
 WHERE d.module = 'base'
   AND d.model = 'ir.module.module'
   AND d.name = 'module_' || map.old;

UPDATE ir_ui_view v
   SET key = map.new || substr(v.key, length(map.old) + 1)
  FROM ou_module_map map
 WHERE v.key LIKE map.old || '.%';

COMMIT;
```

Si `operating_unit_access_all` está instalado, se agrega un paso previo que mueve sus ids XML a
`operating_unit` (`group_all_operating_unit`, `res_groups_privilege_all_operating_units`) y marca el módulo
como `uninstalled`; su único efecto en datos era reescribir el dominio de una regla, que el módulo nuevo
vuelve a escribir al actualizarse.

### 8.3 Cambios en `odoo-pro` / addons path

1. Mergear los tres módulos nuevos en `odoo-pro` (rama 19.0).
2. Quitar `store-addons/stock_operating_unit` y `store-addons/pos_operating_unit` del repositorio de
   `store-addons` cuando ningún cliente los use (Mercalmacén también los tiene; ver 8.6).
3. El submódulo `OCA/operating-unit` puede seguir en el addons path para otros clientes: `excludes` impide
   instalar ambos.

### 8.4 Secuencia en producción

1. Respaldo completo (base + filestore) desde Odoo.sh.
2. Correr las consultas de 3.1 y guardar los conteos.
3. Detener el servidor.
4. Ejecutar el script 8.2.
5. `odoo -d <db> -u operating_unit_base,stock_operating_unit_segregation,pos_operating_unit_visibility --stop-after-init`.
6. Script post-actualización (en `migrations/19.0.1.0.0/post-migrate.py` de
   `pos_operating_unit_visibility`): borrar las tablas `pos_order_line_operating_unit_rel` y
   `pos_payment_operating_unit_rel` que ya no usa ningún campo, **sólo** después de verificar que las
   órdenes tienen UO.
7. Script post-actualización de `stock_operating_unit_segregation`: llenar `stock_rule.operating_unit_id`,
   `stock_warehouse_orderpoint.operating_unit_id` y `pos_payment.config_id` (columnas nuevas almacenadas)
   con un `UPDATE … FROM` en SQL, no con el ORM, para no recalcular registro por registro.
8. Repetir las consultas de 3.1 y comparar con los conteos guardados.
9. Prueba de humo con un usuario de cada UO (sección 9.3).
10. Levantar el servidor.

### 8.5 Reversión

Restaurar el respaldo del paso 1. No hay reversión parcial: el renombrado es atómico pero la actualización
posterior no.

### 8.6 Otros clientes

`store-addons` tiene los mismos ports para Mercalmacén. Al estar en 19.0, el mismo script les aplica; se
evalúa por separado y no forma parte de esta entrega.

### 8.7 Próximas migraciones de versión

Con los módulos propios, la migración a 20.0 entra en el flujo normal de `odoo-pro`: se portan junto con el
resto, con tests propios, sin esperar a OCA. El script 8.2 no se vuelve a usar.

---

## 9. Plan de pruebas

### 9.1 Tests automáticos (por módulo, `post_install`, `-at_install`)

`tests/common.py` en el módulo base: compañía, dos UO (`SDQ`, `STI`), usuario gerente, usuario sólo SDQ,
usuario sólo STI; reutilizado por los otros dos módulos.

**`operating_unit_base`**

| Test | Verifica |
|---|---|
| `test_unique_code_per_company` | Restricciones de unicidad |
| `test_manager_sees_all_units` | Gerente → todas las UO de las compañías activas |
| `test_all_units_group` | Grupo *Access all* sin ser gerente |
| `test_user_sees_assigned_units` | Usuario normal → sólo asignadas |
| `test_units_follow_allowed_companies` | Cambio de `allowed_company_ids` cambia `operating_unit_ids` |
| `test_rule_cache_invalidated` | Quitar una UO al usuario y leer de inmediato: deja de verla sin reiniciar |
| `test_default_unit_cleared_when_removed` | `default_operating_unit_id` se vacía si sale de las permitidas |
| `test_creator_linked_to_new_unit` | Quien crea una UO queda asignado |

**`stock_operating_unit_segregation`**

| Test | Verifica |
|---|---|
| `test_warehouse_default_unit` | UO por defecto del usuario al crear almacén |
| `test_warehouse_unit_propagates_to_locations` | Corrección 7.2 #6 |
| `test_only_internal_locations_have_unit` | Corrección 7.2 #2 |
| `test_child_location_same_unit` | Hijo = padre |
| `test_warehouse_locations_multi_write` | Corrección 7.2 #1 |
| `test_picking_unit_from_picking_type` | UO solicitante calculada |
| `test_picking_unit_mismatch_rejected` | Restricción picking vs almacén |
| `test_move_outside_picking_unit_rejected` | Restricción de movimientos |
| `test_inter_unit_transfer` | A→B válido; visibilidad según 5.3 |
| `test_user_sees_only_own_records` | Almacenes, tipos, ubicaciones, pickings, moves, move lines, quants |
| `test_stock_rule_other_unit_hidden` | Corrección 7.1: `web_read` sin error; reglas de otra UO no visibles |
| `test_orderpoint_rules` | Restricción y visibilidad de reabastecimiento |
| `test_manager_edits_rule_of_any_unit` | Gerente edita reglas de cualquier UO |

**`pos_operating_unit_visibility`**

| Test | Verifica |
|---|---|
| `test_session_takes_config_units` | Sesión congela UO del PdV |
| `test_order_takes_session_units` | Orden desde la sesión |
| `test_lines_and_payments_follow_order` | Relacionados |
| `test_units_frozen_after_config_change` | Cambiar UO del PdV no altera sesiones/órdenes previas |
| `test_cashier_sees_only_own_pos` | `pos.config`, `pos.session`, `pos.order`, `pos.order.line`, `pos.payment`, `report.pos.order` |
| `test_pos_without_units_visible_to_all` | Comportamiento actual |
| `test_only_manager_edits_pos_units` | Grupo en la vista de ajustes |
| Tour `pos_operating_unit_visibility_cashier` | Cajero STI abre su PdV, vende, cierra; no ve el PdV SDQ en el tablero |

Comando:

```bash
docker exec lfernandez_v19 odoo -d test_v19_operating_unit_base \
  -i operating_unit_base,stock_operating_unit_segregation,pos_operating_unit_visibility \
  --test-tags /operating_unit_base,/stock_operating_unit_segregation,/pos_operating_unit_visibility \
  --stop-after-init --http-port=8070
```

### 9.2 Test de migración

Sobre una copia de la base de NC44:

1. Guardar conteos de 3.1 y, por cada usuario activo, cuántos almacenes, pickings, quants, PdV y órdenes ve
   (`search_count` con `with_user`).
2. Ejecutar 8.4 pasos 4–7.
3. Repetir y comparar. Toda diferencia debe estar explicada por las correcciones de la sección 7
   (p. ej. reglas de stock de otra UO que ahora no se ven).

### 9.3 Aceptación funcional

Los escenarios de los manuales de usuario existentes (`docs/manuals/stock_operating_unit`,
`docs/manuals/pos_operating_unit`) con los módulos nuevos, más:

- un responsable de inventario sin rol de gerente de UO abre *Inventario → Configuración → Rutas* y ninguna
  regla visible da error;
- un PdV con dos UO es visible para usuarios de cualquiera de las dos;
- los asientos y valoración del PdV y del inventario siguen centralizados (sin UO).

Los manuales de usuario se regeneran con `tools/manual-generator` sobre la base de pruebas, cambiando los
nombres de módulo en `configs/stock_operating_unit.json` y `configs/pos_operating_unit.json`.

---

## 10. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| NC44 tiene instalados otros módulos `*_operating_unit` | Prerrequisito 3.1 bloqueante; ampliar alcance o desinstalar antes de migrar |
| Algún módulo propio o de NC44 referencia `operating_unit.group_*` por id XML | `grep -rn "operating_unit\." odoo-pro nc44-addons` antes de migrar y actualizar las referencias en el mismo despliegue |
| Filas `uninstalled` de los módulos nuevos chocan con el renombrado | Paso `DELETE` al inicio del script 8.2 |
| Caché de reglas desactualizado tras cambiar UO de usuarios | `clear_cache()` en los puntos de la sección 4.3 y test dedicado |
| Rendimiento de reglas sobre `stock.move.line` / `stock.quant` | Índices en `operating_unit_id` almacenados; medir con `EXPLAIN ANALYZE` en la copia de NC44 |
| Personalizaciones de NC44 sobre las vistas de OCA (herencias con `inherit_id` a vistas de `operating_unit`) | Las vistas conservan id XML y quedan bajo el módulo nuevo por el renombrado; revisar herencias en `nc44-addons` |
| Diferencias visibles para usuarios por las correcciones | Comunicar el cambio de la sección 7 en la entrega |

---

## 11. Fuera de alcance

- Propagar la UO a asientos, facturas, diarios, secuencias o valoración de inventario
  (`account_operating_unit`, `stock_account_operating_unit`). NC44 mantiene contabilidad centralizada.
- UO en productos, contactos, ventas, compras, CRM, RR. HH. o proyectos.
- P&L y balance por UO.
- Cambiar la visibilidad de transferencias entre UO.

Si en el futuro se necesitan, cada uno se diseña como módulo propio `<app>_operating_unit_<función>` sobre
`operating_unit_base`, con el mismo patrón: campo `operating_unit_id`, regla global "sin UO o UO
permitida" y restricciones de coherencia con los documentos de origen.

---

## 12. Checklist de entrega

- [ ] Resultado de la consulta 3.1 en NC44 adjunto a la tarea y alcance confirmado.
- [ ] `operating_unit_base`, `stock_operating_unit_segregation`, `pos_operating_unit_visibility` en
      `odoo-pro` 19.0, con `excludes` hacia los módulos de OCA.
- [ ] Mismos nombres de modelo, campos, tablas e ids XML que los módulos reemplazados.
- [ ] Correcciones de la sección 7 implementadas, cada una con su test.
- [ ] Suite de tests en verde en los tres módulos.
- [ ] `i18n/es.po` completo en los tres módulos.
- [ ] Script `scripts/migrate_operating_unit_to_own_modules.sql` y scripts post-migración.
- [ ] Ensayo de migración sobre copia de NC44 con conteos antes/después comparados.
- [ ] Referencias a `operating_unit.*` en `nc44-addons` y `odoo-pro` actualizadas.
- [ ] Manuales de usuario regenerados con los módulos nuevos.
- [ ] PR con descripción técnica enlazado en la tarea #76295.
