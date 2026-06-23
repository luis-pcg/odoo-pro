# Campos por reporte (DGT-2/3/4 / IR-3)

Rama `19.0-feat-007-lf`. Objetivo: campos necesarios para generar los reportes de forma externa a Odoo.

> DGT-2 / DGT-3 / DGT-4 **no** se generan en Odoo (proceso externo). El módulo `l10n_do_hr_report_base` solo persiste los datos. El IR-3 sí se computa (`dgii_ir3_report`).

Columna **Tipo** = tipo de campo Odoo (Char, Many2one, Selection, etc.).

---

## IR-3 — `l10n.do.ir3.report.line` (módulo `dgii_ir3_report`)

| Campo | Tipo | Qué es |
|---|---|---|
| `employee_id` | Many2one (`hr.employee`) | empleado |
| `document_type` | Char | tipo doc (N=SS, C=cédula, P=pasaporte) |
| `document_number` | Char | número de documento |
| `gross_income` | Monetary | ingreso bruto gravable |
| `exempt_income` | Monetary | ingreso exento |
| `isr_withheld` | Monetary | ISR retenido |
| `dgii_report_id` | Many2one (`dgii.reports`) | reporte DGII del período (MM/YYYY) |
| `company_id` | Many2one (related) | compañía |
| `currency_id` | Many2one (related) | moneda |

## IR-3 — resumen en `dgii.reports` (módulo `dgii_ir3_report`)

| Campo | Tipo | Qué es |
|---|---|---|
| `l10n_do_ir3_line_ids` | One2many | detalle por empleado |
| `l10n_do_ir3_employee_count` | Integer | cantidad de empleados |
| `l10n_do_ir3_gross_income` | Monetary | total bruto |
| `l10n_do_ir3_exempt_income` | Monetary | total exento |
| `l10n_do_ir3_isr_withheld` | Monetary | total ISR retenido |

**Fuente de cálculo IR-3** (reglas de `l10n_do_hr_payroll`, no campos nuevos):
- `gross_income` = reglas `hr_rule_base` + `hr_rule_commissions` + `hr_rule_night_hours`
- `isr_withheld` = regla `hr_rule_isr_employee`
- documento = `hr.employee.l10n_do_social_security_number` / `identification_id` / `passport_id`

---

## DGT-2/3/4 — datos del empleado, `hr.employee` (módulo `l10n_do_hr_report_base`)

| Campo | Tipo | Qué es | Reporte |
|---|---|---|---|
| `first_name` | Char | nombre | DGT + IR-3 + TSS |
| `first_last_name` | Char | primer apellido | DGT + IR-3 + TSS |
| `second_last_name` | Char | segundo apellido | DGT + IR-3 + TSS |
| `l10n_do_sirla_document_type` | Selection (cedula/pasaporte/carnet) | tipo doc SIRLA | DGT-2/3/4 |
| `l10n_do_occupation_id` | Many2one (`l10n.do.hr.occupation`) | ocupación SIRLA | DGT-2/3/4 |
| `l10n_do_nationality_id` | Many2one (`l10n.do.hr.nationality`) | nacionalidad SIRLA | DGT-2/3/4 |
| `l10n_do_education_level_id` | Many2one (`l10n.do.hr.education.level`) | nivel educación SIRLA | DGT-2/3/4 |
| `l10n_do_disability_ids` | Many2many (`l10n.do.hr.disability`) | discapacidad(es) SIRLA | DGT-2/3/4 |
| `l10n_do_work_shift_id` | Many2one (`l10n.do.hr.work.shift`) | turno SIRLA | DGT-2/3/4 |
| `l10n_do_establishment_id` | Many2one (`l10n.do.hr.establishment`) | establecimiento RNL | DGT-2/3/4 |

## DGT — ocupación por defecto del puesto, `hr.job` (módulo `l10n_do_hr_report_base`)

| Campo | Tipo | Qué es |
|---|---|---|
| `l10n_do_occupation_id` | Many2one (`l10n.do.hr.occupation`) | ocupación SIRLA por defecto del puesto |

## DGT — establecimiento, `l10n.do.hr.establishment` (módulo `l10n_do_hr_report_base`)

| Campo | Tipo | Qué es |
|---|---|---|
| `name` | Char | nombre del establecimiento |
| `l10n_do_rnl_code` | Char | código RNL |
| `company_id` | Many2one (`res.company`) | compañía |
| `street` | Char | dirección |
| `state_id` | Many2one (`res.country.state`) | provincia |
| `active` | Boolean | activo |

## DGT-4 — movimientos de personal, `l10n.do.hr.movement` (módulo `l10n_do_hr_report_base`)

| Campo | Tipo | Qué es |
|---|---|---|
| `employee_id` | Many2one (`hr.employee`) | empleado |
| `movement_type` | Selection (NI/NS/NC) | NI=ingreso, NS=salida, NC=cambio |
| `date` | Date | fecha del evento |
| `reason` | Char | motivo |
| `note` | Text | notas |
| `name` | Char | referencia |
| `company_id` | Many2one (`res.company`) | compañía |

## DGT-2 — horas extra, `hr.attendance.overtime.line` (módulo `l10n_do_hr_report_base`)

| Campo | Tipo | Qué es |
|---|---|---|
| `l10n_do_overtime_cause_id` | Many2one (`l10n.do.hr.overtime.cause`) | causa de extensión de jornada (Art. 153) |
| `l10n_do_overtime_pct` | Integer (compute, store) | % recargo (35 ó 100), derivado de `amount_rate` |

*(campos base de Odoo en la línea: `date`, horas extra, `amount_rate`)*

---

## Catálogos SIRLA (códigos exigidos por los DGT) — módulo `l10n_do_hr_report_base`

Modelos: `l10n.do.hr.occupation`, `l10n.do.hr.nationality`, `l10n.do.hr.education.level`, `l10n.do.hr.disability`, `l10n.do.hr.overtime.cause` (mixin `l10n.do.hr.catalog.mixin`).

| Campo | Tipo | Qué es |
|---|---|---|
| `code` | Char | código SIRLA |
| `name` | Char | descripción |
| `active` | Boolean | activo |

Turno `l10n.do.hr.work.shift`:

| Campo | Tipo | Qué es |
|---|---|---|
| `code` | Char | código del turno |
| `name` | Char | nombre del turno |
| `time_start` | Float | hora desde |
| `time_stop` | Float | hora hasta |
| `company_id` | Many2one (`res.company`) | compañía |
| `active` | Boolean | activo |

---

## Solo TSS (no DGT/IR-3)

Por si se descartan para DGT/IR-3:

| Campo | Modelo | Tipo | Qué es |
|---|---|---|---|
| `l10n_do_payroll_key_id` | `hr.version` | Many2one (`l10n.do.payroll.key`) | clave de nómina |
| `l10n_do_income_type` | `hr.version` | Selection (0001–0007) | tipo de ingreso |
| `l10n_do_income_type` | `hr.payslip` | Selection (related) | tipo de ingreso (espejo) |
| `payroll_key` | `l10n.do.payroll.key` | Char | clave secuencial |
| `name` | `l10n.do.payroll.key` | Char | nombre |
