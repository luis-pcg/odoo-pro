# Autodeterminación Mensual TSS — informe de hallazgos, causa y corrección

**Rama:** `19.0-fix-tss_autodeterm_fields-lf` (creada sobre `origin/19.0` @ `dc8375fa`, sin commit)
**Módulos tocados:** `l10n_do_hr_payroll` (19.0.1.0.9), `l10n_do_hr_report_base` (19.0.1.1.2)
**Replicación:** `dev_env_odoo_pro-19/replicate_tss_autodeterm_fields.sh` → DB `v19_tss_autodeterm`
**Material de referencia:** `docs/tss_file/` (instructivo v6, nómina simulada, TXT actual y esperado)

---

## Resumen

| # | Hallazgo reportado | ¿Se reprodujo? | Causa | Estado |
|---|---|---|---|---|
| 1 | Vacaciones no se suman a *Otras Remuneraciones* | **No en el flujo estándar**; sí cuando las vacaciones se pagan en una nómina aparte cuyo lote no se selecciona en el asistente | Alcance del asistente, no cálculo | Aclarado + campo reforzado |
| 2 | *Salario Cotizable INFOTEP* queda en `Salario_SS − 1.00` en empleados con vacaciones | **Sí, exacto** | La regla `COTINF` resta `inputs['VAC']['amount']` (bandera = 1) en vez del monto calculado de la regla `VAC` | Corregido |
| 3 | *Salario Cotizable INFOTEP* se envía con monto aun siendo igual a `Salario_SS` | **Sí, exacto** | El constructor del TXT solo aplica la regla "reportar solo si difiere" a `Salario_ISR`, nunca a INFOTEP | Corregido |

---

## Replicación

Se levantó una DB Odoo 19 con `tss_report` y se sembró la nómina simulada de
`02_Nomina_Simulada_TSS.xlsx` (5 empleados ficticios, período 07/2026, RNC 999999999).
Las vacaciones se capturaron como la entrada `VAC` con valor `1`, que es el modo
"calcular vacaciones" de la regla `hr_rule_vacations` — es lo que produce la
diferencia de RD$1.00 reportada, y por tanto lo que usó quien levantó el caso.

**Antes de la corrección:**

```
Empleado               Salario_SS    Salario_ISR    Otras_Remun        INFOTEP
Laura Mendez             49250.00       49250.00           0.00       49250.00
Mateo Vargas             56549.73       52000.00        4549.73       56548.73   ← Salario_SS − 1.00
Camila Reyes             86999.58       80000.00       26999.58       86998.58   ← Salario_SS − 1.00
Diego Castillo           60000.00       60000.00       10000.00       60000.00
Valeria Santos           30000.00       30000.00           0.00       30000.00
```

En el TXT, el campo INFOTEP (pos. 293-308) salía con monto en los cinco casos,
incluidos Laura, Diego y Valeria, donde es idéntico a `Salario_SS`.

> Los montos de vacaciones (4 549.73 y 6 999.58) no coinciden con los del Excel
> (8 400 y 12 750) porque la regla `VAC` los calcula con los parámetros vigentes
> (`DIAS_LAB_MES` = 23.83, `VAC_DAYS` = 14). El comportamiento es el mismo; solo
> cambia la cifra.

---

## Hallazgo 1 — Vacaciones en *Otras Remuneraciones*

### Lo que se encontró

En el flujo estándar (vacaciones en la misma nómina del período) **Odoo ya suma
las vacaciones a Otras Remuneraciones**. En la replicación:

- Mateo: `Otras_Remun = 4 549.73` = solo vacaciones.
- Camila: `Otras_Remun = 26 999.58` = 20 000 incentivo + 6 999.58 vacaciones.

`_get_period_remuneration` suma la categoría *Otras Remuneraciones* (`OREM`) **más**
la línea de la regla `VAC` — que vive en la categoría *Salario Ordinario* porque
también alimenta `Salario_SS`. Esa suma existe desde 2021 y está igual en 17.0 y 19.0.

Es decir: la columna «Otras Rem. Odoo» del Excel (0 para Mateo, 20 000 para Camila)
no corresponde a lo que el módulo emite en ese escenario.

### El escenario donde el síntoma sí ocurre

Se reprodujo el síntoma exacto pagando las vacaciones en una **nómina extraordinaria
en un lote distinto** del mismo mes, y generando el archivo con **solo el lote regular
seleccionado**:

```
Wizard con SOLO el lote regular seleccionado:
  Salario_SS  = 112400.00     ← incluye las vacaciones (acumulado por categoría)
  Otras_Remun = 0.00          ← la línea VAC no está en ese payslip
```

`Salario_SS` viene de la regla `SALTSS`, que acumula la categoría *Salario Ordinario*
sobre todo el rango de fechas (`_sum_category`), por lo que ve las vacaciones aunque
estén en otra nómina. `Otras Remuneraciones`, en cambio, se lee de las líneas de los
payslips que el asistente recibe. Si el lote de vacaciones no se selecciona, el monto
no aparece.

Seleccionando **ambos** lotes el resultado es correcto:

```
Wizard con AMBOS lotes seleccionados:
  Salario_SS  = [60400.0]
  Otras_Remun = [8400.0]
  INFOTEP     = [52000.0]
```

### Acción

- **Operativa:** al generar la Autodeterminación hay que seleccionar **todos los lotes
  del mes**, incluidas las nóminas extraordinarias de vacaciones. No es un defecto de
  cálculo; es alcance de la selección.
- **Código:** se reforzó la composición del campo para que cubra lo que enumera el
  instructivo ("incentivos + vacaciones de ley + horas extras + bonos vacacionales +
  bonificaciones + **otras retribuciones complementarias**"): ahora se suman las
  categorías *Otras Remuneraciones* y *Retribuciones Complementarias* con `child_of`,
  en vez de una sola categoría con igualdad exacta. Sobre datos estándar el resultado
  no cambia (ninguna regla base usa *Retribuciones Complementarias*); sí evita que se
  pierdan reglas que un cliente cuelgue de esas categorías.

`l10n_do_hr_report_base/models/tss_computation.py`:

```python
categories = self.env.ref("l10n_do_hr_payroll.hr_payroll_taxable_alw") + self.env.ref(
    "l10n_do_hr_payroll.hr_payroll_complementary_alw"
)
payslip_line_id_alw = self.env["hr.payslip.line"].search(
    [
        ("slip_id", "in", slips.ids),
        ("category_id", "child_of", categories.ids),
    ]
)
```

---

## Hallazgo 2 — Salario cotizable INFOTEP con vacaciones (la diferencia de RD$1.00)

### Causa

La regla `hr_rule_infotep_trading` (código `COTINF`) parte del salario cotizable y
resta las vacaciones, pero tomaba el **valor crudo de la entrada** `VAC` en lugar del
**monto calculado por la regla** `VAC`:

```python
vac_payslip = inputs['VAC']['amount'] if 'VAC' in inputs and inputs['VAC']['amount'] else 0
```

La regla `hr_rule_vacations` usa la entrada `VAC` como bandera: con valor `1` calcula
el monto de vacaciones (días × salario diario); con cualquier otro valor lo toma
literal. Cuando el usuario captura `VAC = 1` — el modo normal — `COTINF` restaba
**1.00 peso** en vez de los miles de pesos de vacaciones. De ahí que INFOTEP quedara
en `Salario_SS − 1.00`.

Nota: la línea de acumulación (`payslip._sum('VAC', ...)`) sí leía la línea de nómina,
por lo que el error solo afectaba a la nómina en curso.

### Corrección

`l10n_do_hr_payroll/data/hr_salary_rule.xml`, regla `hr_rule_infotep_trading`:

```python
vac_payslip = result_rules['VAC']['total'] if 'VAC' in result_rules else 0
```

`result_rules` expone el resultado de las reglas ya calculadas (`VAC` es secuencia 13,
`COTINF` es 190), así que se resta el monto real de vacaciones. Sin regresión posible:

| Caso | Antes | Después |
|---|---|---|
| Entrada `VAC = 1` (modo cálculo) | resta 1.00 ✗ | resta el monto calculado ✓ |
| Entrada `VAC = N` (monto directo) | resta N | resta N (igual) |
| Sin entrada `VAC` | resta 0 | resta 0 (igual) |

**Ojo — esto también corrige montos de nómina, no solo el TXT.** La contribución
patronal de INFOTEP (`hr_rule_infotep_contribution`, `INFC = COTINF × %`) se calculaba
sobre una base inflada por el monto de vacaciones. A partir de esta corrección el
aporte de INFOTEP baja en los períodos con vacaciones, que es lo correcto: las
vacaciones de ley no son cotizables para INFOTEP. Conviene avisarlo antes de subirlo a
producción.

---

## Hallazgo 3 — INFOTEP debe ir en cero cuando es igual a Salario_SS

### Causa

El instructivo v6 (pág. 22) indica que *Salario Cotizable INFOTEP* se reporta
únicamente cuando difiere de `Salario_SS`; en caso contrario se llena con cero.
El constructor del TXT aplicaba esa regla a `Salario_ISR` pero nunca a INFOTEP:

```python
SALARIO_ISR = str("{:.2f}".format(float(d["Salario_ISR"][index]))).zfill(16)
if SALARIO_COTIZ == SALARIO_ISR:            # ← solo ISR
    SALARIO_ISR = f"{0:.2f}".zfill(16)
...
SALARIO_INFOTEP = str("{:.2f}".format(float(d["Salario_INFOTEP"][index]))).zfill(16)
```

### Corrección

`l10n_do_hr_report_base/models/tss_txt_builder.py`, en `_tss_build`:

```python
SALARIO_INFOTEP = str("{:.2f}".format(float(d["Salario_INFOTEP"][index]))).zfill(16)
# Layout v6 p. 22: the INFOTEP taxable salary is only reported when
# it differs from Salario_SS; otherwise it must be filled with zero.
if SALARIO_INFOTEP == SALARIO_COTIZ:
    SALARIO_INFOTEP = f"{0:.2f}".zfill(16)
```

Se compara la cadena ya formateada a 16 posiciones, igual que se hace con
`Salario_ISR`, para que la comparación sea exactamente la que se escribe al archivo.

---

## Resultado después de la corrección

```
Empleado               Salario_SS    Salario_ISR    Otras_Remun        INFOTEP
Laura Mendez             49250.00       49250.00           0.00       49250.00
Mateo Vargas             56549.73       52000.00        4549.73       52000.00   ← ya excluye vacaciones
Camila Reyes             86999.58       80000.00       26999.58       80000.00   ← ya excluye vacaciones
Diego Castillo           60000.00       60000.00       10000.00       60000.00
Valeria Santos           30000.00       30000.00           0.00       30000.00
```

Campos del TXT por posición (layout v6):

| Empleado | Salario_SS | Salario_ISR | Otras_Remun | INFOTEP |
|---|---|---|---|---|
| Laura | 49 250.00 | 0.00 | 0.00 | **0.00** |
| Mateo | 56 549.73 | 52 000.00 | 4 549.73 | **52 000.00** |
| Camila | 86 999.58 | 80 000.00 | 26 999.58 | **80 000.00** |
| Diego | 60 000.00 | 0.00 | 10 000.00 | **0.00** |
| Valeria | 30 000.00 | 0.00 | 0.00 | **0.00** |

Coincide con `04_AM_999999999_072026_ESPERADO_TSS.txt`: INFOTEP en cero cuando es igual
a `Salario_SS`, y con el salario sin vacaciones cuando difiere. Los campos que ya
estaban correctos (`Salario_SS`, `Salario_ISR`, ingresos exentos, regalía con código
`01`, tipo de ingreso) no cambiaron.

---

## Verificación de impacto

### Alcance real de los cambios (grep sobre todo el repo, `store-addons` y `enterprise`)

| Lo que cambió | Quién lo consume |
|---|---|
| Regla `COTINF` | `hr_rule_infotep_contribution` (`INFC`, aporte patronal) y `_get_infotep_salary` del reporte. Nada más. |
| `_get_period_remuneration` | Constructor del TXT (Otras Remuneraciones) e IR-3 casilla 4. Nada más. |
| `_tss_build` | Asistente `tss.report.wizard` y `dgii.reports.action_generate_tss`. Nada más. |

14 módulos dependen (transitivamente) de `l10n_do_hr_payroll` / `l10n_do_hr_report_base`;
ninguno de los otros 12 toca estos símbolos. En `store-addons` no hay nada que dependa
de la nómina dominicana.

La categoría *Retribuciones Complementarias* no tiene reglas asignadas en ningún módulo,
y ni ella ni *Otras Remuneraciones* tienen categorías hijas, así que el cambio a
`child_of` es inerte sobre los datos actuales.

### Suites — misma DB con los 16 módulos instalados, rama vs baseline

| Suite | Rama | Baseline |
|---|---|---|
| `dgii_ir3_report` | 9 tests | 9 tests |
| `hr_payroll` (enterprise) | 25 tests | 25 tests |
| `l10n_do_gamification_hr_news` | 12 tests | 12 tests |
| `l10n_do_hr_payroll_liquidation` | 48 tests | 48 tests |
| `l10n_do_hr_report_base` | 17 tests | 17 tests |
| `tss_report` | 7 tests | 7 tests |
| **Total** | **100 tests — 0 failed, 0 errors** | **100 tests — 0 failed, 0 errors** |

Resultado idéntico en ambos árboles. Los 16 módulos afectados instalan y cargan sus
datos sin error en las dos corridas, lo que también valida el XML modificado.

Aviso sobre cobertura: las suites propias de `l10n_do_hr_payroll` **no corren** — su
`tests/__init__.py` tiene todos los imports comentados desde la migración a v19 (usaban
`hr.contract`, fusionado en `hr.version`). El tag `payslip_computation` que se pasó
resolvió a la suite homónima de `hr_payroll` de enterprise, no a la dominicana. La
cobertura real del cálculo de nómina en v19 la aporta
`l10n_do_hr_payroll_liquidation` (48 tests, incluye `test_ordinary_payroll_unaffected.py`,
que verifica precisamente que la nómina ordinaria no se altere).

### Diff línea por línea de la nómina (rama vs baseline)

Se calcularon las 5 nóminas simuladas en ambos árboles y se comparó cada línea:
**88 líneas, 4 cambian**, todas en los dos empleados con vacaciones.

```
Camila     COTINF    86 998.58  ->  80 000.00
Camila     INFC          869.99 ->      800.00
Mateo      COTINF    56 548.73  ->  52 000.00
Mateo      INFC          565.49 ->      520.00
```

Sin cambios en `NET`, `BRUTO`, `ISR`, `SFSE`, `SVDSE`, `SALTSS`, `SALDGII`, `APAGAR`,
`VAC`, `INC`, `REPA` ni en ninguna otra línea, en ninguno de los 5 empleados.

`INFC` es aporte patronal (categoría `COMP`, `appears_on_payslip = False`, excluido en
liquidaciones), no retención al empleado: por eso el neto a pagar no se mueve. Lo que sí
cambia es el costo patronal — dashboard de costo por empleado, la línea de aporte en el
asiento de nómina y el monto a pagar a INFOTEP — que baja el 1% del monto de vacaciones.

### Diff campo por campo del TXT generado (rama vs baseline)

```
LAURA     INFOTEP  '0000000049250.00' -> '0000000000000.00'
MATEO     INFOTEP  '0000000056548.73' -> '0000000052000.00'
CAMILA    INFOTEP  '0000000086998.58' -> '0000000080000.00'
DIEGO     INFOTEP  '0000000060000.00' -> '0000000000000.00'
VALERIA   INFOTEP  '0000000030000.00' -> '0000000000000.00'

Campos que cambian: ['INFOTEP']
Campos intactos   : Tipo_reg, Clave_nom, Tipo_doc, Num_doc, Nombres, Apellido1,
                    Apellido2, Sexo, Fecha_nac, Salario_SS, Aporte_vol, Salario_ISR,
                    Otras_Remun, RNC_agente, Rem_otros_ag, Ingr_exento, Saldo_favor,
                    Tipo_ingreso, y el bloque de códigos 01/02/03 (pos. 313+)
```

Encabezado (`EAM…`) y registro de cierre (`S000007`) idénticos, y la longitud de cada
línea no cambia — no hay corrimiento de posiciones en el ancho fijo. `Otras_Remun` sale
byte a byte igual, lo que confirma que el cambio a `child_of` no altera los valores
actuales (y por lo tanto tampoco la casilla 4 del IR-3, que usa la misma función).

---

## Pendientes / notas

1. **Aviso a producción:** el cambio en `COTINF` reduce el aporte patronal de INFOTEP
   (`INFC`) en los períodos con vacaciones. Es la base correcta, pero cambia números de
   nómina ya emitidos; conviene confirmarlo con el cliente antes de desplegar.
2. **Instrucción de uso:** generar la Autodeterminación seleccionando todos los lotes
   del mes, incluidos los extraordinarios de vacaciones (ver hallazgo 1).
3. **Fuera de alcance, detectado de paso:** al calcular la nómina regular con una
   nómina extraordinaria previa en el mismo mes, `SALTSS` del payslip regular arrastra
   el acumulado y muestra 112 400 en vez de 60 400. En el TXT no se nota (la agregación
   por documento toma el último valor no cero → 60 400), pero el valor en la línea del
   payslip es engañoso. Aparte: la regla `COM` (Comisiones) sigue con el
   `condition_python` sin `result =`, por lo que no dispara — es el defecto ya
   documentado en la incidencia de "entradas salariales que no computan"; por eso en la
   replicación las comisiones de Laura se sembraron dentro del salario base.
