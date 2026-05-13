# Odoo Pro v19 — Reporte de Tests

> Generado: 2026-05-13 10:49:09

## Resumen

| Métrica | Valor |
|---------|-------|
| Módulos pro descubiertos | 192 |
| Instalados correctamente | 51 |
| Versión incompatible (no instalables) | 4 |
| Fallaron instalación | 1 |
| Módulos pro con tests | 91 |
| Módulos con tests corridos | 33 |
| Tests individuales corridos | 304 |
| ↳ Fallaron (assert) | 4 |
| ↳ Errores (excepción) | 45 |
| ✅ Módulos — todos los tests pasaron | 17 |
| ❌ Módulos — tests fallaron | 16 |
| ⚠️  Módulos con warnings en tests | 1 |
| ⏩ Módulos pro sin directorio tests/ | 97 |
| Tiempo fase instalación | 59s (0m 59s) |
| Tiempo fase tests | 546s (9m 6s) |

## ✅ Tests pasaron (17 módulos)

| Módulo | Tests | Tiempo |
|--------|:-----:|:------:|
| `account_bank_charge_import_base` | 8 | 0.1s |
| `account_financial_risk_features` | 18 | 1.57s |
| `account_followup_extra_features` | 12 | 2.08s |
| `account_lock_fiscal_date` | 14 | 2.91s |
| `account_move_route` | 5 | 2.67s |
| `account_payment_advance_payment` | 7 | 0.09s |
| `account_payment_internal_transfer` | 14 | 5.53s |
| `account_payment_reconcile_features` | 12 | 4.26s |
| `auto_backup_sh` ⚠️ | 28 | 0.05s |
| `bnc_bank_statement_import` | 6 | 2.12s |
| `fleet_product_management` | 24 | 0.78s |
| `l10n_do_account_batch_payment_base` | 5 | 0.14s |
| `l10n_do_currency_update` | 4 | 0.67s |
| `odoo_cheque_features` | 3 | 0.07s |
| `product_foreign_cost_price` | 9 | 0.08s |
| `product_price_history` | 14 | 0.39s |
| `stock_warehouse_orderpoint_uom` | 7 | 0.73s |

## ❌ Tests fallaron (16 módulos)

### `account_bank_charge_import_bhd`

- Failures: **0** | Errors: **2** | Tests: 6 | Tiempo: 0.2s

```
ERROR: TestAccountBankChargeImportBHD.test_001_bhd_bank_charge_import_dop
ERROR: TestAccountBankChargeImportBHD.test_002_bhd_bank_charge_import_usd
```

### `account_bank_charge_import_bpd`

- Failures: **0** | Errors: **2** | Tests: 6 | Tiempo: 0.22s

```
ERROR: TestAccountBankChargeImportBPD.test_001_bpd_bank_charge_import_txt
ERROR: TestAccountBankChargeImportBPD.test_002_bpd_bank_charge_import_csv
```

### `account_bank_statement_import_csv_patch`

- Failures: **0** | Errors: **1** | Tests: 4 | Tiempo: 0.25s

```
ERROR: TestBankStatementDraft.test_01_statement_line_draft_and_balance_calculation
```

### `account_default_journals`

- Failures: **2** | Errors: **4** | Tests: 8 | Tiempo: 2.79s

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

### `account_multi_journal_payment_authorization_code`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.08s

```
ERROR: setUpClass (odoo.addons.account_multi_journal_payment_authorization_code.tests.test_multi_journal_authorization_code.TestMultiJournalAuthorizationCode)
```

### `account_partner_fields`

- Failures: **0** | Errors: **1** | Tests: 3 | Tiempo: 0.1s

```
ERROR: AccountMoveTest.test_001_onchange_type
```

### `account_payment_authorization_code`

- Failures: **0** | Errors: **4** | Tests: 6 | Tiempo: 0.05s

```
ERROR: TestAccountPaymentAuthorizationCode.test_payment_constraint_without_code_raises
ERROR: TestAccountPaymentAuthorizationCode.test_payment_optional_when_company_disabled
ERROR: TestAccountPaymentAuthorizationCode.test_payment_with_code_posts
ERROR: TestAccountPaymentAuthorizationCode.test_require_authorization_code_compute
```

### `account_payment_compensation`

- Failures: **1** | Errors: **15** | Tests: 28 | Tiempo: 6.27s

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

- Failures: **0** | Errors: **3** | Tests: 6 | Tiempo: 0.39s

```
ERROR: setUpClass (odoo.addons.account_transfer_features.tests.test_transfer_features.TestDailyFrequency)
ERROR: setUpClass (odoo.addons.account_transfer_features.tests.test_transfer_features.TestPartnerInMoveLines)
ERROR: setUpClass (odoo.addons.account_transfer_features.tests.test_transfer_features.TestPartnerField)
```

### `l10n_do_accounting`

- Failures: **0** | Errors: **2** | Tests: 4 | Tiempo: 0.0s

```
ERROR: setUpClass (odoo.addons.l10n_do_accounting.tests.test_account_journal.AccountJournalTest)
ERROR: setUpClass (odoo.addons.l10n_do_accounting.tests.test_account_move.AccountMoveTest)
```

### `payment_salesperson`

- Failures: **0** | Errors: **6** | Tests: 13 | Tiempo: 0.38s

```
ERROR: TestPaymentSalesperson.test_create_assigns_salesperson_from_partner
ERROR: TestPaymentSalesperson.test_create_from_invoice_first_invoice_mode
ERROR: TestPaymentSalesperson.test_create_no_salesperson_when_partner_has_none
ERROR: TestPaymentSalesperson.test_write_create_uid_as_regular_user_denied
ERROR: TestPaymentSalesperson.test_write_salesperson_as_account_manager_allowed
ERROR: TestPaymentSalesperson.test_write_salesperson_as_regular_user_denied
```

### `purchase_financial_risk`

- Failures: **1** | Errors: **0** | Tests: 20 | Tiempo: 0.98s

```
FAIL: TestPurchaseFinancialRisk.test_partner_risk_purchase_order_compute
```

### `purchase_foreign_cost_update`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 0.11s

```
ERROR: setUpClass (odoo.addons.purchase_foreign_cost_update.tests.test_purchase_foreign_cost_update.TestPurchaseForeignCostUpdate)
```

### `purchase_order_rate`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 1.34s

```
ERROR: setUpClass (odoo.addons.purchase_order_rate.tests.test_purchase_rate.TestPurchaseOrderRate)
```

### `sale_order_rate`

- Failures: **0** | Errors: **1** | Tests: 2 | Tiempo: 1.34s

```
ERROR: setUpClass (odoo.addons.sale_order_rate.tests.test_sale_rate.TestSaleOrderRate)
```

## 🔴 Fallaron instalación (1 módulos pro)

| Módulo | Error |
|--------|-------|
| `hr_payroll_import_inputs` | Failed to load registry |

## 🚫 Versión incompatible (4 módulos pro)

| Módulo |
|--------|
| `payment_bhd` |
| `pos_azul` |
| `pos_hr_minimal_rights` |
| `sale_pos_backend_multi_journal_payment` |

## ⚠️  Warnings en tests (1 módulos)

<details>
<summary><code>auto_backup_sh</code> (1 warnings)</summary>

```
File not found: Backup file _daily.sql.gz not found in path /home/odoo/backup.daily
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

## 📦 Módulos pro descubiertos (192)

<details>
<summary>Ver lista completa con estado</summary>

```
⚠️  NOT_LOADED  acap_bank_statement_import
⏩ NO_TESTS    account_accountant_cheque
✅ PASS        account_bank_charge_import_base
❌ FAIL        account_bank_charge_import_bhd
❌ FAIL        account_bank_charge_import_bpd
❌ FAIL        account_bank_statement_import_csv_patch
⏩ NO_TESTS    account_date_filters
❌ FAIL        account_default_journals
✅ PASS        account_financial_risk_features
✅ PASS        account_followup_extra_features
⏩ NO_TESTS    account_invoice_read_notification
✅ PASS        account_lock_fiscal_date
✅ PASS        account_move_route
❌ FAIL        account_multi_journal_payment
❌ FAIL        account_multi_journal_payment_authorization_code
❌ FAIL        account_partner_fields
✅ PASS        account_payment_advance_payment
❌ FAIL        account_payment_authorization_code
⚠️  NOT_LOADED  account_payment_card_bin
⚠️  NOT_LOADED  account_payment_cash_custom_workflow
❌ FAIL        account_payment_compensation
⚠️  NOT_LOADED  account_payment_compensation_news
✅ PASS        account_payment_internal_transfer
⚠️  NOT_LOADED  account_payment_promotion_discount
✅ PASS        account_payment_reconcile_features
❌ FAIL        account_transfer_features
⏩ NO_TESTS    advanced_web_domain_widget
⚠️  NOT_LOADED  apap_bank_statement_import
⚠️  NOT_LOADED  auto_attribute_value
✅ PASS        auto_backup_sh
⚠️  NOT_LOADED  bdr_bank_statement_import
⚠️  NOT_LOADED  bhd_bank_statement_import
⚠️  NOT_LOADED  bhd_panama_bank_statement_import
⏩ NO_TESTS    bi_all_in_one_schedule_activity
⚠️  NOT_LOADED  bi_warranty_registration
⚠️  NOT_LOADED  blh_bank_statement_import
✅ PASS        bnc_bank_statement_import
⚠️  NOT_LOADED  bpd_bank_statement_import
⚠️  NOT_LOADED  bpm_bank_statement_import
⚠️  NOT_LOADED  bsc_bank_statement_import
⚠️  NOT_LOADED  crm_helpdesk_custom
⚠️  NOT_LOADED  delivery_buenvio
⏩ NO_TESTS    dgii_reports
⚠️  NOT_LOADED  export_view_pdf
⚠️  NOT_LOADED  fleet_account_asset
⚠️  NOT_LOADED  fleet_industry_fsm
✅ PASS        fleet_product_management
⚠️  NOT_LOADED  fleet_product_rules
⚠️  NOT_LOADED  fleet_product_rules_renting
⚠️  NOT_LOADED  helpdesk_sale_custom
⏩ NO_TESTS    helpdesk_ticket_signature
⚠️  NOT_LOADED  hms_account
⚠️  NOT_LOADED  hms_partner
⚠️  NOT_LOADED  hms_sale_pos_backend
⚠️  NOT_LOADED  hms_sales
🔴 INST_FAIL   hr_payroll_import_inputs
⚠️  NOT_LOADED  jmmb_bank_statement_import
⏩ NO_TESTS    ks_dashboard_ninja
⏩ NO_TESTS    ks_dn_advance
✅ PASS        l10n_do_account_batch_payment_base
⚠️  NOT_LOADED  l10n_do_account_batch_payment_bdr
⚠️  NOT_LOADED  l10n_do_account_batch_payment_bhd
⚠️  NOT_LOADED  l10n_do_account_batch_payment_bpd
⚠️  NOT_LOADED  l10n_do_account_batch_payment_ee
⚠️  NOT_LOADED  l10n_do_account_withholding_tax
❌ FAIL        l10n_do_accounting
⚠️  NOT_LOADED  l10n_do_bank_charges_import
⏩ NO_TESTS    l10n_do_banks
⚠️  NOT_LOADED  l10n_do_credit_note
✅ PASS        l10n_do_currency_update
⚠️  NOT_LOADED  l10n_do_document_pools
⚠️  NOT_LOADED  l10n_do_ecf_invoicing
⚠️  NOT_LOADED  l10n_do_ecf_reception
⚠️  NOT_LOADED  l10n_do_ecf_reception_workflow
⚠️  NOT_LOADED  l10n_do_ecommerce
⏩ NO_TESTS    l10n_do_hr
⚠️  NOT_LOADED  l10n_do_hr_course
⚠️  NOT_LOADED  l10n_do_hr_fleet
⚠️  NOT_LOADED  l10n_do_hr_maintenance
⏩ NO_TESTS    l10n_do_hr_news
⚠️  NOT_LOADED  l10n_do_hr_news_accounts_receivable
⚠️  NOT_LOADED  l10n_do_hr_news_attendance
⚠️  NOT_LOADED  l10n_do_hr_payroll
⚠️  NOT_LOADED  l10n_do_hr_payroll_import_inputs
⚠️  NOT_LOADED  l10n_do_hr_payroll_news
⚠️  NOT_LOADED  l10n_do_hr_payroll_news_attendance
⏩ NO_TESTS    l10n_do_hr_recruitment
⚠️  NOT_LOADED  l10n_do_hr_recurrent_news
⚠️  NOT_LOADED  l10n_do_ncf_validation
⚠️  NOT_LOADED  l10n_do_payroll_bhd_file
⚠️  NOT_LOADED  l10n_do_payroll_bpd_file
⚠️  NOT_LOADED  l10n_do_payroll_brrd_file
⚠️  NOT_LOADED  l10n_do_payroll_file_base
⚠️  NOT_LOADED  l10n_do_pos
⚠️  NOT_LOADED  l10n_do_purchase
⚠️  NOT_LOADED  l10n_do_rnc_validation
⚠️  NOT_LOADED  l10n_do_sale
⚠️  NOT_LOADED  l10n_do_sale_pos_backend
⚠️  NOT_LOADED  l10n_do_sale_pos_backend_reconcile_payment
⚠️  NOT_LOADED  l10n_do_sign_to_xml
⚠️  NOT_LOADED  l10n_do_withholding_certification
⚠️  NOT_LOADED  looker_connector
✅ PASS        odoo_cheque_features
⏩ NO_TESTS    odoo_cheque_management
⚠️  NOT_LOADED  odoo_document_printer
⚠️  NOT_LOADED  odoo_document_printer_customization_base
⚠️  NOT_LOADED  payment_azul_webpages
⚠️  NOT_LOADED  payment_azul_webservices
🚫 INCOMPAT    payment_bhd
❌ FAIL        payment_salesperson
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
⚠️  NOT_LOADED  product_pricelist_user_restriction
⚠️  NOT_LOADED  product_product_price_widget
⚠️  NOT_LOADED  product_segment
⚠️  NOT_LOADED  product_stock_qty_date_widgets
⚠️  NOT_LOADED  product_warehouse_quantity
⚠️  NOT_LOADED  professional_templates
❌ FAIL        purchase_financial_risk
⚠️  NOT_LOADED  purchase_financial_risk_features
❌ FAIL        purchase_foreign_cost_update
❌ FAIL        purchase_order_rate
⏩ NO_TESTS    purchase_partner_fields
⚠️  NOT_LOADED  purchase_picking_default
⚠️  NOT_LOADED  purchase_request_currency
⚠️  NOT_LOADED  purchase_request_features
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
⚠️  NOT_LOADED  repair_services
⚠️  NOT_LOADED  repair_warranty_extra_info
⚠️  NOT_LOADED  res_partner_phone_search
⚠️  NOT_LOADED  sale_crm_features
⚠️  NOT_LOADED  sale_financial_risk_features
⚠️  NOT_LOADED  sale_mr_inherit_modify
⚠️  NOT_LOADED  sale_order_glasses_description
❌ FAIL        sale_order_rate
⚠️  NOT_LOADED  sale_order_time_total
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
⚠️  NOT_LOADED  sale_product_generic_readonly
⚠️  NOT_LOADED  sale_stock_product_price_widget
⚠️  NOT_LOADED  sale_stock_qty_date_widgets
⚠️  NOT_LOADED  sale_stock_restriction
⚠️  NOT_LOADED  sale_stock_serial
⚠️  NOT_LOADED  sales_bavel
⚠️  NOT_LOADED  scotiabank_statement_import
⚠️  NOT_LOADED  sh_all_in_one_margin
⚠️  NOT_LOADED  sh_low_stock_notification
⚠️  NOT_LOADED  sh_product_multi_barcode
⚠️  NOT_LOADED  sh_restrict_pricelist
⏩ NO_TESTS    simplify_access_management
⚠️  NOT_LOADED  stock_inventory_forecasted_report
⚠️  NOT_LOADED  stock_landed_costs_features
⚠️  NOT_LOADED  stock_landed_costs_file
⚠️  NOT_LOADED  stock_picking_invoice_link_extra
✅ PASS        stock_warehouse_orderpoint_uom
⚠️  NOT_LOADED  tss_report
⚠️  NOT_LOADED  website_quotation
⚠️  NOT_LOADED  website_stock_availability
⚠️  NOT_LOADED  website_store_pickup
⚠️  NOT_LOADED  whatsapp_connector
⚠️  NOT_LOADED  whatsapp_connector_chatter
⚠️  NOT_LOADED  whatsapp_connector_crm
⚠️  NOT_LOADED  whatsapp_connector_pack
⚠️  NOT_LOADED  whatsapp_connector_sale
⚠️  NOT_LOADED  wk_odoo_directly_print_reports
```

</details>
