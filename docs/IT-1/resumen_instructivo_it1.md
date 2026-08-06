# Resumen del Instructivo de Llenado del Formulario IT-1 (DGII 2020)

> Resumen de lectura del documento *Instructivo Llenado del Formulario IT-1 2020* (DGII /
> Impuestos Internos, Junio 2020). Texto completo en
> `Instructivo_LLENADO_IT-1_2020.md`. Vigente desde el período **enero 2020**.

---

## 1. ¿Qué es el IT-1 y para qué sirve?

El **IT-1** es la **Declaración Jurada y pago del ITBIS** — el Impuesto sobre Transferencia de
Bienes Industrializados y Servicios — que los contribuyentes presentan ante la DGII en
República Dominicana.

- **Para qué sirve:** liquidar el ITBIS de un período → determinar cuánto **impuesto se debe
  pagar** o qué **saldo queda a favor** del contribuyente.
- **Periodicidad:** **mensual** (un IT-1 por mes).
- **Lógica de fondo:** se declara el ITBIS **cobrado** en las ventas (débito fiscal), se le
  resta el ITBIS **pagado deducible** en compras (crédito fiscal / adelanto), se descuentan las
  **retenciones/percepciones** y pagos a cuenta, y se suman las **penalidades** si aplica.

### Prerrequisito obligatorio: Formatos 606 y 607

Antes de presentar el IT-1 hay que enviar:
- **Formato 606** → compras de bienes y servicios.
- **Formato 607** → ventas / ingresos.

Gran parte del IT-1 se completa **automáticamente** a partir del **Anexo A**, que a su vez se
arma con la data del 606/607 y de los **Comprobantes Fiscales Electrónicos (e-CF)**.

### Novedades 2020 (según el instructivo)

- Se incorporan los **e-CF** (Comprobantes Fiscales Electrónicos) en el Anexo A.
- Cambios de nombre en renglones del Anexo A (II, III, IV) y en casillas del IT-1.
- El antiguo **PST** (Procedimiento Simplificado de Tributación) pasa a llamarse **RST**
  (Régimen Simplificado de Tributación) en las casillas 44, 45, 46, 53, 54 y 55.

---

## 2. Dos documentos: Anexo A y Formulario IT-1

El instructivo explica el llenado en **dos partes**:

| Documento | Qué contiene | Cómo se llena |
|---|---|---|
| **Anexo A** | El detalle: operaciones por tipo de NCF, por tipo de venta, por tipo de ingreso, retenciones, constructoras, comisionistas, datos informativos y el desglose del **ITBIS pagado** (con la proporcionalidad) | Se alimenta del **606/607** (en gran parte automático en la Oficina Virtual) |
| **Formulario IT-1** | El resumen y la **liquidación** del impuesto | Muchas casillas **provienen** del Anexo A; otras se calculan o se digitan |

> El módulo `l10n_do_it1_report` reproduce el **Formulario IT-1** (no el Anexo A).

---

## 3. Estructura del Anexo A

- **I. Datos Generales** — datos del contribuyente (automáticos en Oficina Virtual).
- **II. Operaciones por tipo de NCF** (reportadas en 607 / Libro de Ventas / e-NCF) — cantidad y
  monto facturado (sin impuestos) por tipo de comprobante: crédito fiscal (01/31), consumo
  (02/32), nota débito (03/33), nota crédito (04/34), registro único de ingresos (12), regímenes
  especiales (14/44), gubernamentales (15/45), exportaciones (16/46), más "otras operaciones"
  positivas/negativas. **Casilla 11 = Total operaciones** (1+2+3+5+6+7+8+9 − 4 − 10).
- **III. Operaciones por tipo de venta** (monto **con** impuestos) — efectivo, cheque/transfer.,
  tarjeta, crédito, bonos, permutas, otras. **Casilla 19 = total**.
- **IV. Operaciones por tipo de ingreso** (sin impuestos) — por operaciones, financieros,
  extraordinarios, arrendamientos, venta de activos depreciables, otros. **Casilla 26 = total**.
- **V. Pagos computables por retenciones/percepción** — ITBIS que **le retuvieron** al
  contribuyente: Norma 08-04 (tarjetas), 02-05 (BSP-IATA / honorarios / hoteles), retención de
  entidades del Estado, ITBIS percibido. **Casilla 33 = total**.
- **VI. Operaciones de Constructoras** — dirección técnica, contrato de administración,
  asesorías/honorarios (Norma 07-07). Calcula el monto sujeto a ITBIS.
- **VII. Operaciones de Comisionistas** — ventas de bienes/servicios por comisión.
- **VIII. Datos Informativos** — notas de crédito > 30 días, facturas a regímenes especiales (del
  606). No afectan la liquidación.
- **IX. ITBIS Pagado** — el más importante para el crédito fiscal. Se clasifica el ITBIS pagado
  (compras locales / servicios / importaciones) en:
  - **A) No Deducible** (va al costo/gasto): producción de exentos, activos categoría I, otros.
  - **B) Deducible** (adelanto): producción/venta de exportados, de bienes gravados, de servicios
    gravados. **Casilla 52 = total deducible no sujeto a proporcionalidad**.
  - **C) ITBIS sujeto a Proporcionalidad** (Art. 349) — ver sección 5.
  - **Casilla 56 = Total ITBIS Deducible** (52 + 55). Este alimenta las casillas 22–24 del IT-1.

---

## 4. Estructura del Formulario IT-1

| Sección | Contenido | Casillas |
|---|---|---|
| **II. Ingresos por Operaciones** | Total operaciones; No Gravadas (II.A) y Gravadas por tasa (II.B) | 1–15 |
| **III. Liquidación** | ITBIS cobrado − ITBIS deducible → impuesto a pagar / saldo a favor; menos pagos computables | 16–34 |
| **IV. Penalidades** | Recargos, interés indemnizatorio, sanciones | 35–37 |
| **V. Monto a Pagar** | Total a pagar operacional | 38 |
| **A. ITBIS Retenido / Percibido** | El contribuyente como **agente de retención** sobre sus proveedores | 40–63 |
| **B. Penalidades** | Penalidades sobre las retenciones | 64–66 |
| **C. Monto a Pagar** | Total a pagar por retenciones | 67 |
| **Total General** | 38 + 67 | 68 |

**Liquidación (lo esencial):**
- ITBIS cobrado = tasa × base gravada (casillas 16–21).
- ITBIS deducible = ITBIS pagado admitido (casillas 22–25, viene del Anexo A casilla 56).
- **Impuesto a pagar (26) = ITBIS cobrado (21) − ITBIS deducible (25)** si es positivo.
- **Saldo a favor (27)** si es negativo.
- Luego se descuentan: saldos compensables (28), saldo a favor anterior (29), pagos por
  retenciones (30), otros pagos a cuenta (31), compensaciones (32) → **diferencia a pagar (33)**
  o **nuevo saldo a favor (34)**.

**Sección A — el contribuyente como agente de retención:** cuando paga a ciertos proveedores
(personas físicas, sociedades por Normas 07-09 / 02-05 / 07-07, contribuyentes RST, o por
comprobante de compras Norma 05-19) debe **retener** ITBIS y enterarlo a la DGII. Las bases
(montos pagados) están en las casillas 40–49 y el ITBIS retenido (por tasa) en 50–60. Debe
**coincidir con el Formato 606**.

---

## 5. Proporcionalidad del ITBIS (Art. 349 CT, Reglamento 50-13)

Es el cálculo más delicado del formulario.

**Cuándo aplica:** cuando el contribuyente realiza operaciones **gravadas Y exentas** y pagó
ITBIS en compras/importaciones **sin poder discriminar** a cuáles operaciones se destinó
(ej.: publicidad, alquiler de local, asesorías, servicios telefónicos/legales, empaque).

**Regla del coeficiente:**

```
              Op. gravadas + Exportaciones de bienes + Exentas por destino
Coeficiente = ----------------------------------------------------------- × 100
                          Total de operaciones del período

ITBIS admitido = ITBIS sujeto a proporcionalidad × Coeficiente
```

- Al **numerador**: operaciones gravadas + exportaciones de bienes + exentos por destino de
  bienes/servicios gravados.
- Al **denominador**: todas las operaciones del período.
- **Se excluyen** (numerador y denominador): venta/exportación de bienes de capital usados, y
  operaciones inmobiliarias o financieras no habituales (financiera no habitual = no excede 15%
  del total de operaciones).

**No aplica proporcionalidad:**
- Contribuyentes con operaciones 100% gravadas, o 100% exentas.
- Cuando todas las ventas son gravadas y las únicas exentas son **por destino**.

> El instructivo trae **6 ejemplos** numéricos (supermercado, persona física con cursos,
> industria importadora, embotelladora, productos químicos con zona franca, exportador con
> arrendamiento) que muestran el cálculo del coeficiente y el ITBIS admitido.

---

## 6. Penalidades (Art. 252 CT)

Aplican al declarar/pagar **fuera de plazo**:

- **Recargos:** 10% por el primer mes o fracción + **4%** adicional por cada mes o fracción
  siguiente.
- **Interés indemnizatorio:** **1.10%** acumulativo por cada mes o fracción, sobre el monto a
  pagar.
- **Sanciones:** las que imponga la DGII.

> Solo se digita el **%**; el monto lo calcula el formulario. La DGII ofrece una **calculadora de
> recargos** en su portal.

---

## 7. Notas y validaciones importantes (Oficina Virtual)

- Las casillas 1–8 del **Anexo A** se completan automáticamente desde el **607**, **salvo** para
  contribuyentes RST, obligados al Libro de Ventas de Soluciones Fiscales, o que facturan con
  **e-CF**.
- **Casilla 29 (saldo a favor anterior)** se valida contra el saldo a favor del período anterior
  en la **cuenta corriente** del contribuyente.
- **ITBIS deducible (casilla 56)** no puede exceder la columna "ITBIS por adelantar" del **606**.
- **Impuesto a pagar por retenciones (casilla 60)** debe coincidir con el total de retenciones
  del **606**; si es menor, la Oficina Virtual no permite remitir.
- **Coeficiente de proporcionalidad** se valida con la distribución de ingresos del IT-1; si no
  cuadra, no deja remitir.
- **Percepción** (Anexo A casilla 32 / IT-1 casilla 59): **no habilitada** mientras no exista
  normativa que establezca un régimen de percepción.
- Las **retenciones a personas físicas** deben estar previamente en la declaración **IR-17**.
- Si se declaró por Oficina Virtual y hay error, se puede **eliminar y volver a presentar**
  dentro de la fecha hábil.

---

## 8. Glosario rápido

- **ITBIS:** Impuesto sobre Transferencia de Bienes Industrializados y Servicios (IVA dominicano).
- **NCF / e-CF:** Número de Comprobante Fiscal / Comprobante Fiscal Electrónico.
- **606 / 607:** formatos de envío de compras / ventas a la DGII.
- **Débito fiscal:** ITBIS cobrado en ventas. **Crédito fiscal / adelanto:** ITBIS pagado
  deducible en compras.
- **RST:** Régimen Simplificado de Tributación (antes PST).
- **ISFL:** Institución Sin Fines de Lucro. **DUA/DGA:** Declaración Única Aduanera / Dirección
  General de Aduanas.
- **Activos depreciables Cat. 2 y 3:** vehículos livianos, mobiliario/equipos de oficina,
  computadoras (Cat. 2); cualquier otra propiedad depreciable (Cat. 3).
