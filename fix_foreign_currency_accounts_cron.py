APPLY = False

cr = env.cr
cr.execute("DROP TABLE IF EXISTS fx_line, fx_account")

cr.execute("""
CREATE TEMP TABLE fx_account AS
SELECT aa.id AS account_id,
       aa.code_store->>split_part(c.parent_path, '/', 1) AS code,
       aa.name->>'en_US' AS name,
       MIN(j.currency_id) AS currency_id,
       COUNT(DISTINCT j.currency_id) AS n_currencies,
       COUNT(DISTINCT j.company_id) AS n_companies,
       string_agg(DISTINCT j.code, ', ') AS journals,
       NULL::text AS status
  FROM account_journal j
  JOIN res_company c ON c.id = j.company_id
  JOIN account_account aa ON aa.id = j.default_account_id
 WHERE j.currency_id IS NOT NULL
   AND j.currency_id <> c.currency_id
   AND aa.currency_id IS NULL
 GROUP BY aa.id, aa.code_store, c.parent_path, aa.name
""")

cr.execute("""
CREATE TEMP TABLE fx_line AS
SELECT aml.id,
       aml.account_id,
       aml.move_name,
       aml.date,
       aml.parent_state,
       aml.balance,
       aml.currency_id AS old_currency_id,
       aml.amount_currency AS old_amount_currency,
       fa.currency_id AS new_currency_id,
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
 WHERE aml.currency_id IS DISTINCT FROM fa.currency_id
""")

cr.execute("""
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
   END
""")

cr.execute("""
SELECT fa.code, fa.name, cur.name AS currency, fa.journals, fa.status,
       (SELECT COUNT(*) FROM fx_line fl WHERE fl.account_id = fa.account_id) AS lines
  FROM fx_account fa
  LEFT JOIN res_currency cur ON cur.id = fa.currency_id
 ORDER BY fa.status, fa.code
""")
report = ["MODE: %s" % ("APPLY" if APPLY else "DRY RUN (nothing saved, set APPLY = True to apply)"), "", "ACCOUNTS"]
for row in cr.dictfetchall():
    report.append("%s %s [%s] journals=%s lines=%s -> %s" % (
        row["code"], row["name"], row["currency"], row["journals"], row["lines"], row["status"]))

cr.execute("""
SELECT fa.code, fl.id, fl.date, fl.move_name, fl.parent_state, fl.balance,
       oc.name AS old_currency, fl.old_amount_currency, nc.name AS new_currency, fl.new_amount_currency, fl.reconciled_any
  FROM fx_line fl
  JOIN fx_account fa ON fa.account_id = fl.account_id
  JOIN res_currency oc ON oc.id = fl.old_currency_id
  JOIN res_currency nc ON nc.id = fl.new_currency_id
 ORDER BY fa.code, fl.date, fl.id
""")
report += ["", "LINES TO CONVERT"]
for row in cr.dictfetchall():
    report.append("%s line %s %s %s (%s) balance=%s %s %s -> %s %s%s" % (
        row["code"], row["id"], row["date"], row["move_name"] or "", row["parent_state"], row["balance"],
        row["old_currency"], row["old_amount_currency"], row["new_currency"], row["new_amount_currency"],
        " RECONCILED" if row["reconciled_any"] else ""))

if APPLY:
    cr.execute("""
    UPDATE account_move_line aml
       SET currency_id = fl.new_currency_id,
           amount_currency = fl.new_amount_currency,
           amount_residual_currency = CASE WHEN aml.amount_residual <> 0 THEN fl.new_amount_currency ELSE 0 END
      FROM fx_line fl
      JOIN fx_account fa ON fa.account_id = fl.account_id
     WHERE aml.id = fl.id
       AND fa.status LIKE 'OK%'
    """)
    lines_updated = cr.rowcount
    cr.execute("""
    UPDATE account_account aa
       SET currency_id = fa.currency_id
      FROM fx_account fa
     WHERE aa.id = fa.account_id
       AND fa.status LIKE 'OK%'
    """)
    report += ["", "APPLIED: %s lines converted, %s accounts updated" % (lines_updated, cr.rowcount)]
    env.invalidate_all()

cr.execute("DROP TABLE fx_line, fx_account")
message = "\n".join(report)
log(message)
if not APPLY:
    raise UserError(message)
