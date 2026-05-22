# 🧪 Odoo Pro v17 — Test Report

> **Generado:** 21/05/2026 10:52:33 &nbsp;|&nbsp; **Instalación:** 0s &nbsp;|&nbsp; **Tests:** 5m 39s

---

## 📊 Resumen Ejecutivo

| KPI | Valor | Detalle |
|-----|:-----:|---------|
| **Módulos descubiertos** | 173 | 172 instalables · 1 pendientes migración |
| **Módulos instalados** | 172 / 172 | 0 fallaron · 0 incompatibles |
| **Módulos con tests** | 49 / 53 | 49 pasaron · 0 fallaron |
| **Tests individuales** | 390 | 0 assert · 0 excepciones |
| **Tasa de éxito (módulos)** | 100% | `████████████████████` 100% |
| **Tasa de éxito (tests)** | 100% | `████████████████████` 100% |

### Estado por categoría

| Estado | Módulos | Descripción |
|--------|:-------:|-------------|
| ✅ Pasaron | **49** | módulos con todos los tests en verde |
| ❌ Fallaron | **0** | módulos con fallos o errores |
| ⚠️  Con warnings | **1** | módulos con advertencias |
| ⏩ Sin tests | **119** | módulos sin directorio tests/ |
| 🔒 No instalables | **1** | installable=False — pendientes migración |
| 🚫 Incompatibles | **0** | versión incompatible con v17 |
| 🔴 Error install | **0** | fallaron durante la instalación |

---

## ✅ Tests Pasaron &nbsp; `49 módulos`

| Módulo | Tests | Tiempo | Autor | Estado |
|--------|:-----:|:------:|-------|:------:|
| `acap_bank_statement_import` | 5 | 5.2s | Luis Fernandez | ✅ |
| `account_bank_charge_import_bhd` | 4 | 6.93s | Luis Fernandez | ✅ |
| `account_bank_charge_import_bpd` | 4 | 5.65s | Luis Fernandez | ✅ |
| `account_invoice_rate` | 4 | 2.06s | Luis Fernandez | ✅ |
| `account_partner_fields` | 3 | 0.01s | Luis Fernandez | ✅ |
| `account_payment_compensation` | 28 | 6.87s | Luis Fernandez | ✅ |
| `account_payment_compensation_pos` | 19 | 3.71s | Luis Fernandez | ✅ |
| `account_reconcile_payment` | 3 | 7.98s | Luis Fernandez | ✅ |
| `apap_bank_statement_import` | 5 | 0.27s | Luis Fernandez | ✅ |
| `bdi_bank_statement_import` | 5 | 0.0s | Luis Fernandez | ✅ |
| `bdr_bank_statement_import` | 4 | 2.39s | Luis Fernandez | ✅ |
| `bhd_bank_statement_import` | 4 | 9.11s | Luis Fernandez | ✅ |
| `bhd_panama_bank_statement_import` | 4 | 0.32s | Luis Fernandez | ✅ |
| `blh_bank_statement_import` | 4 | 2.21s | Luis Fernandez | ✅ |
| `bnc_bank_statement_import` | 4 | 0.63s | Luis Fernandez | ✅ |
| `bpd_bank_statement_import` | 4 | 2.82s | Luis Fernandez | ✅ |
| `bpm_bank_statement_import` | 4 | 2.2s | Luis Fernandez | ✅ |
| `bsc_bank_statement_import` | 4 | 3.51s | Luis Fernandez | ✅ |
| `delivery_buenvio` | 5 | 1.17s | Luis Fernandez | ✅ |
| `hms_account` | 3 | 2.09s | Luis Fernandez | ✅ |
| `hms_sales` | 4 | 0.28s | Luis Fernandez | ✅ |
| `jmmb_bank_statement_import` | 4 | 2.43s | Luis Fernandez | ✅ |
| `l10n_do_accounting` | 17 | 22.07s | Luis Fernandez | ✅ |
| `l10n_do_currency_update` | 4 | 1.0s | andres-pcg | ✅ |
| `l10n_do_ecf_invoicing` | 18 | 15.42s | Luis Fernandez | ✅ |
| `l10n_do_ecf_reception` | 9 | 3.78s | Luis Fernandez | ✅ |
| `l10n_do_hr_expense` | 35 | 4.5s | Luis Fernandez | ✅ |
| `l10n_do_ncf_validation` | 5 | 4.77s | Luis Fernandez | ✅ |
| `l10n_do_payroll_bhd_file` | 9 | 0.26s | Luis Fernandez | ✅ |
| `l10n_do_payroll_bpd_file` | 12 | 0.51s | Luis Fernandez | ✅ |
| `l10n_do_payroll_brrd_file` | 10 | 0.3s | Luis Fernandez | ✅ |
| `l10n_do_payroll_file_base` | 8 | 0.21s | Luis Fernandez | ✅ |
| `l10n_do_withholding_certification` | 5 | 2.47s | Luis Fernandez | ✅ |
| `payment_azul` ⚠️ | 43 | 0.87s | Luis Fernandez | ✅⚠️ |
| `product_category_inter_company` | 3 | 0.9s | Luis Fernandez | ✅ |
| `product_category_multi_company` | 3 | 2.11s | Luis Fernandez | ✅ |
| `purchase_order_rate` | 4 | 2.01s | Luis Fernandez | ✅ |
| `purchase_picking_default` | 7 | 0.7s | Luis Fernandez | ✅ |
| `purchase_request_features` | 3 | 0.06s | Luis Fernandez | ✅ |
| `res_partner_phone_search` | 3 | 0.33s | Luis Fernandez | ✅ |
| `sale_order_glasses_description` | 3 | 0.18s | Luis Fernandez | ✅ |
| `sale_order_rate` | 3 | 2.0s | Luis Fernandez | ✅ |
| `sale_order_time_total` | 4 | 0.91s | Luis Fernandez | ✅ |
| `sale_stock_features` | 4 | 0.24s | Luis Fernandez | ✅ |
| `sales_bavel` | 19 | 1.04s | Luis Fernandez | ✅ |
| `scotiabank_statement_import` | 4 | 4.21s | Luis Fernandez | ✅ |
| `serial_number_report` | 11 | 0.43s | Luis Fernandez | ✅ |
| `stock_landed_costs_features` | 3 | 2.82s | Luis Fernandez | ✅ |
| `website_currency_convertion` | 13 | 0.6s | Luis Fernandez | ✅ |

## ❌ Tests Fallaron &nbsp; `0 módulos`

> 🎉 **¡Todos los módulos con tests pasaron!**

---

## 🔴 Fallos de Instalación &nbsp; `0 módulos`

> ✅ Todos los módulos se instalaron correctamente.

## 🚫 Versión Incompatible &nbsp; `0 módulos`

> ✅ Ningún módulo con versión incompatible.

## 🔒 Pendientes de Migración a v17 &nbsp; `1 módulos`

> Módulos con `installable = False`. Excluidos del proceso de instalación y tests.

| Módulo | Módulo | Módulo |
|------|------|------|
| `sale_pos_backend_discount_display_amount` |  |  |

## ⚠️  Warnings en Tests &nbsp; `1 módulos`

<details><summary><code>payment_azul</code> — 1 warnings</summary>

```text
Azul: DataVaultToken has unexpected format, skipping tokenization for transaction Test Transaction
```
</details>

## ⏩ Sin Directorio de Tests &nbsp; `119 módulos`

| Módulo | Módulo | Módulo |
|------|------|------|
| `account_accountant_cheque` | `account_auto_transfer_features` | `account_bank_statement_import_csv_patch` |
| `account_date_filters` | `account_default_journals` | `account_financial_risk_features` |
| `account_followup_extra_features` | `account_followup_multi_partner` | `account_invoice_read_notification` |
| `account_lock_fiscal_date` | `account_move_route` | `account_multi_journal_payment` |
| `account_multi_journal_payment_authorization_code` | `account_payment_advance_payment` | `account_payment_authorization_code` |
| `account_payment_card_bin` | `account_payment_cash_custom_workflow` | `account_payment_compensation_news` |
| `account_payment_promotion_discount` | `account_payment_reconcile_features` | `auto_attribute_value` |
| `auto_backup_sh` | `crm_helpdesk_custom` | `dgii_reports` |
| `fleet_account_asset` | `fleet_industry_fsm` | `fleet_product_management` |
| `fleet_product_rules` | `fleet_product_rules_renting` | `helpdesk_sale_custom` |
| `helpdesk_ticket_signature` | `hms_sale_pos_backend` | `hr_payroll_import_inputs` |
| `l10n_do_account_batch_payment_base` | `l10n_do_account_batch_payment_bdr` | `l10n_do_account_batch_payment_bhd` |
| `l10n_do_account_batch_payment_bpd` | `l10n_do_account_batch_payment_ee` | `l10n_do_bank_charges_import` |
| `l10n_do_banks` | `l10n_do_credit_note` | `l10n_do_credit_note_ecf` |
| `l10n_do_document_pools` | `l10n_do_ecf_reception_workflow` | `l10n_do_ecf_status_check` |
| `l10n_do_ecommerce` | `l10n_do_hr` | `l10n_do_hr_bonus_legal` |
| `l10n_do_hr_course` | `l10n_do_hr_fleet` | `l10n_do_hr_maintenance` |
| `l10n_do_hr_news` | `l10n_do_hr_news_accounts_receivable` | `l10n_do_hr_news_attendance` |
| `l10n_do_hr_payroll_import_inputs` | `l10n_do_hr_payroll_news` | `l10n_do_hr_payroll_news_attendance` |
| `l10n_do_hr_recruitment` | `l10n_do_hr_recurrent_news` | `l10n_do_pos` |
| `l10n_do_pos_features` | `l10n_do_purchase` | `l10n_do_rnc_validation` |
| `l10n_do_sale` | `l10n_do_sale_pos_backend` | `l10n_do_sale_pos_backend_reconcile_payment` |
| `l10n_do_sign_to_xml` | `payment_azul_webservices` | `payment_bhd` |
| `payment_salesperson` | `payroll_dynamic_xls_report` | `pos_azul` |
| `pos_cardnet` | `pos_hr_minimal_rights` | `product_fields_tracking` |
| `product_foreign_cost_price` | `product_label_layout` | `product_part_number` |
| `product_price_history` | `product_pricelist_user_restriction` | `product_product_price_widget` |
| `product_segment` | `product_stock_qty_date_widgets` | `purchase_financial_risk` |
| `purchase_financial_risk_features` | `purchase_foreign_cost_update` | `purchase_partner_fields` |
| `purchase_request_currency` | `qztray_base_features` | `recurring_sale_order_app` |
| `recurring_sale_order_app_features` | `repair_no_negative_allow` | `repair_services` |
| `sale_crm_features` | `sale_financial_risk_features` | `sale_mr_inherit_modify` |
| `sale_order_with_other_locations` | `sale_partner_fields` | `sale_pos_backend` |
| `sale_pos_backend_card_bin_promotion` | `sale_pos_backend_card_bin_promotion_payments` | `sale_pos_backend_journal_control` |
| `sale_pos_backend_multi_journal_payment` | `sale_pos_backend_part_number` | `sale_pos_session_link` |
| `sale_product_generic_readonly` | `sale_stock_product_price_widget` | `sale_stock_qty_date_widgets` |
| `sale_stock_restriction` | `sale_stock_serial` | `sale_subscription_draft_invoice` |
| `stock_account_fields_tracking` | `stock_inventory_forecasted_report` | `stock_landed_costs_file` |
| `stock_picking_invoice_link_extra` | `stock_warehouse_orderpoint_uom` | `website_quotation` |
| `website_stock_availability` | `website_store_pickup` |  |

---

## 📦 Inventario Completo &nbsp; `173 módulos`

<details>
<summary>Expandir inventario completo</summary>

| Estado | Módulo | Autor |
|:------:|--------|-------|
| ✅ `PASS` | `acap_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_accountant_cheque` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_auto_transfer_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_bank_charge_import_base` | Luis Fernandez |
| ✅ `PASS` | `account_bank_charge_import_bhd` | Luis Fernandez |
| ✅ `PASS` | `account_bank_charge_import_bpd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_bank_statement_import_csv_patch` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_date_filters` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_default_journals` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_financial_risk_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_followup_extra_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_followup_multi_partner` | Luis Fernandez |
| ✅ `PASS` | `account_invoice_rate` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_invoice_read_notification` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_lock_fiscal_date` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_move_route` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_multi_journal_payment` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_multi_journal_payment_authorization_code` | Luis Fernandez |
| ✅ `PASS` | `account_partner_fields` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_advance_payment` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_authorization_code` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_card_bin` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_cash_custom_workflow` | Luis Fernandez |
| ✅ `PASS` | `account_payment_compensation` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_compensation_news` | Luis Fernandez |
| ✅ `PASS` | `account_payment_compensation_pos` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_promotion_discount` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_reconcile_features` | Luis Fernandez |
| ✅ `PASS` | `account_reconcile_payment` | Luis Fernandez |
| ✅ `PASS` | `apap_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `auto_attribute_value` | Luis Fernandez |
| ⏩ `NO_TESTS` | `auto_backup_sh` | Luis Fernandez |
| ✅ `PASS` | `bdi_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bdr_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bhd_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bhd_panama_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `blh_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bnc_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bpd_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bpm_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bsc_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `crm_helpdesk_custom` | Luis Fernandez |
| ✅ `PASS` | `delivery_buenvio` | Luis Fernandez |
| ⏩ `NO_TESTS` | `dgii_reports` | Erick Cuesto |
| ⏩ `NO_TESTS` | `fleet_account_asset` | Luis Fernandez |
| ⏩ `NO_TESTS` | `fleet_industry_fsm` | Luis Fernandez |
| ⏩ `NO_TESTS` | `fleet_product_management` | Luis Fernandez |
| ⏩ `NO_TESTS` | `fleet_product_rules` | Luis Fernandez |
| ⏩ `NO_TESTS` | `fleet_product_rules_renting` | Luis Fernandez |
| ⏩ `NO_TESTS` | `helpdesk_sale_custom` | Luis Fernandez |
| ⏩ `NO_TESTS` | `helpdesk_ticket_signature` | Luis Fernandez |
| ✅ `PASS` | `hms_account` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hms_partner` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hms_sale_pos_backend` | Luis Fernandez |
| ✅ `PASS` | `hms_sales` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hr_payroll_import_inputs` | Luis Fernandez |
| ✅ `PASS` | `jmmb_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_base` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bdr` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bhd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bpd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_ee` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_accounting` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_bank_charges_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_banks` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_credit_note` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_credit_note_ecf` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_currency_update` | andres-pcg |
| ⏩ `NO_TESTS` | `l10n_do_document_pools` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_ecf_invoicing` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_ecf_reception` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_ecf_reception_workflow` | Daniel Alexander Pereyra Beltran |
| ⏩ `NO_TESTS` | `l10n_do_ecf_status_check` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_ecommerce` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_bonus_legal` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_course` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_hr_expense` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_fleet` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_maintenance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_news` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_news_accounts_receivable` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_news_attendance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_payroll` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_payroll_import_inputs` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_payroll_news` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_payroll_news_attendance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_recruitment` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_recurrent_news` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_ncf_validation` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_payroll_bhd_file` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_payroll_bpd_file` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_payroll_brrd_file` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_payroll_file_base` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_pos` | andrp92 |
| ⏩ `NO_TESTS` | `l10n_do_pos_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_purchase` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_rnc_validation` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_sale` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_sale_pos_backend` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_sale_pos_backend_reconcile_payment` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_sign_to_xml` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_withholding_certification` | Luis Fernandez |
| ✅⚠️ `PASS+W` | `payment_azul` | Luis Fernandez |
| ⏩ `NO_TESTS` | `payment_azul_webservices` | Luis Fernandez |
| ⏩ `NO_TESTS` | `payment_bhd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `payment_salesperson` | Luis Fernandez |
| ⏩ `NO_TESTS` | `payroll_dynamic_xls_report` | Luis Fernandez |
| ⏩ `NO_TESTS` | `pos_azul` | Luis Fernandez |
| ⏩ `NO_TESTS` | `pos_cardnet` | Erick Cuesto |
| ⏩ `NO_TESTS` | `pos_hr_minimal_rights` | Erick Cuesto |
| ✅ `PASS` | `product_category_inter_company` | Luis Fernandez |
| ✅ `PASS` | `product_category_multi_company` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_fields_tracking` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_foreign_cost_price` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_label_layout` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_part_number` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_price_history` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_pricelist_user_restriction` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_product_price_widget` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_segment` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_stock_qty_date_widgets` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_financial_risk` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_financial_risk_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_foreign_cost_update` | Luis Fernandez |
| ✅ `PASS` | `purchase_order_rate` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_partner_fields` | Luis Fernandez |
| ✅ `PASS` | `purchase_picking_default` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_request_currency` | Luis Fernandez |
| ✅ `PASS` | `purchase_request_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `qztray_base_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `recurring_sale_order_app` | Luis Fernandez |
| ⏩ `NO_TESTS` | `recurring_sale_order_app_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `repair_no_negative_allow` | Luis Fernandez |
| ⏩ `NO_TESTS` | `repair_services` | Luis Fernandez |
| ✅ `PASS` | `res_partner_phone_search` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_crm_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_financial_risk_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_mr_inherit_modify` | Luis Fernandez |
| ✅ `PASS` | `sale_order_glasses_description` | Luis Fernandez |
| ✅ `PASS` | `sale_order_rate` | Luis Fernandez |
| ✅ `PASS` | `sale_order_time_total` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_order_with_other_locations` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_partner_fields` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_backend` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_backend_card_bin_promotion` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_backend_card_bin_promotion_payments` | Luis Fernandez |
| 🔒 `NO_INST` | `sale_pos_backend_discount_display_amount` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_backend_journal_control` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_backend_multi_journal_payment` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_backend_part_number` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_pos_session_link` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_product_generic_readonly` | Luis Fernandez |
| ✅ `PASS` | `sale_stock_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_stock_product_price_widget` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_stock_qty_date_widgets` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_stock_restriction` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_stock_serial` | Luis Fernandez |
| ⏩ `NO_TESTS` | `sale_subscription_draft_invoice` | Luis Fernandez |
| ✅ `PASS` | `sales_bavel` | Luis Fernandez |
| ✅ `PASS` | `scotiabank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `serial_number_report` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_account_fields_tracking` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_inventory_forecasted_report` | Luis Fernandez |
| ✅ `PASS` | `stock_landed_costs_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_landed_costs_file` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_picking_invoice_link_extra` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_warehouse_orderpoint_uom` | Luis Fernandez |
| ⏩ `NO_TESTS` | `tss_report` | Luis Fernandez |
| ✅ `PASS` | `website_currency_convertion` | Luis Fernandez |
| ⏩ `NO_TESTS` | `website_quotation` | Luis Fernandez |
| ⏩ `NO_TESTS` | `website_stock_availability` | Luis Fernandez |
| ⏩ `NO_TESTS` | `website_store_pickup` | Luis Fernandez |

</details>

---

*Generado automáticamente por `run_tests.sh` · Odoo Pro v17 · 21/05/2026 10:52:33*