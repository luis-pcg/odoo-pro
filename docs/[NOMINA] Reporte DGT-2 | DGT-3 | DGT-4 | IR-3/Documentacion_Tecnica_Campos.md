# Documentación Técnica — Campos usados por cada reporte (DGT / IR‑3 / TSS)

> | | |
> |---|---|
> | **Autor** | Luis Fernández |
> | **Fecha** | 2026‑06‑23 |
> | **Rama** | `19.0-feat-007-lf` |
> | **Versión Odoo** | 19.0 |
> | **Alcance** | Para cada reporte, **todos** los campos que se usan: los nuevos de esta rama **y** los campos estándar de Odoo. Cada campo indica el **modelo** y el **módulo** donde está definido. |

## Cómo leer las tablas

Columna **Módulo** = dónde está **definido** el campo:

| Módulo | Tipo | Qué aporta |
|---|---|---|
| `hr` | Core Odoo | Empleado, versión/contrato, puesto, identidad (cédula, pasaporte, sexo), fechas, salario |
| `hr_attendance` | Core Odoo | Líneas diarias de horas extra |
| `hr_payroll` | Enterprise | Nómina (`hr.payslip`, `hr.payslip.line`, reglas salariales) |
| `base` / `base_vat` | Core Odoo | Compañía y RNC (`vat`) |
| `dgii_reports` | odoo‑pro | Reporte DGII base (período, estado) |
| `l10n_do_hr` | odoo‑pro | Localización RD del empleado (NSS) |
| `l10n_do_hr_payroll` | odoo‑pro | Campos RD de nómina (agente de retención) |
| `l10n_do_hr_report_base` | 🟩 **Nuevo (esta rama)** | Hub de datos: nombre desglosado, campos/catálogos SIRLA, clave nómina, tipo ingreso, causa+% horas extra, novedades DGT‑4 |
| `dgii_ir3_report` | 🟩 **Nuevo (esta rama)** | IR‑3 dentro del reporte DGII |

> Nota v19: en Odoo 19 la identidad (`identification_id`, `passport_id`, `sex`, `job_id`) y el salario (`wage`) viven en **`hr.version`**, pero son **accesibles desde `hr.employee`** a través de la versión activa. En las tablas se indica el modelo real de definición.

---

## 1. DGT‑2 — Horas Extras (Min. Trabajo / SIRLA)

**Qué se lee:** una fila por empleado y por día con horas extra.
**Modelo principal:** `hr.attendance.overtime.line`

| Campo | Modelo | Módulo | Tipo | Descripción |
|---|---|---|---|---|
| `employee_id` | hr.attendance.overtime.line | `hr_attendance` | Many2one → hr.employee | Empleado |
| `date` | hr.attendance.overtime.line | `hr_attendance` | Date | Día de la hora extra |
| `duration` | hr.attendance.overtime.line | `hr_attendance` | Float | Horas extra del día |
| `amount_rate` | hr.attendance.overtime.line | `hr_attendance` | Float | Multiplicador de pago (1.35 / 2.0) |
| `status` | hr.attendance.overtime.line | `hr_attendance` | Selection | Estado de la línea |
| `time_start` / `time_stop` | hr.attendance.overtime.line | `hr_attendance` | Datetime | Inicio / fin |
| `company_id` | hr.attendance.overtime.line | `hr_attendance` | Many2one → res.company | Compañía |
| **`l10n_do_overtime_cause_id`** | hr.attendance.overtime.line | 🟩 `l10n_do_hr_report_base` | Many2one → l10n.do.hr.overtime.cause | Causa Art. 153 |
| **`l10n_do_overtime_pct`** | hr.attendance.overtime.line | 🟩 `l10n_do_hr_report_base` | Integer (computado) | Recargo RD: `35` o `100` (derivado de `amount_rate`) |

**Identidad del empleado** (también necesaria en el reporte): ver tabla de identidad en §2.

**Catálogo de causas** — `l10n.do.hr.overtime.cause` (🟩 `l10n_do_hr_report_base`), campos `code`, `name`. Valores: a, b, c, d, e (Art. 153).

---

## 2. DGT‑3 — Plantilla de personal / ingreso (Min. Trabajo / SIRLA)

**Qué se lee:** una fila por empleado, combinando ficha + identidad + puesto + versión.

### 2.1 Identidad y datos personales — modelo `hr.employee` / `hr.version`

| Campo | Modelo | Módulo | Tipo | Descripción |
|---|---|---|---|---|
| `name` | hr.employee | `hr` | Char | Nombre completo (display) |
| `birthday` | hr.employee | `hr` | Date | Fecha de nacimiento |
| `identification_id` | hr.version | `hr` | Char | Cédula (11 díg.) — tipo `C` |
| `passport_id` | hr.version | `hr` | Char | Pasaporte — tipo `P` |
| `sex` | hr.version | `hr` | Selection | Sexo → `M` / `F` |
| `l10n_do_social_security_number` | hr.employee | `l10n_do_hr` | Char | NSS (≤ 9) — tipo `N` |
| **`first_name`** | hr.employee | 🟩 `l10n_do_hr_report_base` | Char | Nombres |
| **`first_last_name`** | hr.employee | 🟩 `l10n_do_hr_report_base` | Char | Primer apellido |
| **`second_last_name`** | hr.employee | 🟩 `l10n_do_hr_report_base` | Char | Segundo apellido |

### 2.2 Datos SIRLA — modelo `hr.employee` (🟩 todos nuevos en `l10n_do_hr_report_base`)

| Campo | Tipo | Catálogo destino | Descripción |
|---|---|---|---|
| `l10n_do_sirla_document_type` | Selection | — | Tipo de documento: `cedula` / `pasaporte` / `carnet` |
| `l10n_do_nationality_id` | Many2one | `l10n.do.hr.nationality` | Nacionalidad |
| `l10n_do_occupation_id` | Many2one | `l10n.do.hr.occupation` | Ocupación |
| `l10n_do_education_level_id` | Many2one | `l10n.do.hr.education.level` | Nivel/grado educativo |
| `l10n_do_work_shift_id` | Many2one | `l10n.do.hr.work.shift` | Turno de trabajo |
| `l10n_do_establishment_id` | Many2one | `l10n.do.hr.establishment` | Establecimiento (RNL) |
| `l10n_do_disability_ids` | Many2many | `l10n.do.hr.disability` | Discapacidad(es) |

### 2.3 Puesto — modelo `hr.job`

| Campo | Modelo | Módulo | Tipo | Descripción |
|---|---|---|---|---|
| `name` | hr.job | `hr` | Char | Nombre del puesto |
| **`l10n_do_occupation_id`** | hr.job | 🟩 `l10n_do_hr_report_base` | Many2one → l10n.do.hr.occupation | Ocupación SIRLA por defecto del puesto |

### 2.4 Versión / contrato — modelo `hr.version`

| Campo | Modelo | Módulo | Tipo | Descripción |
|---|---|---|---|---|
| `wage` | hr.version | `hr` | Monetary | Salario mensual bruto |
| `contract_wage` | hr.version | `hr` | Monetary (computado) | Salario del contrato |
| `date_start` | hr.version | `hr` | Date (computado) | Fecha de inicio |
| `contract_date_start` | hr.version | `hr` | Date | Fecha de inicio de contrato |
| `job_id` | hr.version | `hr` | Many2one → hr.job | Puesto |
| **`l10n_do_payroll_key_id`** | hr.version | 🟩 `l10n_do_hr_report_base` | Many2one → l10n.do.payroll.key | Clave de nómina (TSS) |
| **`l10n_do_income_type`** | hr.version | 🟩 `l10n_do_hr_report_base` | Selection `0001`…`0007` | Tipo de ingreso |

**Tipo de ingreso (`l10n_do_income_type`):** 0001 Normal · 0002 Ocasional · 0003 Por hora/parcial · 0004 No trabajó mes completo · 0005 Prorrateado semanal/quincenal · 0006 Pensionado pre Ley 87‑01 · 0007 Exento SDSS.

---

## 3. DGT‑4 — Novedades de personal (Min. Trabajo / SIRLA)

**Qué se lee:** una fila por novedad.
**Modelo:** `l10n.do.hr.movement` (🟩 modelo nuevo, todo en `l10n_do_hr_report_base`)

| Campo | Tipo | Descripción |
|---|---|---|
| `employee_id` | Many2one → hr.employee (req.) | Empleado |
| `movement_type` | Selection `NI` / `NS` / `NC` (req.) | NI = Nuevo Ingreso · NS = Salida · NC = Cambio |
| `date` | Date (req.) | Fecha del evento |
| `reason` | Char | Motivo |
| `note` | Text | Notas |
| `name` | Char | Referencia |
| `company_id` | Many2one → res.company (req.) | Compañía |

Para los datos del empleado en la novedad, se cruza con la identidad de §2.1.

---

## 4. IR‑3 — Retenciones a asalariados (DGII) — *se genera en Odoo*

**Origen de datos:** nóminas **validadas o pagadas** del período `MM/YYYY`.

### 4.1 Reporte DGII del período — modelo `dgii.reports`

| Campo | Módulo | Tipo | Descripción |
|---|---|---|---|
| `name` | `dgii_reports` | Char | Período `MM/YYYY` |
| `company_id` | `dgii_reports` | Many2one → res.company | Compañía |
| `state` | `dgii_reports` | Selection | Estado del reporte |
| **`l10n_do_ir3_employee_count`** | 🟩 `dgii_ir3_report` | Integer | Cantidad de empleados |
| **`l10n_do_ir3_gross_income`** | 🟩 `dgii_ir3_report` | Monetary | Ingreso bruto (base salarial ISR) |
| **`l10n_do_ir3_exempt_income`** | 🟩 `dgii_ir3_report` | Monetary | Ingreso exento (0 por ahora) |
| **`l10n_do_ir3_isr_withheld`** | 🟩 `dgii_ir3_report` | Monetary | ISR retenido |
| **`l10n_do_ir3_line_ids`** | 🟩 `dgii_ir3_report` | One2many → l10n.do.ir3.report.line | Detalle por empleado |
| **`tss_filename`** / **`tss_binary`** | 🟩 `dgii_ir3_report` | Char / Binary | TXT de TSS generado |

### 4.2 Detalle por empleado — modelo `l10n.do.ir3.report.line` (🟩 `dgii_ir3_report`)

| Campo | Tipo | Descripción |
|---|---|---|
| `employee_id` | Many2one → hr.employee | Empleado |
| `document_type` | Char | Tipo de documento (`C`/`P`/`N`) |
| `document_number` | Char | Número de documento |
| `gross_income` | Monetary | Ingreso bruto (base salarial ISR del período) |
| `exempt_income` | Monetary | Ingreso exento (0) |
| `isr_withheld` | Monetary | ISR retenido |

### 4.3 Fuente del cálculo — nómina (`hr_payroll`)

| Campo | Modelo | Módulo | Uso |
|---|---|---|---|
| `state` | hr.payslip | `hr_payroll` | Filtra `validated` / `paid` |
| `date_to` | hr.payslip | `hr_payroll` | Filtra por período |
| `employee_id` | hr.payslip | `hr_payroll` | Agrupa por empleado |
| `version_id` | hr.payslip | `hr_payroll` | Versión/contrato del slip |
| `line_ids` | hr.payslip | `hr_payroll` | Líneas de nómina |
| `salary_rule_id` | hr.payslip.line | `hr_payroll` | Identifica la regla (p.ej. `ISR`) |
| `total` | hr.payslip.line | `hr_payroll` | Importe de la línea |

> El **ingreso bruto** es la base salarial ISR del período; el **ISR retenido** es el total de la regla `hr_rule_isr_employee` (`l10n_do_hr_payroll`).

---

## 5. TSS — Autodeterminación (AM) TXT — *se genera en Odoo*

Archivo `AM_<RNC>_<MMYYYY>.txt`. Cada campo del TXT sale de un campo/regla:

| Campo TXT | Modelo / regla de origen | Módulo |
|---|---|---|
| `RNC` (encabezado) | `company_id.vat` | `base_vat` |
| `Clave_Nomina` | `hr.version.l10n_do_payroll_key_id.payroll_key` | 🟩 `l10n_do_hr_report_base` |
| `Tipo_Doc` / `Numero_Documento` | `identification_id` / `passport_id` (hr) + `l10n_do_social_security_number` (l10n_do_hr) | `hr` / `l10n_do_hr` |
| `Nombres` / `1er_apellido` / `2do_apellido` | `first_name` / `first_last_name` / `second_last_name` | 🟩 `l10n_do_hr_report_base` |
| `Sexo` | `hr.version.sex` | `hr` |
| `Fecha_nacimiento` | `hr.employee.birthday` | `hr` |
| `Salario_cotizable` | regla `hr_rule_tss_calculated` | `l10n_do_hr_payroll` |
| `Aporte_voluntario` | regla `hr_payroll.COMP` | `hr_payroll` |
| `Salario_ISR` | reglas `hr_rule_base` + `hr_rule_commissions` + `hr_rule_night_hours` | `l10n_do_hr_payroll` |
| `Otras_Remuneraciones` | categoría `hr_payroll_taxable_alw` + regla `hr_rule_vacations` | `l10n_do_hr_payroll` |
| `RNC_Ced_Agente_Ret` | `hr.version.l10n_do_single_withholding_agent_partner_id.vat` | `l10n_do_hr_payroll` |
| `Remuneracion_otros_agentes` | `hr.version.l10n_do_remuneration_other_employers` | `l10n_do_hr_payroll` |
| `Saldo_favor_periodo` | categoría `hr_rule_isr_employee_credit` | `l10n_do_hr_payroll` |
| `Salario_INFOTEP` | regla `hr_rule_infotep_trading` | `l10n_do_hr_payroll` |
| `Tipo_Ingreso` | `hr.version.l10n_do_income_type` | 🟩 `l10n_do_hr_report_base` |
| `Regalia_Pascual` | regla `hr_rule_christmas_bonus` | `l10n_do_hr_payroll` |
| `PCVI` | reglas `hr_rule_pre_warning` + `hr_rule_severance_pay` + `hr_rule_employee_refund` | `l10n_do_hr_payroll` |
| `Retencion_PA` | regla `hr_rule_alimony` | `l10n_do_hr_payroll` |

> Campo del agente de retención requiere además `l10n_do_works_in_two_companies` (`l10n_do_hr_payroll`).

---

## 6. Catálogos SIRLA (modelos de apoyo) — 🟩 `l10n_do_hr_report_base`

Cargados en instalación. Se consultan para resolver los Many2one de §2.

| Modelo | Campos | Contenido |
|---|---|---|
| `l10n.do.hr.occupation` | `code`, `name`, `active` | Ocupaciones (~2.800) |
| `l10n.do.hr.nationality` | `code`, `name`, `active` | Nacionalidades |
| `l10n.do.hr.education.level` | `code`, `name`, `active` | Niveles/grados educativos |
| `l10n.do.hr.disability` | `code`, `name`, `active` | Discapacidades |
| `l10n.do.hr.overtime.cause` | `code`, `name`, `active` | Causas horas extra (Art. 153) |
| `l10n.do.hr.work.shift` | `code`, `name`, `time_start`, `time_stop`, `company_id`, `active` | Turnos |
| `l10n.do.hr.establishment` | `name`, `l10n_do_rnl_code`, `street`, `state_id`, `company_id`, `active` | Establecimientos (RNL) |
| `l10n.do.payroll.key` | `name`, `payroll_key` | Clave de nómina (TSS) |
