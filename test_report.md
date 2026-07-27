# 🧪 Odoo Pro v19 — Test Report

> **Generado:** 30/07/2026 00:43:27 &nbsp;|&nbsp; **Instalación:** 7s &nbsp;|&nbsp; **Tests:** 27s

---

## 📊 Resumen Ejecutivo

| KPI | Valor | Detalle |
|-----|:-----:|---------|
| **Módulos descubiertos** | 195 | 152 instalables · 43 pendientes migración |
| **Módulos instalados** | 0 / 152 | 0 fallaron · 1 incompatibles |
| **Módulos con tests** | 77 / 1 | 61 pasaron · 16 fallaron |
| **Tests individuales** | 911 | 6 assert · 35 excepciones |
| **Tasa de éxito (módulos)** | 79% | `████████████████░░░░` 79% |
| **Tasa de éxito (tests)** | 95% | `███████████████████░` 95% |

### Estado por categoría

| Estado | Módulos | Descripción |
|--------|:-------:|-------------|
| ✅ Pasaron | **61** | módulos con todos los tests en verde |
| ❌ Fallaron | **16** | módulos con fallos o errores |
| ⚠️  Con warnings | **4** | módulos con advertencias |
| ⏩ Sin tests | **150** | módulos sin directorio tests/ |
| 🔒 No instalables | **43** | installable=False — pendientes migración |
| 🚫 Incompatibles | **1** | versión incompatible con v19 |
| 🔴 Error install | **0** | fallaron durante la instalación |

---

## ✅ Tests Pasaron &nbsp; `61 módulos`

| Módulo | Tests | Tiempo | Autor | Estado |
|--------|:-----:|:------:|-------|:------:|
| `acap_bank_statement_import` | 7 | 3.88s | lfernandez | ✅ |
| `account_bank_charge_import_base` | 8 | 0.09s | luisfernandez | ✅ |
| `account_bank_charge_import_bhd` | 6 | 6.92s | luisfernandez | ✅ |
| `account_bank_charge_import_bpd` | 6 | 5.47s | luisfernandez | ✅ |
| `account_bank_statement_import_csv_patch` | 4 | 1.18s | lfernandez | ✅ |
| `account_financial_risk_features` | 18 | 1.58s | lfernandez | ✅ |
| `account_followup_extra_features` | 12 | 2.02s | luisfernandez | ✅ |
| `account_lock_fiscal_date` | 14 | 2.77s | lfernandez | ✅ |
| `account_move_route` | 5 | 2.61s | Erick Cuesto | ✅ |
| `account_multi_journal_payment_authorization_code` | 12 | 1.3s | lfernandez | ✅ |
| `account_payment_advance_payment` | 7 | 0.09s | lfernandez | ✅ |
| `account_payment_authorization_code` | 6 | 1.26s | Luis Fernandez | ✅ |
| `account_payment_internal_transfer` | 14 | 4.38s | Erick Cuesto | ✅ |
| `account_payment_reconcile_features` | 12 | 4.19s | Erick Cuesto | ✅ |
| `account_transfer_features` | 21 | 1.22s | Luis Fernandez | ✅ |
| `apap_bank_statement_import` | 7 | 1.91s | lfernandez | ✅ |
| `auto_backup_sh` ⚠️ | 28 | 0.05s | lfernandez | ✅⚠️ |
| `bdr_bank_statement_import` | 7 | 2.16s | lfernandez | ✅ |
| `bhd_bank_statement_import` | 7 | 6.61s | lfernandez | ✅ |
| `bhd_panama_bank_statement_import` | 7 | 2.51s | lfernandez | ✅ |
| `blh_bank_statement_import` | 7 | 2.05s | lfernandez | ✅ |
| `bnc_bank_statement_import` | 6 | 2.1s | lfernandez | ✅ |
| `bpd_bank_statement_import` | 8 | 2.95s | lfernandez | ✅ |
| `bpm_bank_statement_import` | 8 | 2.12s | lfernandez | ✅ |
| `bsc_bank_statement_import` | 9 | 3.87s | lfernandez | ✅ |
| `crm_helpdesk_custom` | 24 | 1.24s | lfernandez | ✅ |
| `fleet_product_management` | 24 | 0.78s | Luis Fernandez | ✅ |
| `fleet_product_rules` | 14 | 0.34s | lfernandez | ✅ |
| `helpdesk_sale_custom` | 13 | 0.83s | Erick Cuesto | ✅ |
| `jmmb_bank_statement_import` | 9 | 1.55s | Luis Fernandez | ✅ |
| `l10n_do_account_batch_payment_base` | 5 | 0.12s | luisfernandez | ✅ |
| `l10n_do_account_batch_payment_bdr` | 6 | 0.14s | luisfernandez | ✅ |
| `l10n_do_account_batch_payment_bhd` | 6 | 0.14s | luisfernandez | ✅ |
| `l10n_do_account_batch_payment_bpd` | 9 | 0.21s | luisfernandez | ✅ |
| `l10n_do_account_batch_payment_ee` | 6 | 0.12s | luisfernandez | ✅ |
| `l10n_do_bank_charges_import` | 11 | 1.5s | luisfernandez | ✅ |
| `l10n_do_currency_update` | 4 | 0.54s | Erick Cuesto | ✅ |
| `l10n_do_ecommerce` | 3 | 0.02s | Erick Cuesto | ✅ |
| `l10n_do_hr_payroll_liquidation` | 46 | 3.03s | luisfernandez | ✅ |
| `l10n_do_rnc_validation` ⚠️ | 16 | 0.22s | luisfernandez | ✅⚠️ |
| `odoo_cheque_features` | 3 | 0.07s | - | ✅ |
| `payment_azul_webpages` ⚠️ | 72 | 2.07s | Luis Fernandez | ✅⚠️ |
| `payment_azul_webservices` ⚠️ | 90 | 0.82s | luisfernandez | ✅⚠️ |
| `payment_salesperson` | 13 | 1.53s | Luis Fernandez | ✅ |
| `product_foreign_cost_price` | 9 | 0.08s | Erick Cuesto | ✅ |
| `product_price_history` | 14 | 0.42s | lfernandez | ✅ |
| `product_pricelist_user_restriction` | 13 | 0.22s | lfernandez | ✅ |
| `purchase_financial_risk` | 20 | 0.99s | Luis Fernandez | ✅ |
| `purchase_financial_risk_features` | 8 | 0.18s | lfernandez | ✅ |
| `purchase_request_features` | 3 | 0.08s | lfernandez | ✅ |
| `repair_services` | 23 | 0.81s | lfernandez | ✅ |
| `sale_crm_features` | 7 | 0.14s | lfernandez | ✅ |
| `sale_financial_risk_features` | 9 | 0.25s | lfernandez | ✅ |
| `sale_order_time_total` | 4 | 0.69s | lfernandez | ✅ |
| `sale_product_generic_readonly` | 8 | 0.19s | lfernandez | ✅ |
| `sale_stock_restriction` | 16 | 1.6s | Erick Cuesto | ✅ |
| `sale_stock_serial` | 9 | 1.36s | Erick Cuesto | ✅ |
| `scotiabank_statement_import` | 10 | 3.15s | lfernandez | ✅ |
| `stock_inventory_forecasted_report` | 48 | 0.6s | lfernandez | ✅ |
| `stock_picking_invoice_link_extra` | 7 | 2.46s | Luis Fernandez | ✅ |
| `stock_warehouse_orderpoint_uom` | 7 | 0.85s | lfernandez | ✅ |

## ❌ Tests Fallaron &nbsp; `16 módulos`

### ❌ `account_default_journals`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 2 &nbsp;|&nbsp; **Errores:** 4 &nbsp;|&nbsp; **Tests:** 8 &nbsp;|&nbsp; **Tiempo:** 2.81s

**Detalle de fallos:**

```
FAIL: TestAccountDefaultJournals.test_payment_onchange_purchase_journal
FAIL: TestAccountDefaultJournals.test_payment_onchange_sales_journal
ERROR: TestAccountDefaultJournals.test_wizard_ignores_default_if_not_in_available
ERROR: TestAccountDefaultJournals.test_wizard_multiple_moves_falls_back_to_super
ERROR: TestAccountDefaultJournals.test_wizard_single_purchase_invoice_uses_partner_journal
ERROR: TestAccountDefaultJournals.test_wizard_single_sale_invoice_uses_partner_journal
```

### ❌ `account_multi_journal_payment`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.09s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.account_multi_journal_payment.tests.test_account_multi_journal_payment.TestAccountMultiJournalPayment)
```

### ❌ `account_partner_fields`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 3 &nbsp;|&nbsp; **Tiempo:** 0.1s

**Detalle de fallos:**

```
ERROR: AccountMoveTest.test_001_onchange_type
```

### ❌ `account_payment_compensation`

> **Autor:** Fernando Figuereo &nbsp;|&nbsp; **Fallos:** 1 &nbsp;|&nbsp; **Errores:** 15 &nbsp;|&nbsp; **Tests:** 28 &nbsp;|&nbsp; **Tiempo:** 5.72s

**Detalle de fallos:**

```
ERROR: TestCompensationInvoiceFlow.test_invoice_flow_lines_have_invoice_id
ERROR: TestCompensationInvoiceFlow.test_invoice_flow_lines_have_no_payment_id
ERROR: TestCompensationInvoiceFlow.test_invoice_flow_requires_invoices_domain
ERROR: TestCompensationInvoiceFlow.test_invoice_outside_date_range_excluded
ERROR: TestCompensationInvoiceFlow.test_localdict_has_invoice_compensation_base_keys
ERROR: TestCompensationInvoiceFlow.test_localdict_payment_is_false_for_invoice_flow
ERROR: TestCompensationInvoiceFlow.test_multiple_invoices_generate_multiple_lines
FAIL: TestCompensationInvoiceFlow.test_profit_base_computed_on_post
ERROR: TestCompensationInvoiceFlow.test_rule_computes_amount_from_invoice_base
ERROR: TestCompensationInvoiceFlow.test_rule_computes_profit_amount
ERROR: TestCompensationPaymentFlow.test_invoice_profile_dispatches_to_invoice_method
ERROR: TestCompensationPaymentFlow.test_partner_with_both_profile_types_gets_both_line_sets
ERROR: TestCompensationPaymentFlow.test_payment_flow_line_references_correct_payment
ERROR: TestCompensationPaymentFlow.test_payment_flow_lines_have_payment_id
ERROR: TestCompensationPaymentFlow.test_payment_flow_requires_at_least_one_filter
```

### ❌ `l10n_do_accounting`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 2 &nbsp;|&nbsp; **Tests:** 4 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_accounting.tests.test_account_journal.AccountJournalTest)
ERROR: setUpClass (odoo.addons.l10n_do_accounting.tests.test_account_move.AccountMoveTest)
```

### ❌ `l10n_do_credit_note`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 2 &nbsp;|&nbsp; **Tests:** 4 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_credit_note.tests.test_l10n_do_credit_note.TestL10nDOCreditNoteItbis)
ERROR: setUpClass (odoo.addons.l10n_do_credit_note.tests.test_l10n_do_credit_note.TestL10nDOCreditNoteCurrency)
```

### ❌ `l10n_do_document_pools`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_document_pools.tests.test_document_pools.TestDocumentPools)
```

### ❌ `l10n_do_ecf_invoicing`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_ecf_invoicing.tests.test_account_move.AccountMoveTest)
```

### ❌ `l10n_do_ncf_validation`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_ncf_validation.tests.test_account_move.AccountMoveTest)
```

### ❌ `l10n_do_purchase`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_purchase.tests.test_purchase_order.TestL10nDOPurchaseOrder)
```

### ❌ `l10n_do_sale`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 3 &nbsp;|&nbsp; **Errores:** 0 &nbsp;|&nbsp; **Tests:** 8 &nbsp;|&nbsp; **Tiempo:** 1.16s

**Detalle de fallos:**

```
FAIL: TestL10nDOSaleOrder.test_change_partner_triggers_constraint
FAIL: TestL10nDOSaleOrder.test_no_vat_high_amount_raises
FAIL: TestL10nDOSaleOrder.test_no_vat_taxpayer_low_amount_raises
```

### ❌ `l10n_do_withholding_certification`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 2 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_withholding_certification.tests.test_account_payment.AccountPaymentWithholdingTest)
ERROR: setUpClass (odoo.addons.l10n_do_withholding_certification.tests.test_account_payment.AccountPaymentWithholdingTest)
```

### ❌ `purchase_foreign_cost_update`

> **Autor:** Fernando Figuereo &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.11s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.purchase_foreign_cost_update.tests.test_purchase_foreign_cost_update.TestPurchaseForeignCostUpdate)
```

### ❌ `purchase_order_rate`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 1.39s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.purchase_order_rate.tests.test_purchase_rate.TestPurchaseOrderRate)
```

### ❌ `sale_order_rate`

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 1.39s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.sale_order_rate.tests.test_sale_rate.TestSaleOrderRate)
```

### ❌ `stock_landed_costs_features`

> **Autor:** luisfernandez &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 3 &nbsp;|&nbsp; **Tiempo:** 1.74s

**Detalle de fallos:**

```
ERROR: TestStockLandedCostsSpecificProducts.test_landed_costs_specific_products
```

---

## 🔴 Fallos de Instalación &nbsp; `0 módulos`

> ✅ Todos los módulos se instalaron correctamente.

## 🚫 Versión Incompatible &nbsp; `1 módulos`

| Módulo | Módulo | Módulo | Módulo |
|-----|-----|-----|-----|
| `sale_pos_backend_multi_journal_payment` |  |  |  |

## 🔒 Pendientes de Migración a v19 &nbsp; `43 módulos`

> Módulos con `installable = False`. Excluidos del proceso de instalación y tests.

| Módulo | Módulo | Módulo |
|------|------|------|
| `account_payment_cash_custom_workflow` | `bi_warranty_registration` | `export_view_pdf` |
| `hms_sale_pos_backend` | `l10n_do_ecf_reception` | `l10n_do_ecf_reception_workflow` |
| `l10n_do_hr_course` | `l10n_do_hr_fleet` | `l10n_do_hr_maintenance` |
| `l10n_do_hr_recurrent_news` | `l10n_do_sale_pos_backend` | `l10n_do_sale_pos_backend_reconcile_payment` |
| `l10n_do_sign_to_xml` | `looker_connector` | `odoo_document_printer` |
| `odoo_document_printer_customization_base` | `printnode_base` | `product_segment` |
| `product_warehouse_quantity` | `professional_templates` | `qztray` |
| `qztray_base` | `qztray_location_labels` | `qztray_partner_labels` |
| `qztray_product_inventory` | `qztray_product_labels` | `qztray_product_purchase` |
| `repair_helpdesk_custom` | `repair_location_settings` | `repair_no_negative_allow` |
| `repair_warranty_extra_info` | `sale_pos_backend` | `sale_pos_backend_card_bin_promotion` |
| `sale_pos_backend_card_bin_promotion_payments` | `sale_pos_backend_discount_display_amount` | `sale_pos_backend_journal_control` |
| `sale_pos_backend_part_number` | `sale_pos_backend_warranty_reports` | `sale_pos_session_link` |
| `sh_all_in_one_margin` | `sh_low_stock_notification` | `sh_product_multi_barcode` |
| `sh_restrict_pricelist` |  |  |

## ⚠️  Warnings en Tests &nbsp; `4 módulos`

<details><summary><code>auto_backup_sh</code> — 1 warnings</summary>

```text
File not found: Backup file _daily.sql.gz not found in path /home/odoo/backup.daily
```
</details>

<details><summary><code>l10n_do_rnc_validation</code> — 4 warnings</summary>

```text
Invalid format for: 999999901
Invalid format for: 99999990101
Invalid format for: 999999901
Invalid format for: 999999901
```
</details>

<details><summary><code>payment_azul_webpages</code> — 2 warnings</summary>

```text
Azul: DataVaultToken has unexpected format, skipping tokenization for transaction Test Transaction
Azul: DataVaultToken has unexpected format, skipping tokenization for transaction Test Transaction
```
</details>

<details><summary><code>payment_azul_webservices</code> — 1 warnings</summary>

```text
Cannot create token: No partner associated with transaction TEST-0
```
</details>

## ⏩ Sin Directorio de Tests &nbsp; `150 módulos`

| Módulo | Módulo | Módulo |
|------|------|------|
| `acap_bank_statement_import` | `account_accountant_cheque` | `account_bank_charge_import_base` |
| `account_bank_charge_import_bhd` | `account_bank_charge_import_bpd` | `account_bank_statement_import_csv_patch` |
| `account_date_filters` | `account_default_journals` | `account_financial_risk_features` |
| `account_followup_extra_features` | `account_invoice_read_notification` | `account_lock_fiscal_date` |
| `account_move_route` | `account_multi_journal_payment` | `account_multi_journal_payment_authorization_code` |
| `account_partner_fields` | `account_payment_advance_payment` | `account_payment_authorization_code` |
| `account_payment_card_bin` | `account_payment_compensation` | `account_payment_compensation_news` |
| `account_payment_internal_transfer` | `account_payment_promotion_discount` | `account_payment_reconcile_features` |
| `account_transfer_features` | `advanced_web_domain_widget` | `apap_bank_statement_import` |
| `auto_attribute_value` | `auto_backup_sh` | `bdr_bank_statement_import` |
| `bhd_bank_statement_import` | `bhd_panama_bank_statement_import` | `bi_all_in_one_schedule_activity` |
| `blh_bank_statement_import` | `bnc_bank_statement_import` | `bpd_bank_statement_import` |
| `bpm_bank_statement_import` | `bsc_bank_statement_import` | `crm_helpdesk_custom` |
| `delivery_buenvio` | `dgii_ir3_report` | `dgii_reports` |
| `fleet_account_asset` | `fleet_industry_fsm` | `fleet_product_management` |
| `fleet_product_rules` | `helpdesk_sale_custom` | `helpdesk_ticket_signature` |
| `hms_account` | `hms_partner` | `hms_sales` |
| `hr_payroll_import_inputs` | `jmmb_bank_statement_import` | `ks_dashboard_ninja` |
| `ks_dn_advance` | `l10n_do_account_batch_payment_base` | `l10n_do_account_batch_payment_bdr` |
| `l10n_do_account_batch_payment_bhd` | `l10n_do_account_batch_payment_bpd` | `l10n_do_account_batch_payment_ee` |
| `l10n_do_account_withholding_tax` | `l10n_do_accounting` | `l10n_do_bank_charges_import` |
| `l10n_do_banks` | `l10n_do_credit_note` | `l10n_do_currency_update` |
| `l10n_do_document_pools` | `l10n_do_ecf_invoicing` | `l10n_do_ecommerce` |
| `l10n_do_gamification_hr_news` | `l10n_do_hr` | `l10n_do_hr_expense` |
| `l10n_do_hr_news` | `l10n_do_hr_news_accounts_receivable` | `l10n_do_hr_payroll` |
| `l10n_do_hr_payroll_import_inputs` | `l10n_do_hr_payroll_news` | `l10n_do_hr_payroll_news_attendance` |
| `l10n_do_hr_recruitment` | `l10n_do_hr_report_base` | `l10n_do_ncf_validation` |
| `l10n_do_payroll_bhd_file` | `l10n_do_payroll_bpd_file` | `l10n_do_payroll_brrd_file` |
| `l10n_do_payroll_file_base` | `l10n_do_pos` | `l10n_do_purchase` |
| `l10n_do_rnc_validation` | `l10n_do_sale` | `l10n_do_withholding_certification` |
| `mcp_server` | `odoo_cheque_features` | `odoo_cheque_management` |
| `payment_azul_webpages` | `payment_azul_webservices` | `payment_bhd` |
| `payment_salesperson` | `pos_azul` | `pos_cardnet` |
| `pos_hms` | `pos_loyalty_card_bin` | `pos_multi_currency` |
| `product_category_inter_company` | `product_category_multi_company` | `product_fields_tracking` |
| `product_foreign_cost_price` | `product_label_for_zebra_printer` | `product_part_number` |
| `product_price_checker` | `product_price_history` | `product_pricelist_user_restriction` |
| `product_product_price_widget` | `product_stock_qty_date_widgets` | `purchase_financial_risk` |
| `purchase_financial_risk_features` | `purchase_foreign_cost_update` | `purchase_order_rate` |
| `purchase_partner_fields` | `purchase_picking_default` | `purchase_request_currency` |
| `purchase_request_features` | `repair_services` | `report_zpl_direct_print` |
| `res_partner_phone_search` | `sale_crm_features` | `sale_financial_risk_features` |
| `sale_mr_inherit_modify` | `sale_order_glasses_description` | `sale_order_rate` |
| `sale_order_time_total` | `sale_order_with_other_locations` | `sale_partner_fields` |
| `sale_product_generic_readonly` | `sale_stock_product_price_widget` | `sale_stock_qty_date_widgets` |
| `sale_stock_restriction` | `sale_stock_serial` | `sale_subscription_draft_invoice` |
| `sales_bavel` | `scotiabank_statement_import` | `simplify_access_management` |
| `stock_inventory_forecasted_report` | `stock_landed_costs_features` | `stock_landed_costs_file` |
| `stock_picking_invoice_link_extra` | `stock_warehouse_orderpoint_uom` | `tss_report` |
| `user_default_iot_printer` | `website_quotation` | `website_stock_availability` |

---

## 📦 Inventario Completo &nbsp; `195 módulos`

<details>
<summary>Expandir inventario completo</summary>

| Estado | Módulo | Autor |
|:------:|--------|-------|
| ✅ `PASS` | `acap_bank_statement_import` | lfernandez |
| ⚠️  `NOT_LOADED` | `account_accountant_cheque` | lfernandez |
| ✅ `PASS` | `account_bank_charge_import_base` | luisfernandez |
| ✅ `PASS` | `account_bank_charge_import_bhd` | luisfernandez |
| ✅ `PASS` | `account_bank_charge_import_bpd` | luisfernandez |
| ✅ `PASS` | `account_bank_statement_import_csv_patch` | lfernandez |
| ⚠️  `NOT_LOADED` | `account_date_filters` | Erick Cuesto |
| ❌ `FAIL` | `account_default_journals` | Erick Cuesto |
| ✅ `PASS` | `account_financial_risk_features` | lfernandez |
| ✅ `PASS` | `account_followup_extra_features` | luisfernandez |
| ⚠️  `NOT_LOADED` | `account_invoice_read_notification` | Erick Cuesto |
| ✅ `PASS` | `account_lock_fiscal_date` | lfernandez |
| ✅ `PASS` | `account_move_route` | Erick Cuesto |
| ❌ `FAIL` | `account_multi_journal_payment` | Erick Cuesto |
| ✅ `PASS` | `account_multi_journal_payment_authorization_code` | lfernandez |
| ❌ `FAIL` | `account_partner_fields` | DanielAPereyraB |
| ✅ `PASS` | `account_payment_advance_payment` | lfernandez |
| ✅ `PASS` | `account_payment_authorization_code` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_payment_card_bin` | Luis Fernandez |
| 🔒 `NO_INST` | `account_payment_cash_custom_workflow` | Erick Cuesto |
| ❌ `FAIL` | `account_payment_compensation` | Fernando Figuereo |
| ⚠️  `NOT_LOADED` | `account_payment_compensation_news` | luisfernandez |
| ✅ `PASS` | `account_payment_internal_transfer` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `account_payment_promotion_discount` | Luis Fernandez |
| ✅ `PASS` | `account_payment_reconcile_features` | Erick Cuesto |
| ✅ `PASS` | `account_transfer_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `advanced_web_domain_widget` | - |
| ✅ `PASS` | `apap_bank_statement_import` | lfernandez |
| ⚠️  `NOT_LOADED` | `auto_attribute_value` | Luis Fernandez |
| ✅⚠️ `PASS+W` | `auto_backup_sh` | lfernandez |
| ✅ `PASS` | `bdr_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bhd_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bhd_panama_bank_statement_import` | lfernandez |
| ⚠️  `NOT_LOADED` | `bi_all_in_one_schedule_activity` | - |
| 🔒 `NO_INST` | `bi_warranty_registration` | - |
| ✅ `PASS` | `blh_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bnc_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bpd_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bpm_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bsc_bank_statement_import` | lfernandez |
| ✅ `PASS` | `crm_helpdesk_custom` | lfernandez |
| ⚠️  `NOT_LOADED` | `delivery_buenvio` | lfernandez |
| ⚠️  `NOT_LOADED` | `dgii_ir3_report` | luisfernandez |
| ⚠️  `NOT_LOADED` | `dgii_reports` | Erick Cuesto |
| 🔒 `NO_INST` | `export_view_pdf` | - |
| ⚠️  `NOT_LOADED` | `fleet_account_asset` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_industry_fsm` | Luis Fernandez |
| ✅ `PASS` | `fleet_product_management` | Luis Fernandez |
| ✅ `PASS` | `fleet_product_rules` | lfernandez |
| ✅ `PASS` | `helpdesk_sale_custom` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `helpdesk_ticket_signature` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `hms_account` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `hms_partner` | Erick Cuesto |
| 🔒 `NO_INST` | `hms_sale_pos_backend` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `hms_sales` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `hr_payroll_import_inputs` | Daniel Alexander Pereyra Beltran |
| ✅ `PASS` | `jmmb_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `ks_dashboard_ninja` | - |
| ⚠️  `NOT_LOADED` | `ks_dn_advance` | - |
| ✅ `PASS` | `l10n_do_account_batch_payment_base` | luisfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_bdr` | luisfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_bhd` | luisfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_bpd` | luisfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_ee` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_account_withholding_tax` | Daniel Alexander Pereyra Beltran |
| ❌ `FAIL` | `l10n_do_accounting` | DanielAPereyraB |
| ✅ `PASS` | `l10n_do_bank_charges_import` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_banks` | luisfernandez |
| ❌ `FAIL` | `l10n_do_credit_note` | DanielAPereyraB |
| ✅ `PASS` | `l10n_do_currency_update` | Erick Cuesto |
| ❌ `FAIL` | `l10n_do_document_pools` | DanielAPereyraB |
| ❌ `FAIL` | `l10n_do_ecf_invoicing` | Erick Cuesto |
| 🔒 `NO_INST` | `l10n_do_ecf_reception` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_ecf_reception_workflow` | DanielAPereyraB |
| ✅ `PASS` | `l10n_do_ecommerce` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `l10n_do_gamification_hr_news` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_course` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_expense` | Erick Cuesto |
| 🔒 `NO_INST` | `l10n_do_hr_fleet` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_hr_maintenance` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_news` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_news_accounts_receivable` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_import_inputs` | Daniel Alexander Pereyra Beltran |
| ✅ `PASS` | `l10n_do_hr_payroll_liquidation` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news_attendance` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_recruitment` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_recurrent_news` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_report_base` | luisfernandez |
| ❌ `FAIL` | `l10n_do_ncf_validation` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_bhd_file` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_bpd_file` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_brrd_file` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_file_base` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_pos` | Luis Fernandez |
| ❌ `FAIL` | `l10n_do_purchase` | Erick Cuesto |
| ✅⚠️ `PASS+W` | `l10n_do_rnc_validation` | luisfernandez |
| ❌ `FAIL` | `l10n_do_sale` | Erick Cuesto |
| 🔒 `NO_INST` | `l10n_do_sale_pos_backend` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_sale_pos_backend_reconcile_payment` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_sign_to_xml` | DanielAPereyraB |
| ❌ `FAIL` | `l10n_do_withholding_certification` | Erick Cuesto |
| 🔒 `NO_INST` | `looker_connector` | - |
| ⚠️  `NOT_LOADED` | `mcp_server` | - |
| ✅ `PASS` | `odoo_cheque_features` | - |
| ⚠️  `NOT_LOADED` | `odoo_cheque_management` | andrp92 |
| 🔒 `NO_INST` | `odoo_document_printer` | - |
| 🔒 `NO_INST` | `odoo_document_printer_customization_base` | - |
| ✅⚠️ `PASS+W` | `payment_azul_webpages` | Luis Fernandez |
| ✅⚠️ `PASS+W` | `payment_azul_webservices` | luisfernandez |
| ⚠️  `NOT_LOADED` | `payment_bhd` | Erick Cuesto |
| ✅ `PASS` | `payment_salesperson` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `pos_azul` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `pos_cardnet` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `pos_hms` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `pos_loyalty_card_bin` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `pos_multi_currency` | Erick Cuesto |
| 🔒 `NO_INST` | `printnode_base` | - |
| ⚠️  `NOT_LOADED` | `product_category_inter_company` | lfernandez |
| ⚠️  `NOT_LOADED` | `product_category_multi_company` | lfernandez |
| ⚠️  `NOT_LOADED` | `product_fields_tracking` | lfernandez |
| ✅ `PASS` | `product_foreign_cost_price` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `product_label_for_zebra_printer` | andrp92 |
| ⚠️  `NOT_LOADED` | `product_part_number` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `product_price_checker` | - |
| ✅ `PASS` | `product_price_history` | lfernandez |
| ✅ `PASS` | `product_pricelist_user_restriction` | lfernandez |
| ⚠️  `NOT_LOADED` | `product_product_price_widget` | DanielAPereyraB |
| 🔒 `NO_INST` | `product_segment` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `product_stock_qty_date_widgets` | DanielAPereyraB |
| 🔒 `NO_INST` | `product_warehouse_quantity` | - |
| 🔒 `NO_INST` | `professional_templates` | - |
| ✅ `PASS` | `purchase_financial_risk` | Luis Fernandez |
| ✅ `PASS` | `purchase_financial_risk_features` | lfernandez |
| ❌ `FAIL` | `purchase_foreign_cost_update` | Fernando Figuereo |
| ❌ `FAIL` | `purchase_order_rate` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `purchase_partner_fields` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `purchase_picking_default` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `purchase_request_currency` | Luis Fernandez |
| ✅ `PASS` | `purchase_request_features` | lfernandez |
| 🔒 `NO_INST` | `qztray` | - |
| 🔒 `NO_INST` | `qztray_base` | - |
| 🔒 `NO_INST` | `qztray_location_labels` | - |
| 🔒 `NO_INST` | `qztray_partner_labels` | - |
| 🔒 `NO_INST` | `qztray_product_inventory` | - |
| 🔒 `NO_INST` | `qztray_product_labels` | - |
| 🔒 `NO_INST` | `qztray_product_purchase` | - |
| 🔒 `NO_INST` | `repair_helpdesk_custom` | andrp92 |
| 🔒 `NO_INST` | `repair_location_settings` | andrp92 |
| 🔒 `NO_INST` | `repair_no_negative_allow` | DanielAPereyraB |
| ✅ `PASS` | `repair_services` | lfernandez |
| 🔒 `NO_INST` | `repair_warranty_extra_info` | andrp92 |
| ⚠️  `NOT_LOADED` | `report_zpl_direct_print` | - |
| ⚠️  `NOT_LOADED` | `res_partner_phone_search` | Luis Fernandez |
| ✅ `PASS` | `sale_crm_features` | lfernandez |
| ✅ `PASS` | `sale_financial_risk_features` | lfernandez |
| ⚠️  `NOT_LOADED` | `sale_mr_inherit_modify` | luisfernandez |
| ⚠️  `NOT_LOADED` | `sale_order_glasses_description` | Erick Cuesto |
| ❌ `FAIL` | `sale_order_rate` | DanielAPereyraB |
| ✅ `PASS` | `sale_order_time_total` | lfernandez |
| ⚠️  `NOT_LOADED` | `sale_order_with_other_locations` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_partner_fields` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_pos_backend` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_pos_backend_card_bin_promotion` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_pos_backend_card_bin_promotion_payments` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_pos_backend_discount_display_amount` | andrp92 |
| 🔒 `NO_INST` | `sale_pos_backend_journal_control` | DanielAPereyraB |
| 🚫 `INCOMPAT` | `sale_pos_backend_multi_journal_payment` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_pos_backend_part_number` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_pos_backend_warranty_reports` | - |
| 🔒 `NO_INST` | `sale_pos_session_link` | DanielAPereyraB |
| ✅ `PASS` | `sale_product_generic_readonly` | lfernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_product_price_widget` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `sale_stock_qty_date_widgets` | DanielAPereyraB |
| ✅ `PASS` | `sale_stock_restriction` | Erick Cuesto |
| ✅ `PASS` | `sale_stock_serial` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `sale_subscription_draft_invoice` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `sales_bavel` | Daniel Alexander Pereyra Beltran |
| ✅ `PASS` | `scotiabank_statement_import` | lfernandez |
| 🔒 `NO_INST` | `sh_all_in_one_margin` | - |
| 🔒 `NO_INST` | `sh_low_stock_notification` | - |
| 🔒 `NO_INST` | `sh_product_multi_barcode` | - |
| 🔒 `NO_INST` | `sh_restrict_pricelist` | - |
| ⚠️  `NOT_LOADED` | `simplify_access_management` | - |
| ✅ `PASS` | `stock_inventory_forecasted_report` | lfernandez |
| ❌ `FAIL` | `stock_landed_costs_features` | luisfernandez |
| ⚠️  `NOT_LOADED` | `stock_landed_costs_file` | Erick Cuesto |
| ✅ `PASS` | `stock_picking_invoice_link_extra` | Luis Fernandez |
| ✅ `PASS` | `stock_warehouse_orderpoint_uom` | lfernandez |
| ⚠️  `NOT_LOADED` | `tss_report` | luisfernandez |
| ⚠️  `NOT_LOADED` | `user_default_iot_printer` | lfernandez |
| ⚠️  `NOT_LOADED` | `website_quotation` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `website_stock_availability` | Erick Cuesto |

</details>

---

*Generado automáticamente por `run_tests.sh` · Odoo Pro v19 · 30/07/2026 00:43:27*