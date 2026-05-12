# Odoo Pro v19 — Reporte de Tests

> Generado: 2026-05-12 12:42:44

## Resumen

| Métrica | Valor |
|---------|-------|
| Módulos pro descubiertos | 191 |
| Instalados correctamente | 110 |
| Versión incompatible (no instalables) | 4 |
| Fallaron instalación | 0 |
| Módulos pro con tests | 90 |
| Módulos con tests corridos | 75 |
| Tests individuales corridos | 723 |
| ↳ Fallaron (assert) | 5 |
| ↳ Errores (excepción) | 67 |
| ✅ Módulos — todos los tests pasaron | 45 |
| ❌ Módulos — tests fallaron | 30 |
| ⚠️  Módulos con warnings en tests | 3 |
| ⏩ Módulos pro sin directorio tests/ | 97 |
| Tiempo fase instalación | 77s (1m 17s) |
| Tiempo fase tests | 4300s (71m 40s) |

## ✅ Tests pasaron (45 módulos)

| Módulo | Tests | Tiempo |
|--------|:-----:|:------:|
| `acap_bank_statement_import` | 7 | 4.31s |
| `account_bank_charge_import_base` | 8 | 0.07s |
| `account_bank_statement_import_csv_patch` | 4 | 0.48s |
| `account_financial_risk_features` | 18 | 1.79s |
| `account_followup_extra_features` | 12 | 2.1s |
| `account_lock_fiscal_date` | 14 | 2.94s |
| `account_move_route` | 5 | 3.11s |
| `account_multi_journal_payment_authorization_code` | 12 | 0.56s |
| `account_partner_fields` | 3 | 0.1s |
| `account_payment_advance_payment` | 7 | 0.16s |
| `account_payment_authorization_code` | 6 | 0.13s |
| `account_payment_reconcile_features` | 12 | 4.47s |
| `apap_bank_statement_import` | 7 | 2.22s |
| `auto_backup_sh` ⚠️ | 28 | 0.05s |
| `bdr_bank_statement_import` | 7 | 2.4s |
| `bhd_bank_statement_import` | 7 | 7.99s |
| `bhd_panama_bank_statement_import` | 7 | 2.74s |
| `blh_bank_statement_import` | 7 | 2.15s |
| `bnc_bank_statement_import` | 6 | 2.21s |
| `bpd_bank_statement_import` | 8 | 3.19s |
| `bpm_bank_statement_import` | 8 | 2.21s |
| `bsc_bank_statement_import` | 9 | 4.35s |
| `fleet_product_management` | 24 | 0.88s |
| `fleet_product_rules` | 14 | 0.35s |
| `jmmb_bank_statement_import` | 9 | 0.86s |
| `l10n_do_account_batch_payment_base` | 5 | 0.12s |
| `l10n_do_account_batch_payment_ee` | 6 | 0.13s |
| `l10n_do_bank_charges_import` | 11 | 0.8s |
| `l10n_do_currency_update` | 4 | 0.67s |
| `l10n_do_ecommerce` | 3 | 0.02s |
| `l10n_do_rnc_validation` ⚠️ | 12 | 0.27s |
| `odoo_cheque_features` | 3 | 0.07s |
| `payment_salesperson` | 13 | 0.8s |
| `product_foreign_cost_price` | 9 | 0.08s |
| `product_price_history` | 14 | 0.43s |
| `product_pricelist_user_restriction` | 13 | 0.21s |
| `purchase_financial_risk_features` | 8 | 0.18s |
| `purchase_request_features` | 3 | 0.08s |
| `repair_services` | 23 | 0.69s |
| `sale_crm_features` | 7 | 0.16s |
| `sale_financial_risk_features` | 9 | 0.26s |
| `sale_order_time_total` | 4 | 0.74s |
| `sale_product_generic_readonly` | 8 | 0.23s |
| `scotiabank_statement_import` | 10 | 3.74s |
| `stock_inventory_forecasted_report` | 48 | 0.56s |

## ❌ Tests fallaron (30 módulos)

### `account_bank_charge_import_bhd`

- Failures: **0** | Errors: **2** | Tests: 6 | Tiempo: 0.19s

```
ERROR: TestAccountBankChargeImportBHD.test_001_bhd_bank_charge_import_dop
ERROR: TestAccountBankChargeImportBHD.test_002_bhd_bank_charge_import_usd
```

### `account_bank_charge_import_bpd`

- Failures: **0** | Errors: **2** | Tests: 6 | Tiempo: 0.52s

```
ERROR: TestAccountBankChargeImportBPD.test_001_bpd_bank_charge_import_txt
ERROR: TestAccountBankChargeImportBPD.test_002_bpd_bank_charge_import_csv
```

### `account_default_journals`

- Failures: **2** | Errors: **4** | Tests: 8 | Tiempo: 2.89s

```
FAIL: TestAccountDefaultJournals.test_payment_onchange_purchase_journal
FAIL: TestAccountDefaultJournals.test_payment_onchange_sales_journal
ERROR: TestAccountDefaultJournals.test_wizard_ignores_default_if_not_in_available
ERROR: TestAccountDefaultJournals.test_wizard_multiple_moves_falls_back_to_super
ERROR: TestAccountDefaultJournals.test_wizard_single_purchase_invoice_uses_partner_journal
ERROR: TestAccountDefaultJournals.test_wizard_single_sale_invoice_uses_partner_journal
```

### `account_multi_journal_payment`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.09s

```
ERROR: setUpClass (odoo.addons.account_multi_journal_payment.tests.test_account_multi_journal_payment.TestAccountMultiJournalPayment)
```

### `account_payment_compensation`

- Failures: **1** | Errors: **15** | Tests: 28 | Tiempo: 6.16s

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

### `account_transfer_features`

- Failures: **0** | Errors: **3** | Tests: 6 | Tiempo: 0.41s

```
ERROR: setUpClass (odoo.addons.account_transfer_features.tests.test_transfer_features.TestDailyFrequency)
ERROR: setUpClass (odoo.addons.account_transfer_features.tests.test_transfer_features.TestPartnerInMoveLines)
ERROR: setUpClass (odoo.addons.account_transfer_features.tests.test_transfer_features.TestPartnerField)
```

### `crm_helpdesk_custom`

- Failures: **0** | Errors: **2** | Tests: 24 | Tiempo: 1.08s

```
ERROR: TestCrmHelpdeskCustom.test_config_settings_relay_to_company
ERROR: TestCrmHelpdeskCustom.test_crm_group_user_can_create_ticket
```

### `helpdesk_sale_custom`

- Failures: **0** | Errors: **1** | Tests: 13 | Tiempo: 0.67s

```
ERROR: TestHelpdeskSaleCustom.test_config_settings_relay_to_company
```

### `l10n_do_account_batch_payment_bdr`

- Failures: **0** | Errors: **2** | Tests: 6 | Tiempo: 0.14s

```
ERROR: TestBDRBatchPayment.test_02_transaction_data_mapping_bdr
ERROR: TestBDRBatchPayment.test_03_wizard_file_generation_bdr
```

### `l10n_do_account_batch_payment_bhd`

- Failures: **0** | Errors: **2** | Tests: 6 | Tiempo: 0.15s

```
ERROR: TestBHDBatchPayment.test_02_transaction_data_mapping_bhd
ERROR: TestBHDBatchPayment.test_03_wizard_file_generation_bhd
```

### `l10n_do_account_batch_payment_bpd`

- Failures: **1** | Errors: **2** | Tests: 9 | Tiempo: 0.21s

```
FAIL: TestBPDBatchPaymentFail.test_04_effective_date_validation_fail
ERROR: TestBPDBatchPaymentFail.test_05_transaction_data_mapping_fail
ERROR: TestBPDBatchPaymentFail.test_06_full_wizard_flow_fail
```

### `l10n_do_accounting`

- Failures: **0** | Errors: **2** | Tests: 4 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_accounting.tests.test_account_journal.AccountJournalTest)
ERROR: setUpClass (odoo.addons.l10n_do_accounting.tests.test_account_move.AccountMoveTest)
```

### `l10n_do_credit_note`

- Failures: **0** | Errors: **2** | Tests: 4 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_credit_note.tests.test_l10n_do_credit_note.TestL10nDOCreditNoteItbis)
ERROR: setUpClass (odoo.addons.l10n_do_credit_note.tests.test_l10n_do_credit_note.TestL10nDOCreditNoteCurrency)
```

### `l10n_do_document_pools`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_document_pools.tests.test_document_pools.TestDocumentPools)
```

### `l10n_do_ecf_invoicing`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_ecf_invoicing.tests.test_account_move.AccountMoveTest)
```

### `l10n_do_ncf_validation`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_ncf_validation.tests.test_account_move.AccountMoveTest)
```

### `l10n_do_purchase`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_purchase.tests.test_purchase_order.TestL10nDOPurchaseOrder)
```

### `l10n_do_sale`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.26s

```
ERROR: setUpClass (odoo.addons.l10n_do_sale.tests.test_sale_order.TestL10nDOSaleOrder)
```

### `l10n_do_withholding_certification`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_withholding_certification.tests.test_account_payment.AccountPaymentWithholdingTest)
ERROR: setUpClass (odoo.addons.l10n_do_withholding_certification.tests.test_account_payment.AccountPaymentWithholdingTest)
```

### `payment_azul_webpages`

- Failures: **0** | Errors: **9** | Tests: 72 | Tiempo: 1.8s

```
ERROR: AzulTransactionRenderingTest.test_rendering_values_contain_required_fields
ERROR: AzulTransactionRenderingTest.test_rendering_values_each_demo_token_sets_correct_datavault_token
ERROR: AzulTransactionRenderingTest.test_rendering_values_locale_english
ERROR: AzulTransactionRenderingTest.test_rendering_values_locale_spanish
ERROR: AzulTransactionRenderingTest.test_rendering_values_merchant_id_matches_demo_provider
ERROR: AzulTransactionRenderingTest.test_rendering_values_normal_payment
ERROR: AzulTransactionRenderingTest.test_rendering_values_tokenize_sets_save_to_vault
ERROR: AzulTransactionRenderingTest.test_rendering_values_validation_sets_create_and_datavault_url
ERROR: AzulTransactionRenderingTest.test_rendering_values_with_demo_token
```

### `payment_azul_webservices`

- Failures: **0** | Errors: **2** | Tests: 18 | Tiempo: 0.08s

```
ERROR: setUpClass (odoo.addons.payment_azul_webservices.tests.test_payment_azul_webservices.TestAzulProvider)
ERROR: setUpClass (odoo.addons.payment_azul_webservices.tests.test_payment_azul_webservices.TestAzulTransaction)
```

### `purchase_financial_risk`

- Failures: **1** | Errors: **1** | Tests: 20 | Tiempo: 0.87s

```
FAIL: TestPurchaseFinancialRisk.test_partner_risk_purchase_order_compute
ERROR: TestPurchaseFinancialRisk.test_res_config_settings_include_risk_purchase_order_done
```

### `purchase_foreign_cost_update`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.11s

```
ERROR: setUpClass (odoo.addons.purchase_foreign_cost_update.tests.test_purchase_foreign_cost_update.TestPurchaseForeignCostUpdate)
```

### `purchase_order_rate`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 1.35s

```
ERROR: setUpClass (odoo.addons.purchase_order_rate.tests.test_purchase_rate.TestPurchaseOrderRate)
```

### `sale_order_rate`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 1.35s

```
ERROR: setUpClass (odoo.addons.sale_order_rate.tests.test_sale_rate.TestSaleOrderRate)
```

### `sale_stock_restriction`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.18s

```
ERROR: setUpClass (odoo.addons.sale_stock_restriction.tests.test_sale_stock_restriction.TestSaleStockRestriction)
```

### `sale_stock_serial`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.19s

```
ERROR: setUpClass (odoo.addons.sale_stock_serial.tests.test_sale_stock_serial.TestSaleStockSerial)
```

### `stock_landed_costs_features`

- Failures: **0** | Errors: **1** | Tests: 3 | Tiempo: 1.58s

```
ERROR: TestStockLandedCostsSpecificProducts.test_landed_costs_specific_products
```

### `stock_picking_invoice_link_extra`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 1.56s

```
ERROR: setUpClass (odoo.addons.stock_picking_invoice_link_extra.tests.test_picking_invoice_residual.TestPickingInvoiceResidual)
```

### `stock_warehouse_orderpoint_uom`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.24s

```
ERROR: setUpClass (odoo.addons.stock_warehouse_orderpoint_uom.tests.test_orderpoint_uom.TestOrderpointUom)
```

## 🔴 Fallaron instalación (0 módulos pro)

_Todos los módulos pro se instalaron correctamente_ ✅

## 🚫 Versión incompatible (4 módulos pro)

| Módulo |
|--------|
| `payment_bhd` |
| `pos_azul` |
| `pos_hr_minimal_rights` |
| `sale_pos_backend_multi_journal_payment` |

## ⚠️  Warnings en tests (3 módulos)

<details>
<summary><code>auto_backup_sh</code> (1 warnings)</summary>

```
File not found: Backup file _daily.sql.gz not found in path /home/odoo/backup.daily
```

</details>

<details>
<summary><code>l10n_do_rnc_validation</code> (4 warnings)</summary>

```
Invalid format for: 999999901
Invalid format for: 99999990101
Invalid format for: 999999901
Invalid format for: 999999901
```

</details>

<details>
<summary><code>payment_azul_webpages</code> (2 warnings)</summary>

```
Azul: DataVaultToken has unexpected format, skipping tokenization for transaction Test Transaction
Azul: DataVaultToken has unexpected format, skipping tokenization for transaction Test Transaction
```

</details>

## ⏩ Módulos pro sin directorio tests/ (97)

| | | |
|---|---|---|
| `account_accountant_cheque` | `account_date_filters` | `account_invoice_read_notification` |
| `account_payment_card_bin` | `account_payment_cash_custom_workflow` | `account_payment_compensation_news` |
| `account_payment_promotion_discount` | `advanced_web_domain_widget` | `auto_attribute_value` |
| `bi_all_in_one_schedule_activity` | `bi_warranty_registration` | `dgii_reports` |
| `export_view_pdf` | `fleet_account_asset` | `fleet_industry_fsm` |
| `fleet_product_rules_renting` | `helpdesk_ticket_signature` | `hms_sale_pos_backend` |
| `hr_payroll_import_inputs` | `ks_dashboard_ninja` | `ks_dn_advance` |
| `l10n_do_account_withholding_tax` | `l10n_do_banks` | `l10n_do_ecf_reception_workflow` |
| `l10n_do_hr_course` | `l10n_do_hr_fleet` | `l10n_do_hr_maintenance` |
| `l10n_do_hr_news` | `l10n_do_hr_news_accounts_receivable` | `l10n_do_hr_news_attendance` |
| `l10n_do_hr_payroll_import_inputs` | `l10n_do_hr_payroll_news` | `l10n_do_hr_payroll_news_attendance` |
| `l10n_do_hr_recruitment` | `l10n_do_hr_recurrent_news` | `l10n_do_payroll_bhd_file` |
| `l10n_do_payroll_bpd_file` | `l10n_do_payroll_brrd_file` | `l10n_do_payroll_file_base` |
| `l10n_do_pos` | `l10n_do_sale_pos_backend` | `l10n_do_sale_pos_backend_reconcile_payment` |
| `l10n_do_sign_to_xml` | `looker_connector` | `odoo_cheque_management` |
| `odoo_document_printer` | `odoo_document_printer_customization_base` | `product_fields_tracking` |
| `product_label_for_zebra_printer` | `product_part_number` | `product_price_checker` |
| `product_product_price_widget` | `product_segment` | `product_stock_qty_date_widgets` |
| `product_warehouse_quantity` | `professional_templates` | `purchase_partner_fields` |
| `purchase_request_currency` | `qztray` | `qztray_base` |
| `qztray_location_labels` | `qztray_partner_labels` | `qztray_product_inventory` |
| `qztray_product_labels` | `qztray_product_purchase` | `repair_helpdesk_custom` |
| `repair_location_settings` | `repair_no_negative_allow` | `repair_warranty_extra_info` |
| `sale_mr_inherit_modify` | `sale_order_with_other_locations` | `sale_partner_fields` |
| `sale_pos_backend` | `sale_pos_backend_card_bin_promotion` | `sale_pos_backend_card_bin_promotion_payments` |
| `sale_pos_backend_discount_display_amount` | `sale_pos_backend_journal_control` | `sale_pos_backend_part_number` |
| `sale_pos_backend_warranty_reports` | `sale_pos_session_link` | `sale_stock_product_price_widget` |
| `sale_stock_qty_date_widgets` | `sh_all_in_one_margin` | `sh_low_stock_notification` |
| `sh_product_multi_barcode` | `sh_restrict_pricelist` | `simplify_access_management` |
| `stock_landed_costs_file` | `website_quotation` | `website_stock_availability` |
| `website_store_pickup` | `whatsapp_connector` | `whatsapp_connector_chatter` |
| `whatsapp_connector_crm` | `whatsapp_connector_pack` | `whatsapp_connector_sale` |
| `wk_odoo_directly_print_reports` |  |  |

## 📦 Módulos pro descubiertos (191)

<details>
<summary>Ver lista completa con estado</summary>

```
✅ PASS        acap_bank_statement_import
⏩ NO_TESTS    account_accountant_cheque
✅ PASS        account_bank_charge_import_base
❌ FAIL        account_bank_charge_import_bhd
❌ FAIL        account_bank_charge_import_bpd
✅ PASS        account_bank_statement_import_csv_patch
⏩ NO_TESTS    account_date_filters
❌ FAIL        account_default_journals
✅ PASS        account_financial_risk_features
✅ PASS        account_followup_extra_features
⏩ NO_TESTS    account_invoice_read_notification
✅ PASS        account_lock_fiscal_date
✅ PASS        account_move_route
❌ FAIL        account_multi_journal_payment
✅ PASS        account_multi_journal_payment_authorization_code
✅ PASS        account_partner_fields
✅ PASS        account_payment_advance_payment
✅ PASS        account_payment_authorization_code
⚠️  NOT_LOADED  account_payment_card_bin
⚠️  NOT_LOADED  account_payment_cash_custom_workflow
❌ FAIL        account_payment_compensation
⏩ NO_TESTS    account_payment_compensation_news
⚠️  NOT_LOADED  account_payment_promotion_discount
✅ PASS        account_payment_reconcile_features
❌ FAIL        account_transfer_features
⏩ NO_TESTS    advanced_web_domain_widget
✅ PASS        apap_bank_statement_import
⚠️  NOT_LOADED  auto_attribute_value
✅ PASS        auto_backup_sh
✅ PASS        bdr_bank_statement_import
✅ PASS        bhd_bank_statement_import
✅ PASS        bhd_panama_bank_statement_import
⏩ NO_TESTS    bi_all_in_one_schedule_activity
⚠️  NOT_LOADED  bi_warranty_registration
✅ PASS        blh_bank_statement_import
✅ PASS        bnc_bank_statement_import
✅ PASS        bpd_bank_statement_import
✅ PASS        bpm_bank_statement_import
✅ PASS        bsc_bank_statement_import
❌ FAIL        crm_helpdesk_custom
⚠️  NOT_LOADED  delivery_buenvio
⏩ NO_TESTS    dgii_reports
⚠️  NOT_LOADED  export_view_pdf
⚠️  NOT_LOADED  fleet_account_asset
⚠️  NOT_LOADED  fleet_industry_fsm
✅ PASS        fleet_product_management
✅ PASS        fleet_product_rules
⚠️  NOT_LOADED  fleet_product_rules_renting
❌ FAIL        helpdesk_sale_custom
⏩ NO_TESTS    helpdesk_ticket_signature
⚠️  NOT_LOADED  hms_account
⚠️  NOT_LOADED  hms_partner
⚠️  NOT_LOADED  hms_sale_pos_backend
⚠️  NOT_LOADED  hms_sales
⚠️  NOT_LOADED  hr_payroll_import_inputs
✅ PASS        jmmb_bank_statement_import
⏩ NO_TESTS    ks_dashboard_ninja
⏩ NO_TESTS    ks_dn_advance
✅ PASS        l10n_do_account_batch_payment_base
❌ FAIL        l10n_do_account_batch_payment_bdr
❌ FAIL        l10n_do_account_batch_payment_bhd
❌ FAIL        l10n_do_account_batch_payment_bpd
✅ PASS        l10n_do_account_batch_payment_ee
⏩ NO_TESTS    l10n_do_account_withholding_tax
❌ FAIL        l10n_do_accounting
✅ PASS        l10n_do_bank_charges_import
⏩ NO_TESTS    l10n_do_banks
❌ FAIL        l10n_do_credit_note
✅ PASS        l10n_do_currency_update
❌ FAIL        l10n_do_document_pools
❌ FAIL        l10n_do_ecf_invoicing
⚠️  NOT_LOADED  l10n_do_ecf_reception
⚠️  NOT_LOADED  l10n_do_ecf_reception_workflow
✅ PASS        l10n_do_ecommerce
⏩ NO_TESTS    l10n_do_hr
⚠️  NOT_LOADED  l10n_do_hr_course
⚠️  NOT_LOADED  l10n_do_hr_fleet
⚠️  NOT_LOADED  l10n_do_hr_maintenance
⏩ NO_TESTS    l10n_do_hr_news
⚠️  NOT_LOADED  l10n_do_hr_news_accounts_receivable
⚠️  NOT_LOADED  l10n_do_hr_news_attendance
⏩ NO_TESTS    l10n_do_hr_payroll
⚠️  NOT_LOADED  l10n_do_hr_payroll_import_inputs
⏩ NO_TESTS    l10n_do_hr_payroll_news
⚠️  NOT_LOADED  l10n_do_hr_payroll_news_attendance
⏩ NO_TESTS    l10n_do_hr_recruitment
⚠️  NOT_LOADED  l10n_do_hr_recurrent_news
❌ FAIL        l10n_do_ncf_validation
⏩ NO_TESTS    l10n_do_payroll_bhd_file
⏩ NO_TESTS    l10n_do_payroll_bpd_file
⏩ NO_TESTS    l10n_do_payroll_brrd_file
⏩ NO_TESTS    l10n_do_payroll_file_base
⏩ NO_TESTS    l10n_do_pos
❌ FAIL        l10n_do_purchase
✅ PASS        l10n_do_rnc_validation
❌ FAIL        l10n_do_sale
⚠️  NOT_LOADED  l10n_do_sale_pos_backend
⚠️  NOT_LOADED  l10n_do_sale_pos_backend_reconcile_payment
⚠️  NOT_LOADED  l10n_do_sign_to_xml
❌ FAIL        l10n_do_withholding_certification
⚠️  NOT_LOADED  looker_connector
✅ PASS        odoo_cheque_features
⏩ NO_TESTS    odoo_cheque_management
⚠️  NOT_LOADED  odoo_document_printer
⚠️  NOT_LOADED  odoo_document_printer_customization_base
❌ FAIL        payment_azul_webpages
❌ FAIL        payment_azul_webservices
🚫 INCOMPAT    payment_bhd
✅ PASS        payment_salesperson
🚫 INCOMPAT    pos_azul
🚫 INCOMPAT    pos_hr_minimal_rights
⚠️  NOT_LOADED  printnode_base
⚠️  NOT_LOADED  product_category_inter_company
⚠️  NOT_LOADED  product_category_multi_company
⏩ NO_TESTS    product_fields_tracking
✅ PASS        product_foreign_cost_price
⚠️  NOT_LOADED  product_label_for_zebra_printer
⚠️  NOT_LOADED  product_part_number
⚠️  NOT_LOADED  product_price_checker
✅ PASS        product_price_history
✅ PASS        product_pricelist_user_restriction
⏩ NO_TESTS    product_product_price_widget
⚠️  NOT_LOADED  product_segment
⏩ NO_TESTS    product_stock_qty_date_widgets
⚠️  NOT_LOADED  product_warehouse_quantity
⚠️  NOT_LOADED  professional_templates
❌ FAIL        purchase_financial_risk
✅ PASS        purchase_financial_risk_features
❌ FAIL        purchase_foreign_cost_update
❌ FAIL        purchase_order_rate
⏩ NO_TESTS    purchase_partner_fields
⚠️  NOT_LOADED  purchase_picking_default
⚠️  NOT_LOADED  purchase_request_currency
✅ PASS        purchase_request_features
⚠️  NOT_LOADED  qztray
⚠️  NOT_LOADED  qztray_base
⚠️  NOT_LOADED  qztray_location_labels
⚠️  NOT_LOADED  qztray_partner_labels
⚠️  NOT_LOADED  qztray_product_inventory
⚠️  NOT_LOADED  qztray_product_labels
⚠️  NOT_LOADED  qztray_product_purchase
⚠️  NOT_LOADED  repair_helpdesk_custom
⚠️  NOT_LOADED  repair_location_settings
⚠️  NOT_LOADED  repair_no_negative_allow
✅ PASS        repair_services
⚠️  NOT_LOADED  repair_warranty_extra_info
⚠️  NOT_LOADED  res_partner_phone_search
✅ PASS        sale_crm_features
✅ PASS        sale_financial_risk_features
⚠️  NOT_LOADED  sale_mr_inherit_modify
⚠️  NOT_LOADED  sale_order_glasses_description
❌ FAIL        sale_order_rate
✅ PASS        sale_order_time_total
⚠️  NOT_LOADED  sale_order_with_other_locations
⏩ NO_TESTS    sale_partner_fields
⚠️  NOT_LOADED  sale_pos_backend
⚠️  NOT_LOADED  sale_pos_backend_card_bin_promotion
⚠️  NOT_LOADED  sale_pos_backend_card_bin_promotion_payments
⚠️  NOT_LOADED  sale_pos_backend_discount_display_amount
⚠️  NOT_LOADED  sale_pos_backend_journal_control
🚫 INCOMPAT    sale_pos_backend_multi_journal_payment
⚠️  NOT_LOADED  sale_pos_backend_part_number
⚠️  NOT_LOADED  sale_pos_backend_warranty_reports
⚠️  NOT_LOADED  sale_pos_session_link
✅ PASS        sale_product_generic_readonly
⏩ NO_TESTS    sale_stock_product_price_widget
⏩ NO_TESTS    sale_stock_qty_date_widgets
❌ FAIL        sale_stock_restriction
❌ FAIL        sale_stock_serial
⚠️  NOT_LOADED  sales_bavel
✅ PASS        scotiabank_statement_import
⚠️  NOT_LOADED  sh_all_in_one_margin
⚠️  NOT_LOADED  sh_low_stock_notification
⚠️  NOT_LOADED  sh_product_multi_barcode
⚠️  NOT_LOADED  sh_restrict_pricelist
⏩ NO_TESTS    simplify_access_management
✅ PASS        stock_inventory_forecasted_report
❌ FAIL        stock_landed_costs_features
⏩ NO_TESTS    stock_landed_costs_file
❌ FAIL        stock_picking_invoice_link_extra
❌ FAIL        stock_warehouse_orderpoint_uom
⏩ NO_TESTS    tss_report
⏩ NO_TESTS    website_quotation
⏩ NO_TESTS    website_stock_availability
⚠️  NOT_LOADED  website_store_pickup
⚠️  NOT_LOADED  whatsapp_connector
⚠️  NOT_LOADED  whatsapp_connector_chatter
⚠️  NOT_LOADED  whatsapp_connector_crm
⚠️  NOT_LOADED  whatsapp_connector_pack
⚠️  NOT_LOADED  whatsapp_connector_sale
⚠️  NOT_LOADED  wk_odoo_directly_print_reports
```

</details>
