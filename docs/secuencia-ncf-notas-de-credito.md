# Secuencia de NCF y notas de crédito

> Por qué se duplicaban los e-NCF de notas de crédito, cómo funciona realmente
> la numeración fiscal dominicana en Odoo 19 y qué se cambió para arreglarlo.
>
> Módulos: `l10n_do_accounting`, `l10n_do_document_pools`. Solo rama 19.0.

---

## 1. El síntoma

Una nota de crédito emitida sobre una **factura de proveedor** (E41 Compras,
E47 Pago al Exterior) salía con el **mismo e-NCF** que una nota de crédito ya
emitida a un cliente.

En el staging de ALCOVER, tres pares posteados:

| e-NCF | Documento de cliente | Documento de proveedor |
|---|---|---|
| `E340000000007` | NC del 2026-07-21 | NC del 2026-09-03 sobre E470000000101 |
| `E340000000009` | NC del 2026-08-11 | NC del 2026-09-08 sobre E470000000085 |
| `E340000000010` | NC del 2026-09-08 | NC del 2026-09-08 sobre E470000000085 |

Efecto en la DGII: el segundo envío del mismo número se rechaza con el código
**135, "Número de secuencia no autorizada"**.

---

## 2. Cómo funciona la numeración (el modelo mental)

### 2.1 El NCF lo emite quien lo numera, no quien vende

La DGII autoriza **un talonario por tipo de comprobante y por RNC**. Quién lo
consume no importa: si el número lo ponemos nosotros, sale de nuestro talonario.

En una factura, el campo `name` guarda el NCF. Pero ese NCF puede ser de dos
dueños distintos:

| `l10n_latam_manual_document_number` | Significado | Ejemplos |
|---|---|---|
| `False` | **Lo numeramos nosotros.** Sale de nuestro talonario. | Todas las ventas (E31, E32, E34…) y las compras auto-numeradas: E41 Compras, E43 Gasto Menor, E47 Pago al Exterior (y sus equivalentes B11, B13, B17) |
| `True` | **Es el número del contraparte**, tecleado a mano. No es nuestro. | Factura de proveedor con su propio E31/B01 |

Ese flag lo decide `_is_l10n_do_manual_document_number()`, y una nota de
crédito **lo hereda de la factura que reversa** (vía `reversed_entry_id`).

### 2.2 La consecuencia que causó el bug

Una NC sobre una factura E47 es de tipo `in_refund` — dirección de compra —
pero es **nuestra**: `manual = False`. Consume el mismo talonario E34 que la NC
de cliente (`out_refund`).

```
Talonario E34 autorizado por la DGII:  1, 2, 3, 4, 5, ...
                                        │  │  │  │  │
        NC a cliente      (out_refund) ─┘  │  └──┤  │
        NC a proveedor E47 (in_refund) ────┘     │  │
        NC a proveedor E41 (in_refund) ──────────┘  │
        NC a cliente      (out_refund) ─────────────┘

Un solo talonario. La dirección del documento es irrelevante.
```

### 2.3 Qué NO comparte talonario

El e-NCF que el suplidor pone en su factura (`manual = True`) vive en el mismo
campo `name`, pero es de él. Nunca puede alimentar nuestra secuencia. Ese es el
único corte legítimo.

---

## 3. Qué estaba mal

### 3.1 Causa raíz: se cortaba por dirección en vez de por dueño del número

`l10n_do_accounting/models/account_move.py`, en `_get_last_sequence_domain()`:

```python
# ANTES  (commit 87bd0da2, 2026-06-05)
where_string += " AND move_type = ANY(%(l10n_do_move_types)s)"
param["l10n_do_move_types"] = (
    self.get_sale_types(include_receipts=True)
    if self.is_sale_document(include_receipts=True)
    else self.get_purchase_types(include_receipts=True)
)
```

Al buscar "¿cuál fue el último E34?", solo miraba documentos de **la misma
dirección**. Resultado: un talonario partido en dos escaleras independientes.

```
                     Escalera de VENTAS        Escalera de COMPRAS
  Talonario E34   ->  1, 2, 3, 4, ...      y    1, 2, 3, 4, ...
                                                 ^^^^^^^^^^^^
                                                 los mismos números
```

La intención del commit era correcta y sigue siendo necesaria: evitar que el
e-NCF de un suplidor contamine nuestra secuencia. Solo usó el discriminante
equivocado — **dirección** en lugar de **quién numera**.

### 3.2 Por qué explotó el 3 de septiembre y no en junio

El fallo quedó latente tres meses. Mientras las dos escaleras vivían en rangos
lejanos nadie chocaba: en ALCOVER la escalera de compras andaba por
`E340000030967` y la de ventas por `E340000000006`.

El 2026-09-03 el commit `d6ccb7cb1` hizo que las notas de crédito de compras
tomaran el pool del diario de ventas. Eso metió **las dos escaleras en el mismo
rango** `[1-50]`, y el primer duplicado apareció ese mismo día a las 20:24.

| Commit | Fecha | Autor | Efecto |
|---|---|---|---|
| `87bd0da2` | 2026-06-05 | DanielAPereyraB | Introduce el corte por dirección. Bug latente |
| `e81d68dce` | 2026-06-08 | DanielAPereyraB | Borra el test de regresión del commit anterior |
| `d6ccb7cb1` | 2026-09-03 | luisfernandez | NC de compras leen el pool de ventas → destapa el bug |

`d6ccb7cb1` no introdujo el defecto: lo hizo visible.

### 3.3 Segundo defecto: el pool no contaba lo que sí se consumía

`l10n_do_document_pools` filtraba los movimientos del pool por `journal_id`:

```python
# ANTES
("journal_id", "=", doc_type.journal_id.id),
```

Pero un pool **no se consume solo por su propio diario**:

- un diario de **compras** no tiene pool de notas de crédito: tira del diario
  de ventas configurado en `l10n_do_credit_note_sequence_journal_id`;
- una **sucursal** factura con el diario de la matriz.

Esos consumos quedaban invisibles. El contador `l10n_do_next_sequence` se
congelaba, el pool **nunca se marcaba agotado** y la numeración se pasaba de
`sequence_end`, emitiendo números fuera de la autorización de la DGII.

Reproducido con el rango `[1-6]` consumido solo desde compras:

```
compra -> NC E340000000006 (seq=6) | pool next=2 estado=valid
compra -> NC E340000000007 (seq=7) | pool next=2 estado=valid  <-- FUERA DEL RANGO
compra -> NC E340000000008 (seq=8) | pool next=2 estado=valid  <-- FUERA DEL RANGO
```

---

## 4. La solución

### 4.1 Cortar por dueño del número, no por dirección

```python
# AHORA
where_string += " AND COALESCE(l10n_latam_manual_document_number, FALSE) = %(l10n_do_manual_number)s"
param["l10n_do_manual_number"] = bool(self.l10n_latam_manual_document_number)
```

Los documentos que numeramos nosotros comparten talonario sin importar la
dirección; los del contraparte quedan fuera. Es exactamente la regla que la
rama **17.0 ya aplicaba** en `_l10n_do_get_last_fiscal_sequence_domain`:

```python
# 17.0
else:
    where_string += " AND l10n_latam_manual_document_number = 'f'"
```

No se pudo copiar el código porque el motor de secuencia de 17 no existe en 19:
allá el NCF vive en un campo aparte (`l10n_do_fiscal_number`) con su propia
maquinaria; en 19 el NCF **es** `name` y pasa por el `sequence.mixin` del core
(migración `upgrades/19.0.1.0.0/pre-migrate_fiscal_number_to_name.py`). Se portó
la regla, no las líneas.

#### ¿Por qué el parámetro sale de `self`?

`_get_last_sequence_domain()` construye el dominio **de un movimiento
concreto**: responde "¿cuál fue el número anterior al mío?". Todos los demás
filtros ya salen de `self` por la misma razón — `l10n_latam_document_type_id`,
`company_ids` — y el código anterior hacía lo mismo con `self.is_sale_document()`.

Fijar la constante `FALSE` en vez de parametrizar rompería las facturas de
proveedor con número manual: se compararían contra *nuestra* secuencia y
producirían avisos de huecos falsos.

### 4.2 Que el pool cuente lo mismo que la numeración

Se extrajo el alcance a un solo sitio, `_l10n_do_pool_moves_domain()`:

```python
return [
    ("l10n_latam_document_type_id", "=", self.l10n_latam_document_type_id.id),
    ("company_id", "child_of", self.company_id.root_id.id),
    ("l10n_latam_manual_document_number", "=", False),
    ("posted_before", "=", True),
    ("sequence_number", ">=", self.sequence_start),
    ("sequence_number", "<=", self.sequence_end),
]
```

### 4.3 ¿Por qué se quitó `journal_id` del pool?

Es la pregunta natural: *"pueden haber múltiples diarios con secuencias"*.

**Lo que separa dos pools del mismo tipo de documento es el RANGO, no el
diario** — y el rango es justo lo que usa la numeración. Si Ventas A tiene E34
`[1-20]` y Ventas B tiene E34 `[21-40]`, cada pool cuenta solo su intervalo y
no pueden verse entre sí.

La numeración **nunca** filtró por diario en 19.0; lo quita a propósito:

```python
where_string = where_string.replace("journal_id = %(journal_id)s AND", "")
```

porque el talonario es de la compañía (del RNC), no del diario. Dejar
`journal_id` en el contador del pool solo lograba que el pool **discrepara** de
la numeración real.

Validado: el escenario de dos diarios de venta con pools distintos pasa
**igual antes y después** del cambio (ver §5, escenario A).

> ⚠️ **Restricción de configuración.** Dos pools del mismo tipo de documento
> dentro del mismo RNC **no deben solaparse en rango**. El módulo valida
> solapamientos solo entre rangos en cola de un mismo pool, no entre diarios
> distintos. Si dos diarios comparten rango, la numeración entrega los mismos
> números — y eso pasa con o sin este cambio.

### 4.4 Sucursales: un solo RNC, un solo talonario

Una sucursal (`res.company.parent_id`) **no carga plan ni diarios propios**:
usa la contabilidad de la matriz. Comprobado en v19:

```
cuentas propias de la sucursal : 0
diarios propios de la sucursal : []
```

Por eso el pool sabe su compañía **a través del diario** (`company_id` es
`related="journal_id.company_id"`), y en el camino normal eso basta: si la
sucursal factura con el diario de la matriz sin tocar el campo Compañía, el
asiento queda con `company_id = matriz`, que es la compañía del pool.

Pero Odoo **sí permite** que el asiento quede a nombre de la sucursal usando el
diario de la matriz — `_compute_company_id` respeta el valor cuando la compañía
del diario está en `company_id.parent_ids`:

```
factura con company_id = sucursal FORZADO:  company=S9  journal.company=M9  -> posteada
```

En ese caso el filtro por compañía exacta dejaba el consumo fuera del contador:

| | e-NCF emitido | ¿duplicado? | Contador del pool |
|---|---|---|---|
| `company_id = <compañía del pool>` | `E340000000002` | no | **2** ← ya consumido, se congela |
| `company_id child_of root_id` | `E340000000002` | no | **3** ✔ |

La numeración nunca duplicó aquí: `_get_last_sequence_domain` ya abarcaba
matriz + sucursales desde antes. El que se quedaba corto era el **contador**,
con la misma consecuencia que en §3.3 — nunca agotar y pasarse de
`sequence_end`.

Se resolvió con el idioma nativo de Odoo para sucursales, en la misma línea que
ya filtraba por compañía:

```python
("company_id", "child_of", self.company_id.root_id.id),
```

`root_id` es la compañía dueña del RNC. Una línea, sin métodos nuevos.

> Nota: `_get_last_sequence_domain` arma su grupo de compañías a mano y solo
> baja **un nivel** (matriz + hijas directas). Con sucursales anidadas a dos
> niveles la numeración se quedaría corta. Es una limitación preexistente,
> ajena a este arreglo. El contador del pool sí cubre el árbol completo, que es
> el lado seguro: agotar de más obliga a pedir rango nuevo, agotar de menos
> quema números no autorizados.

---

## 5. Validación

Scripts en la raíz del entorno de desarrollo:

| Script | Qué cubre |
|---|---|
| `replicate_ncf_credit_note_duplicate.sh` | Reproduce el caso e-CF de ALCOVER (E31→NC, E47→NC) |
| `verify_ncf_sequence_isolation.sh` | El e-NCF del suplidor no toca nuestra secuencia ni el pool |
| `verify_ncf_sequence_multicompany.sh` | Multiempresa, multidiario y sucursales |

Escenarios de `verify_ncf_sequence_multicompany.sh`:

| | Escenario | Antes | Después |
|---|---|---|---|
| **A** | Dos diarios de venta en la misma compañía, pools E34 `[1-20]` y `[21-40]` | OK | OK |
| **B** | Dos compañías independientes con pools E34 de rango **idéntico** | numeración OK, contador del pool desfasado | OK |
| **C** | Sucursal con diario propio y **el mismo rango** que la matriz | **NCF duplicados** | OK, continúa el talonario |
| **D** | Diario de compras apuntando a cada diario de ventas | **NCF duplicados** | OK |

El escenario A pasando en ambos lados es la prueba de que quitar `journal_id`
no rompe el caso multidiario.

Pruebas unitarias:

- `l10n_do_accounting` — **55/55**, incluye dos nuevas en
  `tests/test_credit_note_sequence.py`. Verificado que fallan sin el arreglo
  (`AssertionError: 1 != 2`).
- `l10n_do_ecf_invoicing` — 27/27, `l10n_do_purchase` 3/3, `l10n_do_sale` 6/6.
- `l10n_do_document_pools` — 5 de 6 fallan **igual antes y después**: el arnés
  de pruebas de ese módulo quedó roto en la migración a v19 (`sequence_number`
  sale en 0). Preexistente, fuera del alcance de este arreglo.

---

## 6. Configuración a revisar

El arreglo es de código, pero hay dos cosas que dependen de la configuración:

1. **Diario para NC en cada diario de compras.**
   *Contabilidad → Configuración → Diarios → (diario de compras) →
   **Credit Note Journal***
   (`l10n_do_credit_note_sequence_journal_id`)

   Un diario de compras no tiene pool de notas de crédito propio; toma el del
   diario de ventas que se indique aquí. El campo se calcula solo — el primer
   diario de ventas de la compañía con documentos fiscales — pero es
   **editable**: si hay más de un diario de ventas con pool E34, hay que elegir
   a mano de cuál debe tirar.

2. **Rangos sin solapamiento** entre pools del mismo tipo de documento dentro
   del mismo RNC (ver el aviso en §4.3).

No hay que crear pools que el módulo no crea por sí solo. Los pools salen de
`_l10n_do_create_document_types()` según los tipos de comprobante que le
correspondan al diario; un diario de compras **no** debe tener pool E34.

---

## 7. Datos ya emitidos

El arreglo evita nuevos duplicados; **no corrige los que ya están posteados**.
En ALCOVER quedan tres notas de crédito de proveedor con e-NCF repetido
(`E340000000007`, `E340000000009`, `E340000000010`). Requieren corrección de
datos aparte, coordinada con lo que la DGII tenga aceptado.

Tampoco hay red de seguridad en base de datos: los índices únicos
`account_move_unique_l10n_do_name_sales` y
`account_move_unique_l10n_do_name_purchase_internal` están separados por
dirección, así que un duplicado entre `out_refund` e `in_refund` no lo bloquea
Postgres. Unificarlos exige limpiar antes los duplicados existentes, o la
creación del índice falla.
