-- Expresiones que tumban cualquier informe contable con
--   AttributeError: 'NoneType' object has no attribute 'groupdict'
--   (account_reports/models/account_report.py::_aggregation_apply_bounds)
--
-- Subformulas validos para engine='aggregation':
--   vacio | ignore_zero_division | cross_report(...) | round(n[, METHOD])
--   | if_above(CUR(x)) | if_below(CUR(x)) | if_between(CUR(x),CUR(y))     (CUR = 3 letras MAYUSCULAS)
-- Cualquier otra cosa ('-sum', 'sum', 'if_above(0)', minusculas, parentesis sin cerrar) revienta.
--
-- Read-only. xmlid vacio = reporte/linea creada o duplicada a mano (no viene de un modulo).
SELECT r.id                                   AS report_id,
       r.name->>'en_US'                       AS reporte,
       l.code                                 AS line_code,
       l.name->>'en_US'                       AS linea,
       e.id                                   AS expression_id,
       e.label,
       e.engine,
       e.subformula,
       COALESCE(d.module || '.' || d.name, '(sin xmlid: creado a mano)') AS xmlid,
       cu.login                               AS creado_por,
       e.create_date                          AS creado,
       wu.login                               AS modificado_por,
       e.write_date                           AS modificado
FROM account_report_expression e
JOIN account_report_line l ON l.id = e.report_line_id
JOIN account_report r      ON r.id = l.report_id
LEFT JOIN ir_model_data d  ON d.model = 'account.report.expression' AND d.res_id = e.id
LEFT JOIN res_users cu     ON cu.id = e.create_uid
LEFT JOIN res_users wu     ON wu.id = e.write_uid
WHERE e.engine = 'aggregation'
  AND COALESCE(e.subformula, '') <> ''
  AND e.subformula <> 'ignore_zero_division'
  AND e.subformula NOT LIKE 'cross_report%'
  AND e.subformula NOT LIKE 'round%'
  AND e.subformula NOT LIKE 'if_other_expr_%'
  AND replace(e.subformula, ' ', '') !~ '^\w*\([A-Z]{3}\(-?\d+(\.\d+)?\)(,[A-Z]{3}\(-?\d+(\.\d+)?\))?\)$'
ORDER BY r.id, l.sequence;
