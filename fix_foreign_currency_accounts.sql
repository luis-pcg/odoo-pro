-- Usage:
--   psql -d <db> -f fix_foreign_currency_accounts.sql                 -- dry run, ROLLBACK
--   psql -d <db> -v apply=true -f fix_foreign_currency_accounts.sql   -- COMMIT

\set ON_ERROR_STOP on
\if :{?apply}
\else
\set apply false
\endif

BEGIN;

CREATE TEMP TABLE fx_account ON COMMIT DROP AS
SELECT aa.id AS account_id,
       aa.code_store->>split_part(c.parent_path, '/', 1) AS code,
       aa.name->>'en_US' AS name,
       aa.account_type,
       aa.reconcile,
       MIN(j.currency_id) AS currency_id,
       COUNT(DISTINCT j.currency_id) AS n_currencies,
       COUNT(DISTINCT j.company_id) AS n_companies,
       string_agg(DISTINCT j.code, ', ') AS journals
  FROM account_journal j
  JOIN res_company c ON c.id = j.company_id
  JOIN account_account aa ON aa.id = j.default_account_id
 WHERE j.currency_id IS NOT NULL
   AND j.currency_id <> c.currency_id
   AND aa.currency_id IS NULL
 GROUP BY aa.id, aa.code_store, c.parent_path, aa.name, aa.account_type, aa.reconcile;

CREATE TEMP TABLE fx_line ON COMMIT DROP AS
SELECT aml.id,
       aml.account_id,
       aml.move_name,
       aml.date,
       aml.parent_state,
       aml.balance,
       aml.currency_id AS old_currency_id,
       aml.amount_currency AS old_amount_currency,
       fa.currency_id AS new_currency_id,
       aml.amount_residual,
       EXISTS (
           SELECT 1
             FROM account_partial_reconcile apr
            WHERE aml.id IN (apr.debit_move_id, apr.credit_move_id)
       ) AS reconciled_any,
       ROUND((aml.balance * to_rate.rate / company_rate.rate)::numeric, cur.decimal_places) AS new_amount_currency
  FROM account_move_line aml
  JOIN fx_account fa ON fa.account_id = aml.account_id
  JOIN res_company c ON c.id = aml.company_id
  JOIN res_currency cur ON cur.id = fa.currency_id
  CROSS JOIN LATERAL (
      SELECT COALESCE(
          (SELECT r.rate FROM res_currency_rate r
            WHERE r.currency_id = fa.currency_id
              AND (r.company_id IS NULL OR r.company_id = split_part(c.parent_path, '/', 1)::int)
              AND r.name <= aml.date
            ORDER BY r.company_id NULLS LAST, r.name DESC LIMIT 1),
          (SELECT r.rate FROM res_currency_rate r
            WHERE r.currency_id = fa.currency_id
              AND (r.company_id IS NULL OR r.company_id = split_part(c.parent_path, '/', 1)::int)
            ORDER BY r.company_id NULLS LAST, r.name ASC LIMIT 1)
      ) AS rate
  ) to_rate
  CROSS JOIN LATERAL (
      SELECT COALESCE(
          (SELECT r.rate FROM res_currency_rate r
            WHERE r.currency_id = c.currency_id
              AND (r.company_id IS NULL OR r.company_id = split_part(c.parent_path, '/', 1)::int)
              AND r.name <= aml.date
            ORDER BY r.company_id NULLS LAST, r.name DESC LIMIT 1),
          1.0
      ) AS rate
  ) company_rate
 WHERE aml.currency_id IS DISTINCT FROM fa.currency_id;

ALTER TABLE fx_account ADD COLUMN status text;
UPDATE fx_account fa
   SET status = CASE
       WHEN fa.n_currencies > 1 THEN 'SKIP: journals with different currencies'
       WHEN fa.n_companies > 1 THEN 'SKIP: journals from several companies'
       WHEN EXISTS (SELECT 1 FROM fx_line fl WHERE fl.account_id = fa.account_id AND fl.new_amount_currency IS NULL)
           THEN 'SKIP: no rate for the journal currency'
       WHEN EXISTS (SELECT 1 FROM fx_line fl WHERE fl.account_id = fa.account_id AND fl.reconciled_any)
           THEN 'SKIP: lines to convert are reconciled'
       WHEN EXISTS (SELECT 1 FROM fx_line fl WHERE fl.account_id = fa.account_id) THEN 'OK: convert lines + set currency'
       ELSE 'OK: set currency'
   END;

\echo '=== Accounts ==='
SELECT fa.account_id, fa.code, fa.name, cur.name AS currency, fa.journals, fa.status,
       (SELECT COUNT(*) FROM fx_line fl WHERE fl.account_id = fa.account_id) AS lines_to_convert
  FROM fx_account fa
  LEFT JOIN res_currency cur ON cur.id = fa.currency_id
 ORDER BY fa.status, fa.code;

\echo '=== Lines to convert ==='
SELECT fl.id, fa.code, fl.date, fl.move_name, fl.parent_state, fl.balance,
       oc.name AS old_currency, fl.old_amount_currency,
       nc.name AS new_currency, fl.new_amount_currency, fl.reconciled_any
  FROM fx_line fl
  JOIN fx_account fa ON fa.account_id = fl.account_id
  JOIN res_currency oc ON oc.id = fl.old_currency_id
  JOIN res_currency nc ON nc.id = fl.new_currency_id
 ORDER BY fa.code, fl.date, fl.id;

UPDATE account_move_line aml
   SET currency_id = fl.new_currency_id,
       amount_currency = fl.new_amount_currency,
       amount_residual_currency = CASE WHEN aml.amount_residual <> 0 THEN fl.new_amount_currency ELSE 0 END
  FROM fx_line fl
  JOIN fx_account fa ON fa.account_id = fl.account_id
 WHERE aml.id = fl.id
   AND fa.status LIKE 'OK%';

UPDATE account_account aa
   SET currency_id = fa.currency_id
  FROM fx_account fa
 WHERE aa.id = fa.account_id
   AND fa.status LIKE 'OK%';

\echo '=== Result (posted lines) ==='
SELECT fa.code, ac.name AS account_currency, lc.name AS line_currency,
       COUNT(aml.id) AS lines, SUM(aml.balance) AS balance, SUM(aml.amount_currency) AS amount_currency
  FROM fx_account fa
  JOIN account_account aa ON aa.id = fa.account_id
  LEFT JOIN res_currency ac ON ac.id = aa.currency_id
  LEFT JOIN account_move_line aml ON aml.account_id = aa.id AND aml.parent_state = 'posted'
  LEFT JOIN res_currency lc ON lc.id = aml.currency_id
 GROUP BY fa.code, ac.name, lc.name
 ORDER BY fa.code, lc.name;

\if :apply
COMMIT;
\echo 'COMMITTED'
\else
ROLLBACK;
\echo 'DRY RUN: rolled back (use -v apply=true to commit)'
\endif
