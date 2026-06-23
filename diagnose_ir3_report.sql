-- =====================================================================
-- Diagnóstico IR-3 / TSS  —  descompone las casillas 3 y 4 por regla y
-- por empleado, para ver de dónde sale cada monto y detectar el
-- doble-conteo de Horas Nocturnas (HNI).
--
-- Uso:
--   psql -v company=1 -v mstart=2026-05-01 -v mend=2026-05-31 \
--        -f diagnose_ir3_report.sql -d <base>
--
-- Casilla 3 (Sueldos / Salario_ISR) suma:
--   APAGAR (hr_rule_base) + COM (hr_rule_commissions) + HNI (hr_rule_night_hours)
-- Casilla 4 (Otras Remuneraciones) suma:
--   categoría hr_payroll_taxable_alw  +  VAC (hr_rule_vacations)
-- =====================================================================
\set ON_ERROR_STOP on

DROP TABLE IF EXISTS _ids, _plines, _tagged;

CREATE TEMP TABLE _ids AS
SELECT
    (SELECT res_id FROM ir_model_data WHERE module='l10n_do_hr_payroll' AND name='hr_rule_base')          AS r_apagar,
    (SELECT res_id FROM ir_model_data WHERE module='l10n_do_hr_payroll' AND name='hr_rule_commissions')   AS r_com,
    (SELECT res_id FROM ir_model_data WHERE module='l10n_do_hr_payroll' AND name='hr_rule_night_hours')   AS r_hni,
    (SELECT res_id FROM ir_model_data WHERE module='l10n_do_hr_payroll' AND name='hr_rule_vacations')     AS r_vac,
    (SELECT res_id FROM ir_model_data WHERE module='l10n_do_hr_payroll' AND name='hr_payroll_taxable_alw') AS c_alw;

CREATE TEMP TABLE _plines AS
SELECT s.employee_id, pl.salary_rule_id AS rule_id, sr.category_id, pl.total
FROM hr_payslip_line pl
JOIN hr_payslip p    ON p.id = pl.slip_id
JOIN hr_salary_rule sr ON sr.id = pl.salary_rule_id
JOIN (SELECT id, employee_id FROM hr_payslip) s ON s.id = p.id
WHERE p.company_id = :company
  AND p.state IN ('validated','paid')
  AND p.date_to >= DATE :'mstart'
  AND p.date_to <= DATE :'mend';

CREATE TEMP TABLE _tagged AS
SELECT
    l.employee_id, l.rule_id, l.total,
    (l.rule_id IN (i.r_apagar, i.r_com, i.r_hni))                                          AS in_box3,
    ((l.category_id = i.c_alw AND l.rule_id NOT IN (i.r_apagar,i.r_com,i.r_hni)) OR l.rule_id = i.r_vac) AS in_box4_fixed,
    ((l.category_id = i.c_alw) OR (l.rule_id = i.r_vac))                                    AS in_box4_current,
    (l.rule_id = i.r_hni)                                                                   AS is_hni
FROM _plines l CROSS JOIN _ids i;

\echo '=== TOTAL COMPAÑIA (casilla3, casilla4 con-bug, casilla4 corregido, HNI doble-contado) ==='
SELECT
    round(SUM(total) FILTER (WHERE in_box3), 2)          AS box3_sueldos,
    round(SUM(total) FILTER (WHERE in_box4_current), 2)  AS box4_actual_con_bug,
    round(SUM(total) FILTER (WHERE in_box4_fixed), 2)    AS box4_corregido,
    round(SUM(total) FILTER (WHERE is_hni), 2)           AS hni_doble_contado
FROM _tagged;

\echo '=== CASILLA 3 (Sueldos) por regla ==='
SELECT sr.code AS regla, COALESCE(sr.name->>'es_DO', sr.name->>'en_US') AS nombre, round(SUM(t.total),2) AS monto
FROM _tagged t JOIN hr_salary_rule sr ON sr.id = t.rule_id
WHERE t.in_box3 GROUP BY sr.code, COALESCE(sr.name->>'es_DO', sr.name->>'en_US') ORDER BY 3 DESC;

\echo '=== CASILLA 4 (Otras Remuneraciones) por regla — marca doble-conteo ==='
SELECT sr.code AS regla, COALESCE(sr.name->>'es_DO', sr.name->>'en_US') AS nombre, round(SUM(t.total),2) AS monto,
       CASE WHEN bool_or(t.is_hni) THEN '<< tambien en casilla 3 (doble-conteo)' ELSE '' END AS nota
FROM _tagged t JOIN hr_salary_rule sr ON sr.id = t.rule_id
WHERE t.in_box4_current GROUP BY sr.code, COALESCE(sr.name->>'es_DO', sr.name->>'en_US') ORDER BY 3 DESC;

\echo '=== POR EMPLEADO ==='
SELECT e.name AS empleado,
       round(SUM(total) FILTER (WHERE in_box3),2)         AS box3_sueldos,
       round(SUM(total) FILTER (WHERE in_box4_current),2) AS box4_con_bug,
       round(SUM(total) FILTER (WHERE in_box4_fixed),2)   AS box4_corregido,
       round(SUM(total) FILTER (WHERE is_hni),2)          AS hni
FROM _tagged t JOIN hr_employee e ON e.id = t.employee_id
GROUP BY e.name ORDER BY box3_sueldos DESC;

DROP TABLE IF EXISTS _ids, _plines, _tagged;
