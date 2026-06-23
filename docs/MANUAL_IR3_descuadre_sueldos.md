# Manual — Descuadre IR-3: "Sueldos pagados por el agente" y "Otras remuneraciones"

**Fecha:** 2026-07-01 · **Actualizado:** 2026-07-02
**Módulos:** `dgii_ir3_report`, `l10n_do_hr_report_base` (repo `odoo-pro`, rama `19.0-feat-008-lf`)
**Reporta:** contable — casillas 3 (Sueldos) y 4 (Otras Remuneraciones) del IR-3 no cuadran; ISR (casilla 8) sí cuadra.

> 📸 **Manual ilustrado con capturas del entorno (2026-07-02):**
> [`docs/manuals/dgii_ir3_descuadre_sueldos/README.md`](manuals/dgii_ir3_descuadre_sueldos/README.md)
> — reproduce el descuadre en una base limpia, demuestra el doble conteo de HNI
> con montos verificables a mano y documenta dos hallazgos adicionales de v19:
> **la regla de Comisiones (COM) no se calculaba** (regresión de migración,
> corregida en `l10n_do_hr_payroll/data/hr_salary_rule.xml`) y **el parámetro
> `REC_NOCT` no viene en la data del módulo** (crearlo a mano; sin él, las
> boletas con horas nocturnas no calculan).
>
> ⚠️ **Nota 2026-07-02:** el fix descrito en la §6 se había perdido del working
> tree (nunca llegó a commit); fue re-aplicado y re-verificado en esta fecha.

---

## 1. Resumen ejecutivo

| Casilla | Reporte | Esperado (contable) | Diferencia |
|---|---|---|---|
| 3 — Sueldos pagados por el agente | 1,854,973 | 1,765,000 | +89,973 |
| 4 — Otras remuneraciones | 367,242 | 351,086 | +16,156 |
| 8 — ISR | (cuadra) | — | 0 |

**Dos hallazgos distintos:**

1. **BUG (casilla 4): Horas Nocturnas (HNI) doble-contadas.** HNI se suma en la casilla 3 *y* otra vez en la casilla 4. La diferencia de la casilla 4 (**+16,156**) es exactamente el monto de HNI. → **Corregido.**

2. **NO es bug (casilla 3): composición del monto.** La casilla 3 no es "solo el salario base". Por diseño = **APAGAR (salario) + COM (comisiones) + HNI (horas nocturnas)**, porque las tres son gravables de ISR. El +89,973 es comisiones + nocturnas que la contable no estaba sumando. El monto del reporte es correcto; hay que explicarlo/validarlo con el diagnóstico.

---

## 2. De dónde salen los montos (fuente de datos)

Todo se recalcula en `dgii_ir3_report/models/dgii_report.py::_compute_l10n_do_ir3` a partir de los **payslips del periodo**:

Filtro de payslips (`dgii_report.py:147`):
- `company_id` = compañía del reporte
- `state IN ('validated','paid')` — borrador/hecho **no cuentan**
- `date_to` dentro del mes (tomado del campo `name`, formato `MM/YYYY`)

Agrupa por empleado. Por cada empleado:

| Casilla | Campo | Método (en `l10n_do_hr_report_base/models/tss_computation.py`) | Qué suma |
|---|---|---|---|
| **3** Sueldos | `salaries_paid` | `_get_period_isr_salary` | reglas **APAGAR** + **COM** + **HNI** |
| **4** Otras remuneraciones | `other_remuneration` | `_get_period_remuneration` | categoría `hr_payroll_taxable_alw` + regla **VAC** |
| **5** Otros agentes | `other_agents_remuneration` | `_get_agent_remuneration` | campo contrato `version_id.l10n_do_remuneration_other_employers` (manual) |
| **8** ISR | `income_tax` | filtro directo regla `hr_rule_isr_employee` | retención ISR |

**El monto del salario (regla APAGAR / `hr_rule_base`)** sale de (`l10n_do_hr_payroll/data/hr_salary_rule.xml`):

```python
amounttopay = employee.wage / employee.l10n_do_payment_division
if REAL input:  result = inputs['REAL']   # monto real digitado (si > 1)
elif DLAB input: result = daily_salary * inputs['DLAB']  # días laborados
else:            result = amounttopay
```
= `wage / l10n_do_payment_division`, salvo inputs `REAL` (monto real) o `DLAB` (días laborados). Solo en payslips normales (excluye extraordinarios).

⚠️ Estos métodos son **compartidos con el archivo TSS** (`tss_txt_builder.py`, campos `Salario_ISR` y `Otras_Remuneraciones`). El bug de doble-conteo existía igual en el TSS; el fix lo corrige en ambos y mantiene la invariante "IR-3 == TSS".

---

## 3. Causa raíz del doble-conteo

`hr_rule_night_hours` (código **HNI**) tiene categoría `hr_payroll_taxable_alw` (`hr_salary_rule.xml:180`).

- La casilla 3 la suma **explícitamente** (regla nombrada en `_get_period_isr_salary`).
- La casilla 4 barre **toda la categoría** `hr_payroll_taxable_alw` → vuelve a incluir HNI.

Resultado: HNI cuenta 2 veces → casilla 4 y total (casilla 6) inflados exactamente por el monto de HNI.

---

## 4. Replicación (validación exacta)

Script: **`replicate_ir3_double_count.sh`** (clona DB de test, inyecta un escenario controlado, corre el compute y muestra el desglose antes/después).

Escenario inyectado sobre el empleado Juan (base 28,000): **COM=50,000, HNI=16,156, INC=20,000, VAC=10,000**.

**ANTES del fix:**
```
box3 salaries_paid  = 94,156   (= APAGAR 28,000 + COM 50,000 + HNI 16,156)
box4 other_remun.   = 46,156   (= HNI 16,156 + INC 20,000 + VAC 10,000)   <- HNI repetido
total_paid          = 140,312  (doble-cuenta HNI: sobra 16,156)
```

**DESPUÉS del fix:**
```
box3 salaries_paid  = 94,156   (sin cambio)
box4 other_remun.   = 30,000   (= INC 20,000 + VAC 10,000; HNI excluido)
total_paid          = 124,156  (diferencia por doble-conteo = 0)
```

El patrón coincide con producción: la casilla 4 sobra exactamente el HNI.

---

## 5. Diagnóstico en producción (salario por salario)

Para ver **de dónde sale cada monto** en la base real, sin modificar nada:

```bash
./diagnose_ir3_report.sh <BASE_PRODUCCION> 05/2026 <COMPANY_ID>
```

(o directamente con psql: `diagnose_ir3_report.sql`, variables `company`, `mstart`, `mend`).

Salida:
- **Total compañía**: casilla 3, casilla 4 *con bug* vs *corregido*, y HNI doble-contado.
- **Casilla 3 por regla**: cuánto es APAGAR vs COM vs HNI (aquí verás que el +89,973 = comisiones + nocturnas).
- **Casilla 4 por regla**: marca la línea HNI como doble-conteo.
- **Por empleado**: box3 / box4-con-bug / box4-corregido / HNI, para conciliar salario por salario.

Corre esto sobre el periodo que reportó la contable para confirmar que:
- casilla 4 corregida == 351,086
- casilla 3 == APAGAR + COM + HNI (y decidir si COM debe o no ir en "sueldos", ver §7).

---

## 6. El fix

Archivo: `l10n_do_hr_report_base/models/tss_computation.py`

1. Nuevo helper `_l10n_do_isr_salary_rules()` — única fuente de verdad de las reglas de la casilla 3 (APAGAR, COM, HNI).
2. `_get_period_isr_salary` usa ese helper (mismo resultado que antes).
3. `_get_period_remuneration` **excluye** esas reglas del barrido de categoría:
   ```python
   ("salary_rule_id", "not in", self._l10n_do_isr_salary_rules().ids)
   ```

Efecto: ninguna regla se cuenta en la casilla 3 y en la 4 a la vez. HNI queda solo en la casilla 3 (Salario_ISR), que es su lugar correcto (es gravable de ISR). Aplica también al archivo TSS.

**Test de regresión:** `l10n_do_hr_report_base/tests/test_l10n_do_hr_report_base.py::test_night_hours_not_double_counted`.

---

## 7. Decisión pendiente (negocio) — ¿comisiones en "Sueldos"?

La casilla 3 incluye **comisiones (COM)** además del salario base. Es defendible (las comisiones son gravables de ISR = salario), pero si DGII / la contable exige que la casilla 3 sea **solo salario fijo** y las comisiones vayan a "Otras remuneraciones", es un cambio de una línea:

- Quitar `"hr_rule_commissions"` de `_l10n_do_isr_salary_rules()` (pasa a casilla 4 si su categoría se incluye) — **requiere confirmación de la contable + criterio DGII**.

No se cambió porque altera montos declarados; primero correr el diagnóstico (§5) y validar el criterio.

---

## 8. Despliegue

```bash
# actualizar los módulos en la base de producción
docker exec <odoo_container> odoo -d <BASE> -u l10n_do_hr_report_base,dgii_ir3_report --stop-after-init
```
Luego, en cada reporte DGII del periodo, botón **"Calcular IR-3"** (`action_compute_ir3`) para recomputar las casillas. Regenerar el archivo TSS si aplica.

---

## 9. Verificación realizada

- Replicación controlada: doble-conteo eliminado (total_paid diff 16,156 → 0).
- Tests módulos: **22/22 OK** antes; **16/16 OK** en `l10n_do_hr_report_base` con el test de regresión nuevo incluido; 0 fallos.
- Diagnóstico probado end-to-end sobre DB clonada.

## Archivos entregados
- `diagnose_ir3_report.sh` + `diagnose_ir3_report.sql` — diagnóstico por regla/empleado (correr en producción).
- `replicate_ir3_double_count.sh` — replicación controlada del bug.
- Fix + test en `odoo-pro` (módulos `l10n_do_hr_report_base`).
