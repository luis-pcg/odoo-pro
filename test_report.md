# 🧪 Odoo Pro v19 — Test Report

> **Generado:** 13/05/2026 13:45:15 &nbsp;|&nbsp; **Instalación:** 1m 1s &nbsp;|&nbsp; **Tests:** 8m 59s

---

## 📊 Resumen Ejecutivo

| KPI | Valor | Detalle |
|-----|:-----:|---------|
| **Módulos descubiertos** | 192 | 116 instalables · 76 pendientes migración |
| **Módulos instalados** | 51 / 116 | 1 fallaron · 4 incompatibles |
| **Módulos con tests** | 76 / 79 | 60 pasaron · 16 fallaron |
| **Tests individuales** | 827 | 6 assert · 35 excepciones |
| **Tasa de éxito (módulos)** | 79% | `████████████████░░░░` 79% |
| **Tasa de éxito (tests)** | 95% | `███████████████████░` 95% |

### Estado por categoría

| Estado | Módulos | Descripción |
|--------|:-------:|-------------|
| ✅ Pasaron | **60** | módulos con todos los tests en verde |
| ❌ Fallaron | **16** | módulos con fallos o errores |
| ⚠️  Con warnings | **4** | módulos con advertencias |
| ⏩ Sin tests | **33** | módulos sin directorio tests/ |
| 🔒 No instalables | **76** | installable=False — pendientes migración |
| 🚫 Incompatibles | **4** | versión incompatible con v19 |
| 🔴 Error install | **1** | fallaron durante la instalación |

---

## ✅ Tests Pasaron &nbsp; `60 módulos`

| Módulo | Tests | Tiempo | Autor | Estado |
|--------|:-----:|:------:|-------|:------:|
| `acap_bank_statement_import` | 7 | 3.88s | lfernandez | ✅ |
| `account_bank_charge_import_base` | 8 | 0.09s | Luis Fernandez | ✅ |
| `account_bank_charge_import_bhd` | 6 | 6.92s | lfernandez | ✅ |
| `account_bank_charge_import_bpd` | 6 | 5.47s | lfernandez | ✅ |
| `account_bank_statement_import_csv_patch` | 4 | 1.18s | Luis Fernandez | ✅ |
| `account_financial_risk_features` | 18 | 1.58s | lfernandez | ✅ |
| `account_followup_extra_features` | 12 | 2.02s | lfernandez | ✅ |
| `account_lock_fiscal_date` | 14 | 2.77s | lfernandez | ✅ |
| `account_move_route` | 5 | 2.61s | Erick Cuesto | ✅ |
| `account_multi_journal_payment_authorization_code` | 12 | 1.3s | lfernandez | ✅ |
| `account_payment_advance_payment` | 7 | 0.09s | lfernandez | ✅ |
| `account_payment_authorization_code` | 6 | 1.26s | lfernandez | ✅ |
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
| `jmmb_bank_statement_import` | 9 | 1.55s | lfernandez | ✅ |
| `l10n_do_account_batch_payment_base` | 5 | 0.12s | lfernandez | ✅ |
| `l10n_do_account_batch_payment_bdr` | 6 | 0.14s | lfernandez | ✅ |
| `l10n_do_account_batch_payment_bhd` | 6 | 0.14s | lfernandez | ✅ |
| `l10n_do_account_batch_payment_bpd` | 9 | 0.21s | lfernandez | ✅ |
| `l10n_do_account_batch_payment_ee` | 6 | 0.12s | lfernandez | ✅ |
| `l10n_do_bank_charges_import` | 11 | 1.5s | lfernandez | ✅ |
| `l10n_do_currency_update` | 4 | 0.54s | DanielAPereyraB | ✅ |
| `l10n_do_ecommerce` | 3 | 0.02s | Erick Cuesto | ✅ |
| `l10n_do_rnc_validation` ⚠️ | 12 | 0.27s | Erick Cuesto | ✅⚠️ |
| `odoo_cheque_features` | 3 | 0.07s | - | ✅ |
| `payment_azul_webpages` ⚠️ | 72 | 2.07s | DanielAPereyraB | ✅⚠️ |
| `payment_azul_webservices` ⚠️ | 56 | 0.39s | DanielAPereyraB | ✅⚠️ |
| `payment_salesperson` | 13 | 1.53s | lfernandez | ✅ |
| `product_foreign_cost_price` | 9 | 0.08s | Erick Cuesto | ✅ |
| `product_price_history` | 14 | 0.42s | lfernandez | ✅ |
| `product_pricelist_user_restriction` | 13 | 0.22s | lfernandez | ✅ |
| `purchase_financial_risk` | 20 | 0.99s | lfernandez | ✅ |
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
| `stock_picking_invoice_link_extra` | 7 | 2.46s | lfernandez | ✅ |
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

> **Autor:** Daniel Alexander Pereyra Beltran &nbsp;|&nbsp; **Fallos:** 1 &nbsp;|&nbsp; **Errores:** 15 &nbsp;|&nbsp; **Tests:** 28 &nbsp;|&nbsp; **Tiempo:** 5.72s

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

> **Autor:** Daniel Alexander Pereyra Beltran &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 2 &nbsp;|&nbsp; **Tests:** 4 &nbsp;|&nbsp; **Tiempo:** 0.0s

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

> **Autor:** Daniel Alexander Pereyra Beltran &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

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

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 2 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.0s

**Detalle de fallos:**

```
ERROR: setUpClass (odoo.addons.l10n_do_withholding_certification.tests.test_account_payment.AccountPaymentWithholdingTest)
ERROR: setUpClass (odoo.addons.l10n_do_withholding_certification.tests.test_account_payment.AccountPaymentWithholdingTest)
```

### ❌ `purchase_foreign_cost_update`

> **Autor:** Erick Cuesto &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 2 &nbsp;|&nbsp; **Tiempo:** 0.11s

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

> **Autor:** DanielAPereyraB &nbsp;|&nbsp; **Fallos:** 0 &nbsp;|&nbsp; **Errores:** 1 &nbsp;|&nbsp; **Tests:** 3 &nbsp;|&nbsp; **Tiempo:** 1.74s

**Detalle de fallos:**

```
ERROR: TestStockLandedCostsSpecificProducts.test_landed_costs_specific_products
```

---

## 🔴 Fallos de Instalación &nbsp; `1 módulos`

| Módulo | Causa del fallo |
|--------|-----------------|
| `hr_payroll_import_inputs` | Failed to load registry |

## 🚫 Versión Incompatible &nbsp; `4 módulos`

| Módulo | Módulo | Módulo | Módulo |
|-----|-----|-----|-----|
| `payment_bhd` | `pos_azul` | `pos_hr_minimal_rights` | `sale_pos_backend_multi_journal_payment` |

## 🔒 Pendientes de Migración a v19 &nbsp; `76 módulos`

> Módulos con `installable = False`. Excluidos del proceso de instalación y tests.

| Módulo | Módulo | Módulo |
|------|------|------|
| `account_payment_card_bin` | `account_payment_cash_custom_workflow` | `account_payment_promotion_discount` |
| `auto_attribute_value` | `bi_warranty_registration` | `delivery_buenvio` |
| `export_view_pdf` | `fleet_account_asset` | `fleet_industry_fsm` |
| `fleet_product_rules_renting` | `hms_account` | `hms_partner` |
| `hms_sale_pos_backend` | `hms_sales` | `l10n_do_ecf_reception` |
| `l10n_do_ecf_reception_workflow` | `l10n_do_hr_course` | `l10n_do_hr_fleet` |
| `l10n_do_hr_maintenance` | `l10n_do_hr_news_accounts_receivable` | `l10n_do_hr_news_attendance` |
| `l10n_do_hr_payroll_import_inputs` | `l10n_do_hr_payroll_news_attendance` | `l10n_do_hr_recurrent_news` |
| `l10n_do_sale_pos_backend` | `l10n_do_sale_pos_backend_reconcile_payment` | `l10n_do_sign_to_xml` |
| `looker_connector` | `odoo_document_printer` | `odoo_document_printer_customization_base` |
| `printnode_base` | `product_category_inter_company` | `product_category_multi_company` |
| `product_label_for_zebra_printer` | `product_part_number` | `product_price_checker` |
| `product_segment` | `product_warehouse_quantity` | `professional_templates` |
| `purchase_picking_default` | `purchase_request_currency` | `qztray` |
| `qztray_base` | `qztray_location_labels` | `qztray_partner_labels` |
| `qztray_product_inventory` | `qztray_product_labels` | `qztray_product_purchase` |
| `repair_helpdesk_custom` | `repair_location_settings` | `repair_no_negative_allow` |
| `repair_warranty_extra_info` | `res_partner_phone_search` | `sale_mr_inherit_modify` |
| `sale_order_glasses_description` | `sale_order_with_other_locations` | `sale_pos_backend` |
| `sale_pos_backend_card_bin_promotion` | `sale_pos_backend_card_bin_promotion_payments` | `sale_pos_backend_discount_display_amount` |
| `sale_pos_backend_journal_control` | `sale_pos_backend_part_number` | `sale_pos_backend_warranty_reports` |
| `sale_pos_session_link` | `sales_bavel` | `sh_all_in_one_margin` |
| `sh_low_stock_notification` | `sh_product_multi_barcode` | `sh_restrict_pricelist` |
| `website_store_pickup` | `whatsapp_connector` | `whatsapp_connector_chatter` |
| `whatsapp_connector_crm` | `whatsapp_connector_pack` | `whatsapp_connector_sale` |
| `wk_odoo_directly_print_reports` |  |  |

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

## ⏩ Sin Directorio de Tests &nbsp; `33 módulos`

| Módulo | Módulo | Módulo |
|------|------|------|
| `account_accountant_cheque` | `account_date_filters` | `account_invoice_read_notification` |
| `account_payment_compensation_news` | `advanced_web_domain_widget` | `bi_all_in_one_schedule_activity` |
| `dgii_reports` | `helpdesk_ticket_signature` | `hr_payroll_import_inputs` |
| `ks_dashboard_ninja` | `ks_dn_advance` | `l10n_do_account_withholding_tax` |
| `l10n_do_banks` | `l10n_do_hr_news` | `l10n_do_hr_payroll_news` |
| `l10n_do_hr_recruitment` | `l10n_do_payroll_bhd_file` | `l10n_do_payroll_bpd_file` |
| `l10n_do_payroll_brrd_file` | `l10n_do_payroll_file_base` | `l10n_do_pos` |
| `odoo_cheque_management` | `product_fields_tracking` | `product_product_price_widget` |
| `product_stock_qty_date_widgets` | `purchase_partner_fields` | `sale_partner_fields` |
| `sale_stock_product_price_widget` | `sale_stock_qty_date_widgets` | `simplify_access_management` |
| `stock_landed_costs_file` | `website_quotation` | `website_stock_availability` |

---

## 📦 Inventario Completo &nbsp; `192 módulos`

<details>
<summary>Expandir inventario completo</summary>

| Estado | Módulo | Autor |
|:------:|--------|-------|
| ✅ `PASS` | `acap_bank_statement_import` | lfernandez |
| ⏩ `NO_TESTS` | `account_accountant_cheque` | lfernandez |
| ✅ `PASS` | `account_bank_charge_import_base` | Luis Fernandez |
| ✅ `PASS` | `account_bank_charge_import_bhd` | lfernandez |
| ✅ `PASS` | `account_bank_charge_import_bpd` | lfernandez |
| ✅ `PASS` | `account_bank_statement_import_csv_patch` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_date_filters` | Erick Cuesto |
| ❌ `FAIL` | `account_default_journals` | Erick Cuesto |
| ✅ `PASS` | `account_financial_risk_features` | lfernandez |
| ✅ `PASS` | `account_followup_extra_features` | lfernandez |
| ⏩ `NO_TESTS` | `account_invoice_read_notification` | Erick Cuesto |
| ✅ `PASS` | `account_lock_fiscal_date` | lfernandez |
| ✅ `PASS` | `account_move_route` | Erick Cuesto |
| ❌ `FAIL` | `account_multi_journal_payment` | Erick Cuesto |
| ✅ `PASS` | `account_multi_journal_payment_authorization_code` | lfernandez |
| ❌ `FAIL` | `account_partner_fields` | DanielAPereyraB |
| ✅ `PASS` | `account_payment_advance_payment` | lfernandez |
| ✅ `PASS` | `account_payment_authorization_code` | lfernandez |
| 🔒 `NO_INST` | `account_payment_card_bin` | DanielAPereyraB |
| 🔒 `NO_INST` | `account_payment_cash_custom_workflow` | DanielAPereyraB |
| ❌ `FAIL` | `account_payment_compensation` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `account_payment_compensation_news` | Daniel Alexander Pereyra Beltran |
| ✅ `PASS` | `account_payment_internal_transfer` | Erick Cuesto |
| 🔒 `NO_INST` | `account_payment_promotion_discount` | DanielAPereyraB |
| ✅ `PASS` | `account_payment_reconcile_features` | Erick Cuesto |
| ✅ `PASS` | `account_transfer_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `advanced_web_domain_widget` | - |
| ✅ `PASS` | `apap_bank_statement_import` | lfernandez |
| 🔒 `NO_INST` | `auto_attribute_value` | DanielAPereyraB |
| ✅⚠️ `PASS+W` | `auto_backup_sh` | lfernandez |
| ✅ `PASS` | `bdr_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bhd_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bhd_panama_bank_statement_import` | lfernandez |
| ⏩ `NO_TESTS` | `bi_all_in_one_schedule_activity` | - |
| 🔒 `NO_INST` | `bi_warranty_registration` | - |
| ✅ `PASS` | `blh_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bnc_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bpd_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bpm_bank_statement_import` | lfernandez |
| ✅ `PASS` | `bsc_bank_statement_import` | lfernandez |
| ✅ `PASS` | `crm_helpdesk_custom` | lfernandez |
| 🔒 `NO_INST` | `delivery_buenvio` | DanielAPereyraB |
| ⏩ `NO_TESTS` | `dgii_reports` | DanielAPereyraB |
| 🔒 `NO_INST` | `export_view_pdf` | - |
| 🔒 `NO_INST` | `fleet_account_asset` | DanielAPereyraB |
| 🔒 `NO_INST` | `fleet_industry_fsm` | DanielAPereyraB |
| ✅ `PASS` | `fleet_product_management` | Luis Fernandez |
| ✅ `PASS` | `fleet_product_rules` | lfernandez |
| 🔒 `NO_INST` | `fleet_product_rules_renting` | DanielAPereyraB |
| ✅ `PASS` | `helpdesk_sale_custom` | Erick Cuesto |
| ⏩ `NO_TESTS` | `helpdesk_ticket_signature` | Erick Cuesto |
| 🔒 `NO_INST` | `hms_account` | DanielAPereyraB |
| 🔒 `NO_INST` | `hms_partner` | DanielAPereyraB |
| 🔒 `NO_INST` | `hms_sale_pos_backend` | DanielAPereyraB |
| 🔒 `NO_INST` | `hms_sales` | DanielAPereyraB |
| 🔴 `INST_FAIL` | `hr_payroll_import_inputs` | DanielAPereyraB |
| ✅ `PASS` | `jmmb_bank_statement_import` | lfernandez |
| ⏩ `NO_TESTS` | `ks_dashboard_ninja` | - |
| ⏩ `NO_TESTS` | `ks_dn_advance` | - |
| ✅ `PASS` | `l10n_do_account_batch_payment_base` | lfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_bdr` | lfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_bhd` | lfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_bpd` | lfernandez |
| ✅ `PASS` | `l10n_do_account_batch_payment_ee` | lfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_account_withholding_tax` | Daniel Alexander Pereyra Beltran |
| ❌ `FAIL` | `l10n_do_accounting` | Daniel Alexander Pereyra Beltran |
| ✅ `PASS` | `l10n_do_bank_charges_import` | lfernandez |
| ⏩ `NO_TESTS` | `l10n_do_banks` | lfernandez |
| ❌ `FAIL` | `l10n_do_credit_note` | DanielAPereyraB |
| ✅ `PASS` | `l10n_do_currency_update` | DanielAPereyraB |
| ❌ `FAIL` | `l10n_do_document_pools` | DanielAPereyraB |
| ❌ `FAIL` | `l10n_do_ecf_invoicing` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_ecf_reception` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_ecf_reception_workflow` | DanielAPereyraB |
| ✅ `PASS` | `l10n_do_ecommerce` | Erick Cuesto |
| ⏩ `NO_TESTS` | `l10n_do_hr` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_course` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_hr_fleet` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_hr_maintenance` | DanielAPereyraB |
| ⏩ `NO_TESTS` | `l10n_do_hr_news` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_news_accounts_receivable` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_hr_news_attendance` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_payroll_import_inputs` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_payroll_news_attendance` | DanielAPereyraB |
| ⏩ `NO_TESTS` | `l10n_do_hr_recruitment` | Daniel Alexander Pereyra Beltran |
| 🔒 `NO_INST` | `l10n_do_hr_recurrent_news` | DanielAPereyraB |
| ❌ `FAIL` | `l10n_do_ncf_validation` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_bhd_file` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_bpd_file` | lfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_brrd_file` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_file_base` | lfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_pos` | andrp92 |
| ❌ `FAIL` | `l10n_do_purchase` | Erick Cuesto |
| ✅⚠️ `PASS+W` | `l10n_do_rnc_validation` | Erick Cuesto |
| ❌ `FAIL` | `l10n_do_sale` | Erick Cuesto |
| 🔒 `NO_INST` | `l10n_do_sale_pos_backend` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_sale_pos_backend_reconcile_payment` | DanielAPereyraB |
| 🔒 `NO_INST` | `l10n_do_sign_to_xml` | DanielAPereyraB |
| ❌ `FAIL` | `l10n_do_withholding_certification` | DanielAPereyraB |
| 🔒 `NO_INST` | `looker_connector` | - |
| ✅ `PASS` | `odoo_cheque_features` | - |
| ⏩ `NO_TESTS` | `odoo_cheque_management` | andrp92 |
| 🔒 `NO_INST` | `odoo_document_printer` | - |
| 🔒 `NO_INST` | `odoo_document_printer_customization_base` | - |
| ✅⚠️ `PASS+W` | `payment_azul_webpages` | DanielAPereyraB |
| ✅⚠️ `PASS+W` | `payment_azul_webservices` | DanielAPereyraB |
| 🚫 `INCOMPAT` | `payment_bhd` | andrp92 |
| ✅ `PASS` | `payment_salesperson` | lfernandez |
| 🚫 `INCOMPAT` | `pos_azul` | Daniel Alexander Pereyra Beltran |
| 🚫 `INCOMPAT` | `pos_hr_minimal_rights` | DanielAPereyraB |
| 🔒 `NO_INST` | `printnode_base` | - |
| 🔒 `NO_INST` | `product_category_inter_company` | DanielAPereyraB |
| 🔒 `NO_INST` | `product_category_multi_company` | DanielAPereyraB |
| ⏩ `NO_TESTS` | `product_fields_tracking` | lfernandez |
| ✅ `PASS` | `product_foreign_cost_price` | Erick Cuesto |
| 🔒 `NO_INST` | `product_label_for_zebra_printer` | andrp92 |
| 🔒 `NO_INST` | `product_part_number` | DanielAPereyraB |
| 🔒 `NO_INST` | `product_price_checker` | - |
| ✅ `PASS` | `product_price_history` | lfernandez |
| ✅ `PASS` | `product_pricelist_user_restriction` | lfernandez |
| ⚠️  `NOT_LOADED` | `product_product_price_widget` | DanielAPereyraB |
| 🔒 `NO_INST` | `product_segment` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `product_stock_qty_date_widgets` | DanielAPereyraB |
| 🔒 `NO_INST` | `product_warehouse_quantity` | - |
| 🔒 `NO_INST` | `professional_templates` | - |
| ✅ `PASS` | `purchase_financial_risk` | lfernandez |
| ✅ `PASS` | `purchase_financial_risk_features` | lfernandez |
| ❌ `FAIL` | `purchase_foreign_cost_update` | Erick Cuesto |
| ❌ `FAIL` | `purchase_order_rate` | DanielAPereyraB |
| ⏩ `NO_TESTS` | `purchase_partner_fields` | DanielAPereyraB |
| 🔒 `NO_INST` | `purchase_picking_default` | DanielAPereyraB |
| 🔒 `NO_INST` | `purchase_request_currency` | DanielAPereyraB |
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
| 🔒 `NO_INST` | `res_partner_phone_search` | DanielAPereyraB |
| ✅ `PASS` | `sale_crm_features` | lfernandez |
| ✅ `PASS` | `sale_financial_risk_features` | lfernandez |
| 🔒 `NO_INST` | `sale_mr_inherit_modify` | DanielAPereyraB |
| 🔒 `NO_INST` | `sale_order_glasses_description` | DanielAPereyraB |
| ❌ `FAIL` | `sale_order_rate` | DanielAPereyraB |
| ✅ `PASS` | `sale_order_time_total` | lfernandez |
| 🔒 `NO_INST` | `sale_order_with_other_locations` | DanielAPereyraB |
| ⏩ `NO_TESTS` | `sale_partner_fields` | DanielAPereyraB |
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
| 🔒 `NO_INST` | `sales_bavel` | DanielAPereyraB |
| ✅ `PASS` | `scotiabank_statement_import` | lfernandez |
| 🔒 `NO_INST` | `sh_all_in_one_margin` | - |
| 🔒 `NO_INST` | `sh_low_stock_notification` | - |
| 🔒 `NO_INST` | `sh_product_multi_barcode` | - |
| 🔒 `NO_INST` | `sh_restrict_pricelist` | - |
| ⏩ `NO_TESTS` | `simplify_access_management` | - |
| ✅ `PASS` | `stock_inventory_forecasted_report` | lfernandez |
| ❌ `FAIL` | `stock_landed_costs_features` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `stock_landed_costs_file` | DanielAPereyraB |
| ✅ `PASS` | `stock_picking_invoice_link_extra` | lfernandez |
| ✅ `PASS` | `stock_warehouse_orderpoint_uom` | lfernandez |
| ⚠️  `NOT_LOADED` | `tss_report` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `website_quotation` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `website_stock_availability` | Erick Cuesto |
| 🔒 `NO_INST` | `website_store_pickup` | DanielAPereyraB |
| 🔒 `NO_INST` | `whatsapp_connector` | - |
| 🔒 `NO_INST` | `whatsapp_connector_chatter` | - |
| 🔒 `NO_INST` | `whatsapp_connector_crm` | - |
| 🔒 `NO_INST` | `whatsapp_connector_pack` | - |
| 🔒 `NO_INST` | `whatsapp_connector_sale` | - |
| 🔒 `NO_INST` | `wk_odoo_directly_print_reports` | andrp92 |

</details>

---

*Generado automáticamente por `run_tests.sh` · Odoo Pro v19 · 13/05/2026 13:45:15*