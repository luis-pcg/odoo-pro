# Fix nómina — `KeyError: 'REAL'` en la regla APAGAR (Salario a Pagar)

**Módulo:** `l10n_do_hr_payroll`
**Archivo corregido:** `data/hr_salary_rule.xml` (regla `hr_rule_base`, código `APAGAR`)
**Fecha:** 2026-07-20

---

## 1. Síntoma

Al calcular nóminas aparece, por cada empleado afectado:

```
Operación no válida
Código Python erróneo definido para:
- Regla de salario: Salario a Pagar (APAGAR)
- Error: <class 'KeyError'>: 'REAL' while evaluating
"amounttopay = contract.wage / contract.l10n_do_payment_division
if bool('REAL' in inputs and inputs['REAL']['amount']):
    result = ((inputs['REAL'] and inputs['REAL']['amount']) if inputs['REAL']['amount'] > 1 else 0)
elif bool('DLAB' in inputs and inputs['DLAB']['amount']):
    result = (BASE / 23.83) * inputs['REAL']['amount']
else:
    result = amounttopay"
```

Empleados reportados: *Yulianny Aybar Nelson*, *ELIESTHER FRANCISCO VASQUEZ*, *Maria Angelica Jimenez* — todos con recibo de nómina que incluye el input **Días Laborados (DLAB)**.

---

## 2. Causa raíz

La regla `APAGAR` decide el monto a pagar según los inputs de la nómina:

| Rama | Condición | Se ejecuta cuando |
|------|-----------|-------------------|
| `if`   | `'REAL' in inputs and inputs['REAL']['amount']` | Hay input **Salario Real** (ingreso mitad de mes) |
| `elif` | `'DLAB' in inputs and inputs['DLAB']['amount']` | Hay input **Días Laborados** y **NO** hay REAL |
| `else` | — | Salario ordinario completo |

El cuerpo del `elif` es un **copy-paste equivocado**: la condición mira `DLAB`, pero el cálculo lee `inputs['REAL']['amount']`:

```python
elif bool('DLAB' in inputs and inputs['DLAB']['amount']):
    result = (BASE / 23.83) * inputs['REAL']['amount']   # ← 'REAL' no existe aquí
```

Cuando la nómina trae **DLAB pero no REAL** (el caso normal de un empleado que ingresó/salió a mitad de período y se le pagan días laborados), el `if` da falso por `'REAL' in inputs == False`, entra al `elif`, y al leer `inputs['REAL']` revienta con `KeyError: 'REAL'`.

> Esta rama **nunca funcionó**: siempre que se cumplía su condición, crasheaba. No hay comportamiento correcto previo que preservar en ella.

La regla hermana `BASE` (`hr_rule_basic`, misma estructura) tiene la versión **correcta**, que usa `DLAB` en el cuerpo:

```python
elif bool('DLAB' in inputs and inputs['DLAB']['amount']):
    amount_to_pay = (amount_to_pay / 23.83) * inputs['DLAB']['amount']
```

`23.83` = promedio de días laborables por mes (RD). `DLAB` = días efectivamente laborados. La rama calcula: `tarifa_diaria × días_laborados`.

---

## 3. Por qué reaparece en CADA deploy de Odoo.sh

`data/hr_salary_rule.xml` se carga con `<odoo>` **sin `noupdate="1"`** → `noupdate=0`.

Consecuencia:

1. Alguien "arregla" la regla a mano en la UI de producción (Nómina → Configuración → Reglas salariales → APAGAR) y las nóminas vuelven a calcular.
2. Llega el siguiente deploy. Odoo.sh corre `-u l10n_do_hr_payroll` (o `-u all`).
3. Odoo **recarga** `hr_salary_rule.xml` y **sobrescribe** el campo `amount_python_compute` con el texto buggy del archivo.
4. El fix manual desaparece → el `KeyError` vuelve.

Bucle: **cada deploy revierte el arreglo de la UI.** La única solución permanente es corregir el XML fuente (lo que hace este parche): como `noupdate=0`, el próximo `-u` escribirá el código correcto y quedará estable.

---

## 4. El fix

`l10n_do_hr_payroll/data/hr_salary_rule.xml`, regla `APAGAR` (`hr_rule_base`):

```diff
 elif bool('DLAB' in inputs and inputs['DLAB']['amount']):
-    result = (BASE / 23.83) * inputs['REAL']['amount']
+    result = (BASE / 23.83) * inputs['DLAB']['amount']
 else:
     result = amounttopay
```

**Cambio mínimo:** solo la clave que crashea (`inputs['REAL']` → `inputs['DLAB']`).
Se deja intacto `BASE / 23.83` (la base del multiplicador, la parte sensible del cálculo) porque:
- El `if` (rama REAL) sigue igual.
- El `else` (rama salario ordinario) sigue igual.
- Solo se repara la rama DLAB para que produzca `tarifa_diaria × días_laborados`, alineada con la regla hermana BASE.

⚠️ **No es un tema de indentación.** La indentación del bloque ya es correcta (4 espacios, `if/elif/else` al mismo nivel). El bug es puramente la clave del diccionario en el cuerpo del `elif`.

---

## 5. Cómo replicar el caso en un entorno Odoo.sh

### 5.a — Rápido y determinista (script de shell, read-only)

Toma el código **tal como está en la base** y lo evalúa contra el escenario que rompe (DLAB sin REAL). No crea nóminas ni modifica datos.

Script: [`docs/repro/apagar_keyerror_real.py`](repro/apagar_keyerror_real.py)

**En Odoo.sh:** *Branch → Shell*, y luego:

```bash
odoo-bin shell -d $PGDATABASE --no-http < /home/odoo/src/user/../repro/apagar_keyerror_real.py
# o pegar el contenido del script tras abrir:  odoo-bin shell -d $PGDATABASE
```

**En el dev-env local (docker):**

```bash
docker exec -i ${ODOO_DEVELOPER}_v17 \
  odoo shell -d <DB> --no-http < docs/repro/apagar_keyerror_real.py
```

Salida esperada **con el bug**:

```
REPRODUCIDO  ->  KeyError: 'REAL'
```

Salida esperada **ya corregido** (tras `-u l10n_do_hr_payroll`):

```
SIN ERROR  ->  result = 12589.17
```

### 5.b — Reproducción end-to-end en la UI (nómina real)

1. Empleado con contrato activo (`wage` > 0, `l10n_do_payment_division` configurado).
2. Nómina → **Recibos de nómina** → Crear, seleccionar empleado/contrato/período.
3. Pestaña **Otros inputs** → agregar línea:
   - Tipo: **Días Laborados** (`DLAB`), cantidad p. ej. `10`.
   - **NO** agregar la línea **Salario Real** (`REAL`).
4. **Calcular hoja** → aparece `KeyError: 'REAL'` en la regla APAGAR.
5. Con el fix aplicado y módulo actualizado, el mismo cálculo devuelve el salario proporcional a los días laborados sin error.

---

## 6. Verificar el fix

```bash
# 1. Actualizar el módulo (aplica el XML corregido a la base, noupdate=0)
docker exec ${ODOO_DEVELOPER}_v17 odoo -d <DB> -u l10n_do_hr_payroll --stop-after-init

# 2. Re-correr el script de reproducción -> debe imprimir "SIN ERROR"
docker exec -i ${ODOO_DEVELOPER}_v17 \
  odoo shell -d <DB> --no-http < docs/repro/apagar_keyerror_real.py

# 3. En la UI: recalcular una nómina con DLAB -> sin KeyError
```

En Odoo.sh: hacer merge del branch con el fix → el deploy corre `-u` → la regla queda corregida de forma permanente.

---

## 7. Mitigación temporal en producción (mientras se despliega)

Si urge calcular nóminas **antes** del deploy, se puede editar la regla en la UI
(Nómina → Configuración → Reglas salariales → *Salario a Pagar*, campo *Cálculo Python*),
cambiando `inputs['REAL']['amount']` por `inputs['DLAB']['amount']` en el `elif`.

⚠️ **Este cambio manual se revierte en el próximo deploy** (ver §3). Es solo un
puente; el fix definitivo es el del XML en este parche.
