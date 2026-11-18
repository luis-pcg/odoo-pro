\pset footer off
\echo 'Novedades con monto <= 0 (no se migran a v19):'

SELECT cn.id                                 AS novedad_id,
       cn.name                               AS novedad,
       cn.amount                             AS monto,
       CASE WHEN cn.is_active THEN 'Sí' ELSE 'No' END AS activa,
       CASE WHEN cn.is_dues THEN cn.dues || ' cuotas (' || COALESCE(cn.dues_remaining, 0) || ' restantes)'
            ELSE 'Fija' END                  AS tipo,
       pit.name                              AS tipo_entrada,
       emp.name                              AS empleado,
       c.name                                AS contrato,
       co.name                               AS compania,
       (SELECT count(*) FROM hr_contract_news_hr_payslip_rel rel
         WHERE rel.hr_contract_news_id = cn.id) AS nominas_vinculadas
  FROM hr_contract_news cn
  LEFT JOIN hr_contract c ON c.id = cn.contract_id
  LEFT JOIN hr_employee emp ON emp.id = c.employee_id
  LEFT JOIN res_company co ON co.id = c.company_id
  LEFT JOIN hr_payslip_input_type pit ON pit.id = cn.input_type_id
 WHERE COALESCE(cn.amount, 0) <= 0
 ORDER BY co.name, emp.name, cn.name;

\echo 'Resumen:'

SELECT count(*)                                   AS total,
       count(*) FILTER (WHERE cn.is_active)       AS activas,
       count(*) FILTER (WHERE NOT cn.is_active)   AS inactivas,
       count(*) FILTER (WHERE cn.amount < 0)      AS negativas
  FROM hr_contract_news cn
 WHERE COALESCE(cn.amount, 0) <= 0;
