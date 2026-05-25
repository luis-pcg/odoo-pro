# Guía de Liquidaciones de Importación
### `stock_landed_costs_features` — Odoo 17

---

## Índice

1. [¿Qué es una liquidación de importación?](#1-qué-es-una-liquidación-de-importación)
2. [Conceptos clave](#2-conceptos-clave)
3. [Cómo se integra con Odoo](#3-cómo-se-integra-con-odoo)
4. [Arquitectura del módulo](#4-arquitectura-del-módulo)
5. [Flujo completo paso a paso](#5-flujo-completo-paso-a-paso)
6. [Métodos de distribución (Split Methods)](#6-métodos-de-distribución-split-methods)
7. [Pre-despacho (Pre-clearance)](#7-pre-despacho-pre-clearance)
8. [Resumen de valoración](#8-resumen-de-valoración)
9. [Configuración inicial](#9-configuración-inicial)
10. [Casos de uso comunes](#10-casos-de-uso-comunes)
11. [Errores frecuentes](#11-errores-frecuentes)

---

## 1. ¿Qué es una liquidación de importación?

Cuando una empresa importa productos, el precio que paga al proveedor extranjero (precio FOB) **no es el costo real** del producto. Al llegar a la empresa, ese producto tiene costos adicionales:

```
Precio FOB (proveedor)
    + Flete internacional
    + Seguro marítimo
    + Aranceles aduanales
    + Gastos de agente aduanal
    + Almacenaje en puerto
    ─────────────────────────
    = COSTO REAL en inventario
```

Una **liquidación** es el documento que:
1. **Agrupa** todos esos costos adicionales de una importación específica
2. **Los distribuye** proporcionalmente entre todos los productos importados
3. **Actualiza** el costo en inventario de cada producto

> **Ejemplo:**
> Importas 10 TVs y 20 iPhones. El flete cuesta USD 850.
> La liquidación toma esos USD 850 y los reparte entre los 30 productos
> según el método elegido (por valor, por cantidad, por peso, etc.).

---

## 2. Conceptos clave

| Término | Definición |
|---------|-----------|
| **Landed Cost Run** | La liquidación completa. Agrupa facturas, productos de pre-despacho y los costos de aterrizaje generados. |
| **Landed Cost** (`stock.landed.cost`) | Un costo de aterrizaje individual vinculado a una recepción de inventario. Odoo nativo. |
| **Cost Line** | Línea dentro del landed cost: qué producto de costo (flete, arancel) y con qué método se distribuye. |
| **Pre-despacho** | Estimado de costo ANTES de que llegue la factura real. Permite iniciar la liquidación sin factura. |
| **Split Method** | Cómo se distribuye el costo entre los productos importados. |
| **Settlement Cost** | El costo total calculado para un producto **en esta liquidación específica** (no su costo permanente). |
| **Cost Factor** | Ratio entre Settlement Cost y valor original. Ej: 1.12 = el producto costó 12% más de lo esperado. |
| **FOB Amount** | Valor de los productos antes de costos adicionales (suma de `former_cost` del resumen). |
| **Picking** | La recepción de inventario (`stock.picking` done) a la que se le aplican los costos. |

---

## 3. Cómo se integra con Odoo

### Odoo nativo vs módulo custom

```
┌─────────────────────────────────────────────────────────────────────┐
│                         ODOO NATIVO                                  │
│                                                                      │
│  stock.landed.cost          stock.landed.cost.line                   │
│  ┌──────────────────┐       ┌────────────────────────┐               │
│  │ vendor_bill_id   │──────►│ product_id (servicio)  │               │
│  │ picking_ids      │       │ price_unit             │               │
│  │ account_journal  │       │ split_method  ◄────────┼── cálculo     │
│  │ state            │       │ account_id             │    real aquí  │
│  └──────────────────┘       └────────────────────────┘               │
│                                      │                               │
│                                      ▼                               │
│  stock.valuation.adjustment.lines                                    │
│  ┌──────────────────────────────────────┐                            │
│  │ product_id | former_cost | add_cost  │                            │
│  │ final_cost | quantity | weight       │                            │
│  └──────────────────────────────────────┘                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
           ▲                              ▲
           │  extiende                    │  agrega
           │                             │
┌─────────────────────────────────────────────────────────────────────┐
│              stock_landed_costs_features (CUSTOM)                    │
│                                                                      │
│  stock.landed.cost.run  ◄── NUEVO: el "contenedor" de la liquidación│
│  ┌──────────────────────────────────────────────────────────┐        │
│  │ vendor_bill_ids (M2M) ── facturas proveedores            │        │
│  │ product_ids           ── líneas de pre-despacho          │        │
│  │ landed_cost_ids       ── los stock.landed.cost generados │        │
│  │ summary_ids           ── resumen consolidado por producto│        │
│  │ state: draft → validated → cancelled                     │        │
│  └──────────────────────────────────────────────────────────┘        │
│                                                                      │
│  account.move  ← agrega: general_split_method (Default Split Method) │
│  stock.landed.cost.product ← NUEVO: línea de pre-despacho           │
│  stock.valuation.adjustment.summary ← NUEVO: resumen consolidado    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Mapa de modelos

```
stock.landed.cost.run
│
├── vendor_bill_ids ──────────► account.move (facturas proveedor)
│                                    └── invoice_line_ids
│                                         └── is_landed_costs_line = True
│                                         └── general_split_method (Default)
│
├── product_ids ──────────────► stock.landed.cost.product (pre-despacho)
│                                    └── general_split_method (Default)
│
├── landed_cost_ids ──────────► stock.landed.cost (ODOO NATIVO)
│                                    ├── picking_ids ──► stock.picking (done)
│                                    ├── cost_lines
│                                    │    └── split_method ← copiado desde Default
│                                    └── valuation_adjustment_lines
│                                         └── por cada producto del picking
│
└── summary_ids ──────────────► stock.valuation.adjustment.summary
                                     ├── product_id
                                     ├── former_cost       (valor antes)
                                     ├── additional_landed_cost
                                     ├── final_cost        (Settlement Cost)
                                     └── cost_factor_currency
```

---

## 4. Arquitectura del módulo

### Estados del Run

```
                    ┌─────────────────────────────┐
                    │                             │
             ┌──────┴──────┐             ┌───────▼──────┐
             │    DRAFT    │             │  VALIDATED   │
             │             │──[Validate]►│              │
             └──────┬──────┘             └──────────────┘
                    │
                    │ [Cancel]
                    ▼
             ┌──────────────┐
             │  CANCELLED   │
             └──────────────┘

  Dentro de DRAFT el usuario puede:
  ├── Agregar/quitar facturas (vendor_bill_ids)
  ├── Agregar/quitar líneas de pre-despacho (product_ids)
  ├── [Generate] → crea/actualiza los stock.landed.cost
  └── En cada landed cost: agregar picking, computar individualmente
```

### Botones del formulario

| Botón | Acción | Condición |
|-------|--------|-----------|
| **Generate** | Crea `stock.landed.cost` desde pre-despacho y facturas | `state = draft` ó `pre_validated` |
| **Validate** | Compute all → valida todos los LC → `state = validated` | `state = draft` |
| **Cancel** | Cancela todos los LC draft, pone `state = cancelled` | `state = draft` |
| **Compute** (tab Landed Costs) | Computa un LC individual | LC en `draft` |
| **Validate** (tab Landed Costs) | Valida un LC individual | LC en `draft` |

---

## 5. Flujo completo paso a paso

```
PASO 1 — RECEPCIÓN DE MERCANCÍA
═══════════════════════════════

  Proveedor envía productos
       │
       ▼
  stock.picking (type=incoming)
  ┌────────────────────────────────┐
  │ 10 × Samsung TV 55"           │
  │ 20 × iPhone 15 128GB          │
  │ state = done ✓                │
  └────────────────────────────────┘
  Esto asigna valor inicial a los productos
  (según método de costeo: AVCO/FIFO)


PASO 2 — FACTURAS DE IMPORTACIÓN
══════════════════════════════════

  Facturas de proveedores llegadas:

  Factura A (proveedor USD)           Factura B (agente aduanal DOP)
  ┌──────────────────────────┐        ┌──────────────────────────┐
  │ Samsung Electronics Ltd  │        │ Agentes Aduanales S.A.   │
  │ USD 850.00               │        │ DOP 12,500.00            │
  │ "Flete & Seguro"         │        │ "Gestión Aduanal"        │
  │ is_landed_costs_line ✓   │        │ is_landed_costs_line ✓   │
  │ Default Split: By Cost   │        │ Default Split: By Qty    │
  └──────────────────────────┘        └──────────────────────────┘
  state = posted ✓                    state = posted ✓


PASO 3 — CREAR LA LIQUIDACIÓN
═══════════════════════════════

  Inventario > Landed Costs Run > Nuevo

  stock.landed.cost.run (DRAFT)
  ┌────────────────────────────────────────────────────────────┐
  │ B/L No: BL-2026-001     Manifest: MNF-2026-001            │
  │ Date: 2026-05-22         Date B/L: 2026-05-17              │
  │                                                            │
  │ Tab [Vendor Bills]:                                        │
  │   ├── Factura A (USD 850)   Default Split: By Cost         │
  │   └── Factura B (DOP 12,500) Default Split: By Quantity    │
  │                                                            │
  │ Tab [Pre-clearance Products]:  (opcional)                  │
  │   └── "Flete FOB" DOP 42,500  Default Split: By Cost       │
  │                                                            │
  │ Tab [Landed Costs]:   (vacío por ahora)                    │
  └────────────────────────────────────────────────────────────┘


PASO 4 — GENERAR LANDED COSTS
═══════════════════════════════

  [Generate] →

  Por cada fuente se crea un stock.landed.cost:

  LC-001 (desde Factura A)              LC-002 (desde Pre-despacho)
  ┌────────────────────────────┐        ┌────────────────────────────┐
  │ vendor_bill_id: Factura A  │        │ preclearance_product_id    │
  │ cost_lines:                │        │ cost_lines:                │
  │  └── Flete USD 850*        │        │  └── Flete FOB DOP 42,500  │
  │      split_method: By Cost │        │      split_method: By Cost │
  │ picking_ids: ??? (vacío)   │        │ picking_ids: ??? (vacío)   │
  └────────────────────────────┘        └────────────────────────────┘

  * El monto USD 850 se convierte a DOP al tipo de cambio del día


PASO 5 — VINCULAR RECEPCIONES
══════════════════════════════

  En cada LC, seleccionar los picking(s) donde llegaron los productos:

  LC-001                                LC-002
  picking_ids = [REC-001] ✓            picking_ids = [REC-001] ✓

  REC-001: 10 Samsung TV + 20 iPhone (done ✓)


PASO 6 — COMPUTAR
══════════════════

  [Compute] en cada LC  o  [Compute] en el tab Landed Costs:

  Odoo calcula cuánto del costo adicional corresponde a cada producto:

  LC-001 — Flete USD 850 (≈ DOP 50,065) — Split: By Current Cost
  ┌──────────────────────────────────────────────────────────────┐
  │ Producto      │ Former Cost │ % del total │ Add. Cost        │
  ├───────────────┼─────────────┼─────────────┼──────────────────┤
  │ Samsung TV×10 │ DOP 350,000 │    77.8%    │ DOP 38,951       │
  │ iPhone 15×20  │ DOP 400,000 │    22.2%    │ DOP 11,114       │  ← nota: 20 units pero menor valor total
  │               │ DOP 750,000 │   100.0%    │ DOP 50,065       │
  └──────────────────────────────────────────────────────────────┘


PASO 7 — VALIDAR
═════════════════

  [Validate] en el Run:
  1. compute_landed_cost_all()  — recalcula todo
  2. button_validate() en cada LC — crea asientos contables
  3. _update_summary_records() — construye el resumen consolidado
  4. run.state = "validated"

  stock.landed.cost: state = done ✓
  stock.landed.cost.run: state = validated ✓


RESULTADO FINAL — Resumen de Valoración
════════════════════════════════════════

  Tab [Valuation Summary]:

  ┌─────────────────┬────────────┬────────────┬──────────────┬──────────┐
  │ Producto        │ Valor Orig.│ +Costo Imp.│ Settlement   │ Factor   │
  │                 │(former_cost│(additional)│ Cost         │ de Costo │
  ├─────────────────┼────────────┼────────────┼──────────────┼──────────┤
  │ Samsung TV 55"  │ 35,000 DOP │  4,895 DOP │  39,895 DOP  │  1.140   │
  │ iPhone 15 128GB │ 20,000 DOP │    557 DOP │  20,557 DOP  │  1.028   │
  └─────────────────┴────────────┴────────────┴──────────────┴──────────┘
                                              ↑
                               "Costo en Liquidación"
                               = lo que costó el producto
                                 en ESTA importación específica
                               ≠ nuevo precio unitario permanente
                                 (eso lo gestiona AVCO/FIFO)

  Totales:
  FOB Amount:              DOP  750,000  (valor antes de costos)
  Additional Costs Total:  DOP  108,150  (todos los costos adicionales)
  Amount Total Cost:       DOP  858,150  (costo total de esta importación)
  Average Cost Factor:         1.144    (promedio ponderado)
```

---

## 6. Métodos de distribución (Split Methods)

El **Default Split Method** en la factura/pre-despacho es una plantilla. Se copia al `split_method` real del `stock.landed.cost.line` al generar.

### ¿Cuándo usar cada uno?

```
EQUAL — Partes iguales entre todos los productos
═════
  Costo: DOP 1,000   Productos: TV, iPhone, Laptop
  TV:     DOP 333.33
  iPhone: DOP 333.33
  Laptop: DOP 333.33
  ↳ Úsalo para costos fijos independientes del producto

BY QUANTITY — Por número de unidades
════════════
  Costo: DOP 1,000   TV×10, iPhone×20 = 30 unidades
  TV:     DOP 333.33  (10/30 × 1,000)
  iPhone: DOP 666.67  (20/30 × 1,000)
  ↳ Úsalo para costos de manejo por pieza (ej: seguro por bulto)

BY CURRENT COST — Por valor FOB proporcional  ← MÁS COMÚN para importaciones
════════════════
  Costo: DOP 1,000   TV FOB=350,000  iPhone FOB=400,000
  TV:     DOP 467    (350k/750k × 1,000)
  iPhone: DOP 533    (400k/750k × 1,000)
  ↳ Úsalo para: flete, seguro, aranceles — todo lo que va proporcional al valor

BY WEIGHT — Por kilogramos
══════════
  Costo: DOP 1,000   TV=150kg (10×15kg), iPhone=6kg (20×0.3kg)
  TV:     DOP 962    (150/156 × 1,000)
  iPhone: DOP  38    (6/156   × 1,000)
  ↳ Úsalo para: flete marítimo, almacenaje por peso

BY VOLUME — Por metros cúbicos
══════════
  Costo: DOP 1,000   TV=2m³ (10×0.2m³), iPhone=0.02m³ (20×0.001m³)
  TV:     DOP 990    (2/2.02 × 1,000)
  iPhone: DOP  10    (0.02/2.02 × 1,000)
  ↳ Úsalo para: alquiler de contenedor, almacenaje por volumen
```

---

## 7. Pre-despacho (Pre-clearance)

El pre-despacho permite iniciar la liquidación **antes de recibir la factura real** del agente aduanal o transportista.

### Caso de uso

```
TIMELINE típico de una importación:
                                                        
  Día 1   Día 5      Día 10        Día 15    Día 20
  │       │          │             │         │
  ┼───────┼──────────┼─────────────┼─────────┼────
  │       │          │             │         │
  Recibo  Factura    Llegan        Factura   Liquidación
  orden   proforma   productos     real del  final
  compra  proveedor  al almacén    agente    disponible
  
Sin pre-despacho: esperas hasta Día 20 para cerrar la liquidación
Con pre-despacho: abres la liquidación en Día 10 con estimado

```

### Flujo de pre-despacho

```
ESTIMADO (pre-despacho):
stock.landed.cost.product
┌────────────────────────────────────────┐
│ Product: International Freight        │
│ Label: "Flete estimado BL-2026-001"   │
│ Account: Cuenta de entrada inventario │
│ Qty: 1   Price: DOP 42,500 (estimado) │
│ Default Split: By Current Cost        │
│ Invoice: (vacío por ahora)            │
│ State: draft                          │
└────────────────────────────────────────┘
         │
         │ Cuando llega la factura real
         ▼
FACTURA REAL asociada:
  invoice_id → Factura real (posted)
         │
         │ Si hay diferencia entre estimado y real
         ▼
[Generate Entries] → crea asiento contable de diferencia
  Estimado: DOP 42,500
  Real:     DOP 41,800
  Diff:     DOP    700 → asiento a clearance_difference_account
```

### Configuración requerida

> **Inventory > Configuration > Settings:**
> - Activar **Pre-clearance** ✓
> - Configurar **Pre-clearance difference account**
>   (cuenta contable para las diferencias entre estimado y real)

---

## 8. Resumen de valoración

El tab **Valuation Summary** consolida todos los `stock.valuation.adjustment.lines` de todos los landed costs del run, agrupados por producto.

```
Landed Cost 1 (Flete USD)          Landed Cost 2 (Pre-despacho)
stock.valuation.adjustment.lines   stock.valuation.adjustment.lines
┌─────────┬────────┬──────────┐    ┌─────────┬────────┬──────────┐
│ TV      │ 35,000 │ + 3,895  │    │ TV      │ 35,000 │ + 1,000  │
│ iPhone  │ 20,000 │ + 1,114  │    │ iPhone  │ 20,000 │ +   557  │ ← mismo producto,
└─────────┴────────┴──────────┘    └─────────┴────────┴──────────┘   diferente LC
                            │                              │
                            └──────────────┬───────────────┘
                                           │ _update_summary_records()
                                           │ suma additional_landed_cost
                                           ▼
                    stock.valuation.adjustment.summary
                    ┌──────────┬─────────────┬─────────────────┬────────────────┐
                    │ Producto │ former_cost │ additional_cost │ Settlement Cost│
                    ├──────────┼─────────────┼─────────────────┼────────────────┤
                    │ TV 55"   │ 35,000 DOP  │  4,895 DOP      │  39,895 DOP    │
                    │ iPhone   │ 20,000 DOP  │  1,671 DOP      │  21,671 DOP    │
                    └──────────┴─────────────┴─────────────────┴────────────────┘

  former_cost     = valor por unidad ANTES de esta liquidación
  additional_cost = suma de todos los costos adicionales distribuidos / unidad
  Settlement Cost = former_cost + additional_cost (en esta liquidación)
  Cost Factor     = Settlement Cost / former_cost  (ej: 1.14 = 14% más caro)

  El widget ▲▼ compara el Cost Factor actual vs la liquidación anterior
  del mismo producto (busca en runs anteriores no cancelados)
```

---

## 9. Configuración inicial

### Paso 1: Módulos a instalar

```
stock_landed_costs          ← Odoo nativo (requerido)
stock_landed_costs_features ← Este módulo (requerido)
stock_landed_costs_file     ← Opcional: vincula expedientes (LC Files) a runs
```

### Paso 2: Configuración de inventario

```
Inventory > Configuration > Settings

[✓] Landed Costs
    └── Activar costos de aterrizaje

[✓] Pre-clearance (si se usa)
    └── Pre-clearance difference account: [cuenta contable]
```

### Paso 3: Configuración de productos de costo

Los productos que representan costos de importación deben configurarse como:

```
product.template / product.product:

  Type:             Service  ← siempre
  landed_cost_ok:   True     ← activar "Can be a Landed Cost"
  split_method_landed_cost:  [método por defecto]  ← configurable

  Si es un arancel (tariff):
    tariff_ok:      True
    tariff_product_id: [producto al que aplica el arancel]
```

### Paso 4: Método de costeo de productos importados

Los productos que se importan deben tener una categoría con:

```
product.category:
  Costing Method:  Average Cost (AVCO) ← recomendado para importaciones
                   o First In First Out (FIFO)
  Inventory Valuation: Automated ← para que Odoo ajuste el costo automáticamente
```

### Paso 5: Permisos de usuario

| Grupo | Acceso |
|-------|--------|
| `Inventory / User` | Ver y crear runs |
| `Accounting / Billing` | Ver facturas vinculadas |
| `Landed Cost Pre-clearance` | Usar el tab de pre-despacho |
| `Accounting / Accountant` | Ver asientos contables del run |

---

## 10. Casos de uso comunes

### Caso A: Importación simple (solo facturas)

```
1. Recepción de mercancía
2. Facturas del proveedor llegan (FOB + flete en una sola factura)
3. Crear Run
4. Agregar factura al tab Vendor Bills
5. Marcar líneas de flete como is_landed_costs_line = True
6. Generate → crea LC vinculado a la factura
7. Agregar picking al LC
8. Compute → Validate
```

> **Limitación:** Este flujo requiere `stock_landed_costs_file` para que
> las líneas de factura pasen el filtro `lc_file_id ∈ run.lc_file_ids`.
> Sin ese módulo, usar el flujo de pre-despacho.

### Caso B: Importación con pre-despacho (recomendado)

```
1. Recepción de mercancía
2. Crear Run
3. Agregar facturas al tab Vendor Bills (solo para visibilidad)
4. Agregar líneas de pre-despacho con costos estimados
5. Generate → crea LC desde pre-despacho
6. Agregar picking al LC
7. Compute → Validate
8. Cuando llega factura real: asociar en invoice_id de cada línea pre-despacho
9. Si hay diferencia: Generate Entries
```

### Caso C: Aranceles específicos por producto

```
Contexto: Un producto tiene arancel del 20%, otro del 8%.
El módulo puede crear líneas de arancel específicas por producto.

1. Configurar producto de costo como tariff_ok = True
2. Configurar tariff_product_id al producto que paga ese arancel
3. El módulo calcula el arancel solo sobre las unidades de ESE producto
   (no distribuye el arancel de un producto al otro)
```

---

## 11. Errores frecuentes

### "All landed cost must be linked to at least a picking"

```
Causa:  Un stock.landed.cost en el run no tiene picking_ids asignado.
Solución: En el tab Landed Costs, abrir cada LC y agregar el picking
         correspondiente antes de validar el run.
```

### "Cannot validate this document because not all pre-clearance difference entries are posted"

```
Causa:  Hay líneas de pre-despacho con diferencia entre estimado y factura real,
        y no se han generado los asientos de diferencia.
Solución: Botón "Generate Entries" en el tab Pre-clearance Products.
```

### "Only draft landed costs can be validated"

```
Causa:  El run ya fue validado o cancelado.
Solución: Crear un nuevo run. Los runs validados son inmutables.
```

### El resumen de valoración está vacío

```
Causa:  Los landed costs no han sido computados antes de consultar el resumen.
Solución: Usar [Validate] en el run (que fuerza compute_landed_cost_all)
          o [Compute] en el tab Landed Costs antes de validar.
```

### El Cost Factor no muestra indicador ▲▼

```
Causa:  No hay runs anteriores para el mismo producto (primera importación)
        o el run anterior está cancelado.
Comportamiento esperado: el widget solo aparece cuando existe historial.
```

---

## Referencia rápida de campos

| Modelo | Campo | Descripción |
|--------|-------|-------------|
| `stock.landed.cost.run` | `vendor_bill_ids` | Facturas proveedor de esta importación |
| `stock.landed.cost.run` | `product_ids` | Líneas de pre-despacho |
| `stock.landed.cost.run` | `landed_cost_ids` | LCs generados (Odoo nativo) |
| `stock.landed.cost.run` | `summary_ids` | Resumen consolidado por producto |
| `stock.landed.cost.run` | `fob_currency` | Suma de `former_cost` del resumen |
| `stock.landed.cost.run` | `additional_cost_total_currency` | Suma de costos adicionales |
| `stock.landed.cost.run` | `amount_total_currency` | FOB + Additional (total importación) |
| `account.move` | `general_split_method` | Default Split Method para cuando se generen LCs |
| `stock.landed.cost.product` | `general_split_method` | Default Split Method del pre-despacho |
| `stock.landed.cost.line` | `split_method` | Método real usado en el cálculo |
| `stock.valuation.adjustment.summary` | `former_cost` | Valor antes de esta liquidación |
| `stock.valuation.adjustment.summary` | `additional_landed_cost` | Costo adicional asignado |
| `stock.valuation.adjustment.summary` | `final_cost` | Settlement Cost (en esta liquidación) |
| `stock.valuation.adjustment.summary` | `cost_factor_currency` | Ratio final/former |

---

*Módulo: `stock_landed_costs_features` v17.0.1.0.6 — INDEXA SRL / Progressa Group*
