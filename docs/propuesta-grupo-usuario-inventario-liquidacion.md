# Propuesta técnica — Grupo de seguridad "Usuario Inventario + Liquidación"

**Fecha:** 2026-08-18
**Rama base:** `17.0` (`odoo-pro`)
**Módulos afectados:** `stock_landed_costs_features`, `stock_landed_costs_file`
**Autor del análisis:** equipo de desarrollo Indexa / Progressa

---

## 1. Solicitud del cliente

> El módulo de liquidación actualmente solo funciona para los usuarios que tienen *Inventario / Administrador*. Esto genera una situación de seguridad complicada, ya que no necesariamente estos usuarios deberían poder validar conduces de entrada.
>
> Solicitan cambiar el código Python y lo que corresponda para que el módulo funcione con un grupo nuevo llamado **"Usuario Inventario + Liquidación"**, que tenga los accesos base del usuario de Inventario + todo lo que haga falta para liquidar.

El diagnóstico del cliente es correcto: hoy la liquidación **exige** `stock.group_stock_manager` (Inventario / Administrador). Este documento detalla el porqué, el diseño propuesto y el listado exacto de cambios por archivo.

---

## 2. Alcance real de "el módulo de liquidación"

La funcionalidad no vive en un solo módulo. Son tres capas:

| Capa | Módulo | Modelos propios |
|---|---|---|
| Núcleo Odoo | `stock_landed_costs` (LGPL, core) | `stock.landed.cost`, `stock.landed.cost.lines`, `stock.valuation.adjustment.lines` |
| Indexa | `stock_landed_costs_features` | `stock.landed.cost.run`, `stock.landed.cost.product`, `stock.valuation.adjustment.summary` |
| Indexa | `stock_landed_costs_file` | `stock.landed.cost.file` (Expediente de Liquidación) |

Cualquier cambio de permisos debe cubrir **las tres**, porque `button_validate()` del *Landed Cost Run* recorre los tres niveles en una sola transacción y termina escribiendo en contabilidad e inventario valorizado.

---

## 3. Diagnóstico: por qué hoy solo funciona con "Inventario / Administrador"

### 3.1 ACLs que gatillan la exigencia

| Modelo | Archivo ACL | Grupo exigido | Operaciones |
|---|---|---|---|
| `stock.landed.cost.run` | `stock_landed_costs_features/security/ir.model.access.csv:2` | `stock.group_stock_manager` | CRUD |
| `stock.valuation.adjustment.summary` | `…ir.model.access.csv:3` | `stock.group_stock_manager` | CRUD |
| `stock.landed.cost.product` | `…ir.model.access.csv:4` | `stock.group_stock_manager` | CRUD |
| `stock.landed.cost` | core `stock_landed_costs/security/ir.model.access.csv:2` | `stock.group_stock_manager` | CRUD |
| `stock.landed.cost.lines` | core `…:3` | `stock.group_stock_manager` | CRUD |
| `stock.valuation.adjustment.lines` | core `…:4` | `stock.group_stock_manager` | CRUD |
| `stock.valuation.layer` | core `stock_account/security/ir.model.access.csv:8` | `stock.group_stock_manager` | R/W/C (sin unlink) |
| `account.account` (lectura) | core `stock_account/…` | `stock.group_stock_manager` | R |
| `account.journal` (lectura) | core `stock_account/…` | `stock.group_stock_manager` | R |
| `stock.landed.cost.file` | `stock_landed_costs_file/security/ir.model.access.csv:2` | `stock_landed_costs_file.stock_landed_costs_file_user` | CRUD |

Además, `stock_landed_costs_file.stock_landed_costs_file_user` **no tiene `implied_ids`** y solo está asignado a `base.user_root` y `base.user_admin` (`stock_landed_costs_file/security/res_groups_data.xml:4-7`). Es decir: en la práctica, hoy la liquidación completa funciona solo para *admin* o para quien se le asigne el grupo a mano.

### 3.2 Escrituras no-sudo en el camino de validación

`stock.landed.cost.button_validate()` (core, `stock_landed_costs/models/stock_landed_cost.py:109-172`) hace, con el usuario real (sin `sudo`):

1. `self.env['stock.valuation.layer'].create(...)` — línea 137 → 483.
2. `linked_layer.remaining_value += cost_to_add` (write en SVL).
3. `self.env['account.move'].create(move_vals)` + `move._post()` — líneas 167-172.
4. `reconcile_landed_cost()` → `aml.reconcile()` — línea 174 → crea `account.partial.reconcile` / `account.full.reconcile`.

Única excepción ya resuelta por Odoo: `product.sudo().standard_price += …` (línea 160) — la actualización del costo del producto **no** requiere permiso de escritura sobre productos.

Consecuencia: **liquidar requiere, además de Inventario/Administrador, permisos de escritura contable** (`account.group_account_invoice` para `account.move`, `account.move.line`, `account.partial.reconcile`, `account.full.reconcile`). Hoy eso pasa desapercibido porque el usuario de pruebas es *admin*.

### 3.3 Vistas y botones con grupos contables

`stock_landed_costs_features/views/stock_landed_cost_run_views.xml`:

| Línea | Elemento | Grupo |
|---|---|---|
| 40 | Botón *Journal items* | `account.group_account_user` |
| 65 | Pestaña *Vendor Bills* | `account.group_account_invoice` |
| 75, 81 | Subtotal / Total de facturas | `account.group_account_invoice` |
| 89, 141 | Pestaña *Pre-clearance Products* / campo | `stock_landed_costs_features.group_preclearance` |
| 122 | Botón *Generate Entries* | `account.group_account_user` |

Y en Python: `stock_landed_cost_run.py:221` → `if not self.user_has_groups("account.group_account_invoice"): raise AccessError(...)`.

### 3.4 Menús inalcanzables para un rol no administrador

Los menús de Expedientes de Liquidación (`stock_landed_costs_file/views/stock_landed_cost_file_views.xml:106-135`) están colgados de:

- `account.menu_finance_configuration` → requiere `account.group_account_manager`
- `stock.menu_stock_config_settings` → menú de *Configuración* de Inventario (requiere `base.group_system` en la práctica)
- `purchase.menu_purchase_config` → requiere `purchase.group_purchase_manager`

Un rol de liquidación no administrador **no vería ninguno de los tres**, aunque tenga la ACL del modelo.

### 3.5 Qué se está regalando hoy al dar "Inventario / Administrador"

`stock.group_stock_manager` otorga CRUD completo sobre, entre otros: `stock.warehouse`, `stock.location`, `stock.picking.type`, `stock.move`, `stock.move.line`, `stock.rule`, `stock.route`, `stock.putaway.rule`, `stock.scrap`, `stock.warehouse.orderpoint`, `product.template`, `product.product`, `product.category`, `product.pricelist`, `product.pricelist.item`, `product.supplierinfo`, `uom.uom`, `res.partner`, más los asistentes de ajuste de inventario (`stock.inventory.conflict`, `stock.request.count`, `stock.quant.relocate`) y `stock.valuation.layer.revaluation` (revalorización manual de inventario).

Es decir, para liquidar una importación hoy hay que entregar control total del inventario, del catálogo de productos y de las listas de precios. La observación del cliente es válida y el riesgo es mayor al que él menciona.

### 3.6 Aclaración importante sobre "validar conduces de entrada"

**Esto debe quedar explícito con el cliente antes de desarrollar:** en Odoo estándar, la validación de transferencias (incluidas las recepciones / conduces de entrada) **ya está permitida al *Usuario* de Inventario**, no solo al Administrador:

```
odoo/addons/stock/security/ir.model.access.csv:8
access_stock_picking_user,stock.picking user,model_stock_picking,stock.group_stock_user,1,1,1,1
```

Por lo tanto, el grupo solicitado — *"accesos base del usuario de Inventario + liquidación"* — **seguirá permitiendo validar conduces de entrada**, porque hereda `stock.group_stock_user`.

Lo que sí se elimina con esta propuesta es todo lo del punto 3.5 (ajustes de inventario, revalorización, catálogo, precios, almacenes, rutas, descartes).

Si el requerimiento real incluye **impedir validar recepciones**, hace falta un control adicional que **no** es parte de este cambio de grupos. Opciones (a cotizar aparte):

- Regla de registro (`ir.rule`) sobre `stock.picking` por tipo de operación / almacén para el nuevo grupo.
- Grupo aún más restringido que no herede `stock.group_stock_user` y reciba solo lectura sobre `stock.picking` / `stock.move` / `stock.quant` (rompe el enunciado "accesos base del usuario de Inventario", pero es lo que cumple el objetivo de seguridad declarado).
- Override de `stock.picking.button_validate()` con chequeo de grupo.

**Recomendación:** implementar el grupo tal como se pide (Fase 1, este documento) y levantar esta pregunta al cliente en paralelo; si responde que sí hay que bloquear recepciones, se ejecuta la Fase 2 con la opción 1 o 3.

---

## 4. Diseño propuesto

### 4.1 Nuevo grupo

```xml
<!-- stock_landed_costs_features/security/res_groups.xml -->
<record id="group_landed_cost_settlement" model="res.groups">
    <field name="name">User + Landed Cost Settlement</field>
    <field name="category_id" ref="base.module_category_inventory_inventory"/>
    <field name="implied_ids" eval="[(4, ref('stock.group_stock_user'))]"/>
</record>
```

- XML ID: `stock_landed_costs_features.group_landed_cost_settlement`
- Nombre técnico en inglés (convención del repo); traducción en `i18n/es_DO.po`:
  `msgstr "Usuario Inventario + Liquidación"`
- Categoría: **Inventario**, para que aparezca como opción de rol junto a *Usuario* / *Administrador*.

### 4.2 Restricción crítica: mantener el radio button de la categoría Inventario

`res.users.get_groups_by_application()` (`odoo/addons/base/models/res_users.py:1674-1699`) decide si una categoría se pinta como **radio (selection)** o como **checkboxes (boolean)** así:

```python
order = {g: len(g.trans_implied_ids & gs) for g in gs}
if len(set(order.values())) == len(gs):
    return (app, 'selection', gs.sorted(key=order.get), category_name)
else:
    return (app, 'boolean', gs, (100, 'Other'))
```

El orden de implicación dentro de la categoría **debe ser total** (conteos distintos). Con la categoría Inventario:

| Grupo | Implicados dentro de la categoría | Conteo |
|---|---|---|
| `stock.group_stock_user` | — | 0 |
| `…group_landed_cost_settlement` | `group_stock_user` | 1 |
| `stock.group_stock_manager` | `group_stock_user` | 1 ❌ |

Empate ⇒ **toda la categoría Inventario degrada a checkboxes y se mueve al bloque "Other"** en el formulario de usuario. Regresión de UI grave y silenciosa.

**Solución obligatoria:** hacer que *Administrador* implique el grupo nuevo:

```xml
<record id="stock.group_stock_manager" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('stock_landed_costs_features.group_landed_cost_settlement'))]"/>
</record>
```

Resultado (jerarquía limpia, radio preservado, y los administradores actuales no pierden nada):

```
Usuario (0)  <  Usuario Inventario + Liquidación (1)  <  Administrador (2)
```

> Alternativa descartada: crear el grupo en una categoría oculta como *checkbox* adicional. Es más flexible (se combina con cualquier rol de inventario) pero no cumple el enunciado del cliente de "un rol", y deja el grupo fuera del selector natural de Inventario. Si el cliente prefiere que sea combinable, es un cambio de una línea (`category_id`) y se elimina el `implied_ids` sobre el manager.

### 4.3 Estrategia para los permisos contables

Liquidar **obliga** a crear y asentar un `account.move` (§3.2). Dos caminos:

**Opción A — ACL contable acotada por reglas de registro (recomendada)**

Dar al grupo nuevo, en `stock_landed_costs_features/security/`:

- `account.account` → R
- `account.journal` → R
- `account.move`, `account.move.line` → R/W/C (sin unlink)
- `account.partial.reconcile`, `account.full.reconcile` → R/W/C (necesarios para `reconcile_landed_cost`)

y acotar la escritura con dos `ir.rule` sobre el grupo nuevo (`ir.rule` soporta `perm_read` / `perm_write` / `perm_create` / `perm_unlink`):

```xml
<!-- lectura amplia: necesita ver facturas de proveedor en la pestaña Vendor Bills -->
<record id="account_move_lc_read_rule" model="ir.rule">
    <field name="name">Landed cost settlement: read moves</field>
    <field name="model_id" ref="account.model_account_move"/>
    <field name="domain_force">[(1, '=', 1)]</field>
    <field name="groups" eval="[(4, ref('group_landed_cost_settlement'))]"/>
    <field name="perm_read" eval="True"/>
    <field name="perm_write" eval="False"/>
    <field name="perm_create" eval="False"/>
    <field name="perm_unlink" eval="False"/>
</record>

<!-- escritura acotada: solo asientos del diario de liquidación -->
<record id="account_move_lc_write_rule" model="ir.rule">
    <field name="name">Landed cost settlement: write settlement entries</field>
    <field name="model_id" ref="account.model_account_move"/>
    <field name="domain_force">[('move_type', '=', 'entry')]</field>
    <field name="groups" eval="[(4, ref('group_landed_cost_settlement'))]"/>
    <field name="perm_read" eval="False"/>
    <field name="perm_write" eval="True"/>
    <field name="perm_create" eval="True"/>
    <field name="perm_unlink" eval="False"/>
</record>
```

Ventajas: trazabilidad real (`create_uid` = usuario que liquidó), no se toca el core, la fecha de bloqueo fiscal (`period_lock_date`) se sigue aplicando con toda su fuerza.

Advertencias a documentar:
- Las reglas por grupo se combinan con **OR**. Un usuario que además tenga `account.group_account_invoice` recibe `account.account_move_rule_group_invoice` (`domain_force = [(1,'=',1)]`, sin restricción de operación) y la restricción de arriba deja de acotar. Es esperado: ese usuario ya es de facturación.
- Restringir por diario (en lugar de `move_type`) es más estricto pero exige leer `res.company.lc_journal_id` en el dominio; se puede con `[('journal_id', '=', user.company_id.lc_journal_id.id)]`, aunque falla si la compañía no lo tiene configurado. Se sugiere `move_type = 'entry'` + validación de diario en Python.

**Opción B — `sudo()` en el tramo contable**

Override de `stock.landed.cost.button_validate()` en `stock_landed_costs_features` que eleve a `sudo()` cuando el usuario tenga el grupo nuevo y **no** tenga facturación. Menos ACLs que otorgar, pero:

- `create_uid` de los asientos pasa a ser OdooBot ⇒ se pierde auditoría.
- `res.company._get_user_fiscal_lock_date()` (`odoo/addons/account/models/company.py:368-376`) usa `user_has_groups('account.group_account_manager')`; como superusuario pertenece a todos los grupos, **se omite `period_lock_date`** y solo se respeta `fiscalyear_lock_date`. Debilita el cierre contable.

⇒ **Se recomienda la Opción A.** La B queda como plan de contingencia si el cliente rechaza otorgar ACL de `account.move` al grupo.

### 4.4 Expediente de Liquidación (`stock_landed_costs_file`)

`stock_landed_costs_file.stock_landed_costs_file_user` queda como grupo funcional, pero pasa a ser **implicado** por el nuevo grupo:

```xml
<record id="stock_landed_costs_file.stock_landed_costs_file_user" model="res.groups">
    <field name="implied_ids"
           eval="[(4, ref('stock_landed_costs_features.group_landed_cost_settlement'))]"/>
</record>
```

⚠️ Ojo con la dirección: es el grupo **nuevo** el que debe implicar a *Clearance Files User*, no al revés. Se declara en `stock_landed_costs_file` (que depende de `features`) extendiendo el grupo nuevo:

```xml
<record id="stock_landed_costs_features.group_landed_cost_settlement" model="res.groups">
    <field name="implied_ids" eval="[(4, ref('stock_landed_costs_file_user'))]"/>
</record>
```

---

## 5. Cambios por archivo

### 5.1 `stock_landed_costs_features`

| # | Archivo | Cambio |
|---|---|---|
| 1 | `security/res_groups.xml` | Crear `group_landed_cost_settlement` (categoría Inventario, implica `stock.group_stock_user`). Añadir el `implied_ids` sobre `stock.group_stock_manager` (§4.2). Evaluar si `group_preclearance` debe implicar el nuevo grupo en lugar de `account.group_account_invoice` (hoy línea 6). |
| 2 | `security/ir.model.access.csv` | Reasignar las 3 filas de `stock.group_stock_manager` → grupo nuevo (el manager las sigue teniendo por herencia). Añadir filas para: `stock_landed_costs.model_stock_landed_cost`, `model_stock_landed_cost_lines`, `model_stock_valuation_adjustment_lines` (CRUD), `stock_account.model_stock_valuation_layer` (R/W/C), `account.model_account_account` (R), `account.model_account_journal` (R), `account.model_account_move` + `model_account_move_line` (R/W/C), `account.model_account_partial_reconcile` + `model_account_full_reconcile` (R/W/C). |
| 3 | `security/ir_rule.xml` | Añadir las dos reglas de `account.move` de §4.3. Opcional: reglas espejo para `account.move.line`. La regla multi-compañía de `stock.landed.cost.run` no cambia. |
| 4 | `models/stock_landed_cost_run.py:221` | `user_has_groups("account.group_account_invoice")` → aceptar también el grupo nuevo: `self.env.user.has_group("…group_landed_cost_settlement") or self.env.user.has_group("account.group_account_invoice")`. |
| 5 | `models/stock_landed_cost_run.py:293` | **Bug preexistente en el camino de liquidación:** `difference_move_id.post()` — `post()` no existe en Odoo 17 (es `_post()` / `action_post()`, `odoo/addons/account/models/account_move.py:3904` y `:4258`). Hoy lanza `AttributeError` al generar asientos de diferencia de pre-liquidación. Corregir a `action_post()` dentro de este mismo cambio. |
| 6 | `views/stock_landed_cost_run_views.xml` | Añadir el grupo nuevo en los `groups=` de líneas 40, 65, 75, 81 y 122 (formato `groups="account.group_account_invoice,stock_landed_costs_features.group_landed_cost_settlement"`). Sin esto el nuevo rol ve el formulario sin pestaña de facturas ni botones. |
| 7 | `views/stock_valuation_adjustment_summary_views.xml` | La acción no tiene `groups`; se rige por la ACL del modelo → queda cubierta por el punto 2. Verificar el menú si se le agrega uno. |
| 8 | `i18n/es_DO.po` | Añadir `model:res.groups,name:stock_landed_costs_features.group_landed_cost_settlement` → `"Usuario Inventario + Liquidación"`. |
| 9 | `__manifest__.py` | Bump `17.0.1.0.9` → **`17.0.1.1.0`** (cambio de modelo de seguridad, no es un patch). |
| 10 | `migrations/17.0.1.1.0/post-migration.py` | Ver §6. |

### 5.2 `stock_landed_costs_file`

| # | Archivo | Cambio |
|---|---|---|
| 11 | `security/res_groups_data.xml` | Encadenar `group_landed_cost_settlement` → `stock_landed_costs_file_user` (§4.4). Mantener la asignación a root/admin. |
| 12 | `views/stock_landed_cost_file_views.xml:106-135` | Los tres menús cuelgan de menús de *Configuración* inaccesibles para el rol nuevo (§3.4). Añadir un menú operativo visible, p. ej. bajo `stock.menu_stock_warehouse_mgmt` con `groups="stock_landed_costs_file.stock_landed_costs_file_user"`, junto a *Landed Costs Run*. |
| 13 | `models/stock_picking.py:15-27` | `update_purchase_lc_files()` escribe `picking.purchase_id.lc_file_ids` en el entorno del usuario ⇒ **`AccessError` de `purchase.order`** para un usuario de inventario sin permisos de compras (`purchase.order` W solo para `purchase.group_purchase_user` / `group_purchase_manager`). Envolver en `sudo()` (es una sincronización interna, no un cambio funcional de la orden) o condicionar con `check_access_rights(..., raise_exception=False)`. |
| 14 | `models/stock_landed_cost_file.py:58-68` | `_compute_all_count()` hace `search()` sobre `purchase.order` y `account.move.line` ⇒ falla al abrir el Expediente sin permisos de compras/contabilidad. Usar `sudo()` en los `_get_file_related_*()` de conteo o `search_count` con `sudo`. **Aparte:** el compute hace `file.write({...})` sobre campos *no almacenados* — patrón incorrecto que conviene corregir a asignación directa (`file.purchase_count = …`) en el mismo PR. |
| 15 | `models/stock_landed_cost_file.py:70-130` | Los `action_view_related_*` ya usan `self.sudo().env.ref(...)` para leer la acción, pero devuelven acciones de `purchase.order` / `account.move` que el rol nuevo puede no poder abrir. Decidir: ocultar los stat buttons con `groups=` o aceptar el `AccessError` al hacer clic. Recomendado: `groups="purchase.group_purchase_user"` / `account.group_account_invoice"` en los botones de compras y facturas. |
| 16 | `security/ir.model.access.csv` | Sin cambios (ya apunta al grupo funcional, que ahora se hereda). |
| 17 | `i18n/es_DO.po` | Sin cambios obligatorios. |
| 18 | `__manifest__.py` | Bump `17.0.1.0.6` → **`17.0.1.1.0`**. |

### 5.3 Sin cambios (verificado)

- `product.product.standard_price`: el core ya usa `sudo()` (`stock_landed_cost.py:160`) ⇒ no hace falta W sobre productos.
- `ir.sequence.next_by_code`: solo exige R, y `base.group_user` ya la tiene (`base/security/ir.model.access.csv:28`).
- `ir.property` (fallback de diario en `_default_account_journal_id`): `_get_default_property` usa `self.sudo().search(...)` ⇒ no requiere ACL.
- `decimal.precision`, `res.company`: lectura ya disponible al usuario interno.
- `stock.picking` / `stock.move`: cubiertos por `stock.group_stock_user`.

---

## 6. Migración y compatibilidad

Convención del repo: `migrations/<version>/{pre,post}-migration.py` usando `odoo.upgrade.util` (ver `stock_landed_costs_features/migrations/17.0.1.0.9/pre-migrate.py`).

`post-migration.py` de `17.0.1.1.0` debe:

1. **No romper instalaciones existentes.** Las ACLs reasignadas al grupo nuevo siguen aplicando a los administradores por el `implied_ids` de §4.2; Odoo recalcula `res_groups_implied_rel` al actualizar el módulo. Verificar en la migración que `stock.group_stock_manager` quedó con el grupo nuevo en `trans_implied_ids` y forzarlo si no.
2. **Repoblar `res_groups_users_rel`** para los usuarios que ya tenían `stock.group_stock_manager` (Odoo no lo hace retroactivamente para grupos implicados creados después; el mecanismo se aplica al escribir `groups_id`). Patrón:

```python
def migrate(cr, version):
    cr.execute("""
        INSERT INTO res_groups_users_rel (gid, uid)
        SELECT new.res_id, rel.uid
        FROM ir_model_data new
        JOIN ir_model_data mgr
          ON mgr.module = 'stock' AND mgr.name = 'group_stock_manager'
        JOIN res_groups_users_rel rel ON rel.gid = mgr.res_id
        WHERE new.module = 'stock_landed_costs_features'
          AND new.name = 'group_landed_cost_settlement'
        ON CONFLICT DO NOTHING
    """)
```

3. **Opcional (a pedido del cliente):** asignar el grupo nuevo a una lista de usuarios de importaciones y quitarles `stock.group_stock_manager`. Se recomienda **no** hacerlo automáticamente — es una decisión funcional del cliente, no una migración técnica.

---

## 7. Plan de pruebas

### 7.1 Tests automatizados (nuevos)

Archivo sugerido: `stock_landed_costs_features/tests/test_landed_cost_settlement_security.py`, reutilizando `TestStockLandedCostsCommon` como ya hace `test_stock_landed_costs_specific_products.py`.

1. Usuario con **solo** `group_landed_cost_settlement`:
   - crea `stock.landed.cost.run`, agrega producto de pre-liquidación, `button_generate_landed_costs()`, `compute_landed_cost_all()`, `button_validate()` → sin `AccessError`;
   - se generan `stock.valuation.layer` y `account.move` asentado;
   - `product.standard_price` se actualiza.
2. Mismo usuario: `generate_difference_entries()` con factura posteada → asiento de diferencia creado y **asentado** (cubre el bug de `post()`).
3. Mismo usuario: abre un `stock.landed.cost.file` con OC y factura relacionadas → sin `AccessError` (cubre §5.2 #13/#14).
4. **Negativos:** el mismo usuario **no** puede: crear/escribir `stock.warehouse`, `stock.location`, `product.template`, `stock.valuation.layer.revaluation`, ni crear un `account.move` de tipo `in_invoice`.
5. Usuario con `stock.group_stock_manager` (sin tocar nada más) sigue liquidando igual → no regresión.
6. Test de UI/estructura: la categoría Inventario sigue siendo `selection`:
   ```python
   apps = self.env['res.users'].get_groups_by_application()
   inv = next(x for x in apps if x[0] == self.env.ref('base.module_category_inventory_inventory'))
   self.assertEqual(inv[1], 'selection')
   ```
   Este test es el que atrapa la regresión de §4.2.

### 7.2 Pruebas manuales

Usar un DB fresco y el script `setup_test_landed_costs_features.py` como base de datos semilla; crear un usuario `liquidador` con solo el rol nuevo y recorrer el flujo completo: Expediente → OC → recepción → factura de proveedor con líneas de costo → *Landed Costs Run* → Generar → Calcular → Validar → revisar Resumen de Valuación y asiento contable.

⚠️ Recordatorio operativo: `run_tests.sh` marca **PASS aunque falle `setUpClass`**. Verificar siempre con `grep -E 'FAIL|ERROR' test_logs/modules/<módulo>.log`.

---

## 8. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Categoría Inventario degrada a checkboxes | Alto (UI de todos los usuarios) | `implied_ids` en manager + test de §7.1.6 |
| Otorgar C/W sobre `account.move` al grupo | Medio | `ir.rule` acotada a `move_type='entry'`; revisar con el cliente |
| Instalaciones existentes: usuarios manager sin el grupo nuevo en `res_groups_users_rel` | Alto (pierden acceso a liquidación) | Migración §6.2 + prueba de upgrade sobre copia de producción |
| `sudo()` en `stock_landed_costs_file` amplía alcance sobre `purchase.order` | Bajo | Limitar el `sudo()` a la escritura de `lc_file_ids` únicamente |
| El cliente espera que el nuevo rol **no** pueda validar recepciones | Alto (expectativa) | Aclarar §3.6 **antes** de desarrollar |
| Fecha de bloqueo contable si se elige la Opción B | Medio | Preferir Opción A |

---

## 9. Estimación

| Tarea | Estimado |
|---|---|
| Grupo + ACLs + `ir.rule` + jerarquía de categoría | 4 h |
| Ajustes de vistas y menús (features + file) | 3 h |
| Ajustes Python (`user_has_groups`, `sudo` en file, fix `post()`) | 3 h |
| Migración + prueba de upgrade | 3 h |
| Tests automatizados (positivos, negativos, categoría) | 6 h |
| Traducciones + README + pruebas manuales end-to-end | 3 h |
| **Total Fase 1** | **~22 h** |
| Fase 2 (bloquear validación de recepciones, si aplica) | 6–10 h adicionales |

---

## 10. Decisiones pendientes del cliente

1. ¿El nuevo rol debe **impedir** validar conduces de entrada? (§3.6) — define si hay Fase 2.
2. ¿Rol excluyente en la categoría Inventario (radio) o permiso combinable (checkbox)? (§4.2)
3. ¿Se acepta otorgar creación/escritura de asientos (`move_type='entry'`) acotada por regla, o se prefiere `sudo()` con pérdida de auditoría? (§4.3)
4. ¿Se debe asignar el grupo nuevo automáticamente a algún conjunto de usuarios en la migración? (§6.3)
