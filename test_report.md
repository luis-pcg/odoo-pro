# 🧪 Odoo Pro v17 — Test Report

> **Generado:** 24/07/2026 00:24:15 &nbsp;|&nbsp; **Instalación:** 1m 43s &nbsp;|&nbsp; **Tests:** 4s

---

## 📊 Resumen Ejecutivo

| KPI | Valor | Detalle |
|-----|:-----:|---------|
| **Módulos descubiertos** | 174 | 173 instalables · 1 pendientes migración |
| **Módulos instalados** | 60 / 173 | 1 fallaron · 0 incompatibles |
| **Módulos con tests** | 52 / 1 | 52 pasaron · 0 fallaron |
| **Tests individuales** | 432 | 0 assert · 0 excepciones |
| **Tasa de éxito (módulos)** | 100% | `████████████████████` 100% |
| **Tasa de éxito (tests)** | 100% | `████████████████████` 100% |

### Estado por categoría

| Estado | Módulos | Descripción |
|--------|:-------:|-------------|
| ✅ Pasaron | **52** | módulos con todos los tests en verde |
| ❌ Fallaron | **0** | módulos con fallos o errores |
| ⚠️  Con warnings | **2** | módulos con advertencias |
| ⏩ Sin tests | **172** | módulos sin directorio tests/ |
| 🔒 No instalables | **1** | installable=False — pendientes migración |
| 🚫 Incompatibles | **0** | versión incompatible con v17 |
| 🔴 Error install | **1** | fallaron durante la instalación |

---

## ✅ Tests Pasaron &nbsp; `52 módulos`

| Módulo | Tests | Tiempo | Autor | Estado |
|--------|:-----:|:------:|-------|:------:|
| `acap_bank_statement_import` | 5 | 5.69s | Luis Fernandez | ✅ |
| `account_bank_charge_import_bhd` | 4 | 7.56s | Luis Fernandez | ✅ |
| `account_bank_charge_import_bpd` ⚠️ | 7 | 5.88s | luisfernandez | ✅⚠️ |
| `account_invoice_rate` | 4 | 2.43s | Luis Fernandez | ✅ |
| `account_partner_fields` | 3 | 0.21s | Fernando R. Figuereo Roa | ✅ |
| `account_payment_compensation` | 28 | 7.17s | Fernando R. Figuereo Roa | ✅ |
| `account_payment_compensation_pos` | 19 | 4.11s | Fernando R. Figuereo Roa | ✅ |
| `account_reconcile_payment` | 3 | 5.61s | Fernando R. Figuereo Roa | ✅ |
| `apap_bank_statement_import` | 5 | 0.84s | Luis Fernandez | ✅ |
| `bdi_bank_statement_import` | 5 | 0.23s | Luis Fernandez | ✅ |
| `bdr_bank_statement_import` | 4 | 3.08s | Luis Fernandez | ✅ |
| `bhd_bank_statement_import` | 4 | 9.78s | Luis Fernandez | ✅ |
| `bhd_panama_bank_statement_import` | 4 | 0.75s | Fernando R. Figuereo Roa | ✅ |
| `blh_bank_statement_import` | 4 | 2.82s | Luis Fernandez | ✅ |
| `bnc_bank_statement_import` | 4 | 0.82s | Luis Fernandez | ✅ |
| `bpd_bank_statement_import` | 4 | 3.23s | Luis Fernandez | ✅ |
| `bpm_bank_statement_import` | 4 | 2.82s | Fernando R. Figuereo Roa | ✅ |
| `bsc_bank_statement_import` | 4 | 4.53s | Luis Fernandez | ✅ |
| `delivery_buenvio` | 5 | 1.44s | Fernando R. Figuereo Roa | ✅ |
| `hms_account` | 3 | 2.7s | Luis Fernandez | ✅ |
| `hms_sales` | 4 | 0.54s | Fernando R. Figuereo Roa | ✅ |
| `jmmb_bank_statement_import` | 4 | 3.39s | Fernando R. Figuereo Roa | ✅ |
| `l10n_do_currency_update` | 6 | 1.99s | Fernando R. Figuereo Roa | ✅ |
| `l10n_do_ecf_invoicing` | 19 | 15.39s | Erick Cuesto | ✅ |
| `l10n_do_ecf_reception` | 9 | 4.61s | Fernando R. Figuereo Roa | ✅ |
| `l10n_do_hr_expense` | 35 | 4.89s | Fernando R. Figuereo Roa | ✅ |
| `l10n_do_it1_report` | 4 | 4.53s | — | ✅ |
| `l10n_do_ncf_validation` | 5 | 5.44s | Fernando R. Figuereo Roa | ✅ |
| `l10n_do_payroll_bhd_file` | 9 | 0.51s | lfernandez | ✅ |
| `l10n_do_payroll_bpd_file` | 13 | 0.68s | luisfernandez | ✅ |
| `l10n_do_payroll_brrd_file` | 10 | 0.51s | lfernandez | ✅ |
| `l10n_do_payroll_file_base` | 8 | 0.36s | Luis Fernandez | ✅ |
| `l10n_do_withholding_certification` | 5 | 2.91s | Fernando R. Figuereo Roa | ✅ |
| `odoo_cheque_features` | 3 | 0.26s | — | ✅ |
| `payment_azul` ⚠️ | 43 | 1.08s | lfernandez | ✅⚠️ |
| `payment_azul_webservices` | 19 | 0.77s | luisfernandez | ✅ |
| `payment_bhd` | 26 | 0.92s | Erick Cuesto | ✅ |
| `product_category_inter_company` | 3 | 1.31s | Luis Fernandez | ✅ |
| `product_category_multi_company` | 3 | 2.51s | Luis Fernandez | ✅ |
| `purchase_order_rate` | 4 | 2.75s | Fernando R. Figuereo Roa | ✅ |
| `purchase_picking_default` | 7 | 0.95s | Fernando R. Figuereo Roa | ✅ |
| `purchase_request_features` | 3 | 0.25s | Luis Fernandez | ✅ |
| `res_partner_phone_search` | 3 | 0.25s | Luis Fernandez | ✅ |
| `sale_order_glasses_description` | 3 | 0.43s | Fernando R. Figuereo Roa | ✅ |
| `sale_order_rate` | 3 | 2.43s | Fernando R. Figuereo Roa | ✅ |
| `sale_order_time_total` | 4 | 1.22s | Luis Fernandez | ✅ |
| `sale_stock_features` | 4 | 0.49s | Luis Fernandez | ✅ |
| `sales_bavel` | 19 | 1.14s | Fernando R. Figuereo Roa | ✅ |
| `scotiabank_statement_import` | 4 | 5.14s | Fernando R. Figuereo Roa | ✅ |
| `serial_number_report` | 11 | 0.72s | Fernando R. Figuereo Roa | ✅ |
| `stock_landed_costs_features` | 3 | 3.28s | lfernandez | ✅ |
| `website_currency_convertion` | 13 | 0.84s | Luis Fernandez | ✅ |

## ❌ Tests Fallaron &nbsp; `0 módulos`

> 🎉 **¡Todos los módulos con tests pasaron!**

---

## 🔴 Fallos de Instalación &nbsp; `1 módulos`

| Módulo | Causa del fallo |
|--------|-----------------|
| `l10n_do_accounting` | Failed to load registry  Traceback (most recent call last):   File "/usr/lib/python3/dist-packages/odoo/modules/registry.py", line 110, in new     odoo.modules.load_modules(registry, force_demo, status, update_module)   File "/usr/lib/python3/dist-pa |

## 🚫 Versión Incompatible &nbsp; `0 módulos`

> ✅ Ningún módulo con versión incompatible.

## 🔒 Pendientes de Migración a v17 &nbsp; `1 módulos`

> Módulos con `installable = False`. Excluidos del proceso de instalación y tests.

| Módulo | Módulo | Módulo |
|------|------|------|
| `sale_pos_backend_discount_display_amount` |  |  |

## ⚠️  Warnings en Tests &nbsp; `2 módulos`

<details><summary><code>account_bank_charge_import_bpd</code> — 6 warnings</summary>

```text
BPD csv line 10 skipped: no NCF found (got '').
BPD csv line 11 skipped: no NCF found (got 'RD$').
BPD csv line 10 skipped: no NCF found (got '').
BPD csv line 11 skipped: no NCF found (got 'RD$').
BPD csv line 9 skipped: no NCF found (got '').
… (1 más)
```
</details>

<details><summary><code>payment_azul</code> — 1 warnings</summary>

```text
Azul: DataVaultToken has unexpected format, skipping tokenization for transaction Test Transaction
```
</details>

## ⏩ Sin Directorio de Tests &nbsp; `172 módulos`

| Módulo | Módulo | Módulo |
|------|------|------|
| `acap_bank_statement_import` | `account_accountant_cheque` | `account_auto_transfer_features` |
| `account_bank_charge_import_base` | `account_bank_charge_import_bhd` | `account_bank_charge_import_bpd` |
| `account_bank_statement_import_csv_patch` | `account_date_filters` | `account_default_journals` |
| `account_financial_risk_features` | `account_followup_extra_features` | `account_followup_multi_partner` |
| `account_invoice_rate` | `account_invoice_read_notification` | `account_lock_fiscal_date` |
| `account_move_route` | `account_multi_journal_payment` | `account_multi_journal_payment_authorization_code` |
| `account_partner_fields` | `account_payment_advance_payment` | `account_payment_authorization_code` |
| `account_payment_card_bin` | `account_payment_cash_custom_workflow` | `account_payment_compensation` |
| `account_payment_compensation_news` | `account_payment_compensation_pos` | `account_payment_promotion_discount` |
| `account_payment_reconcile_features` | `account_reconcile_payment` | `apap_bank_statement_import` |
| `auto_attribute_value` | `auto_backup_sh` | `bdi_bank_statement_import` |
| `bdr_bank_statement_import` | `bhd_bank_statement_import` | `bhd_panama_bank_statement_import` |
| `blh_bank_statement_import` | `bnc_bank_statement_import` | `bpd_bank_statement_import` |
| `bpm_bank_statement_import` | `bsc_bank_statement_import` | `crm_helpdesk_custom` |
| `delivery_buenvio` | `dgii_reports` | `fleet_account_asset` |
| `fleet_industry_fsm` | `fleet_product_management` | `fleet_product_rules` |
| `fleet_product_rules_renting` | `helpdesk_sale_custom` | `helpdesk_team_restrict_visibility` |
| `helpdesk_ticket_signature` | `hms_account` | `hms_partner` |
| `hms_sale_pos_backend` | `hms_sales` | `hr_payroll_import_inputs` |
| `jmmb_bank_statement_import` | `l10n_do_account_batch_payment_base` | `l10n_do_account_batch_payment_bdr` |
| `l10n_do_account_batch_payment_bhd` | `l10n_do_account_batch_payment_bpd` | `l10n_do_account_batch_payment_ee` |
| `l10n_do_bank_charges_import` | `l10n_do_banks` | `l10n_do_credit_note` |
| `l10n_do_credit_note_ecf` | `l10n_do_currency_update` | `l10n_do_document_pools` |
| `l10n_do_ecf_invoicing` | `l10n_do_ecf_reception` | `l10n_do_ecf_reception_workflow` |
| `l10n_do_ecf_status_check` | `l10n_do_ecommerce` | `l10n_do_hr` |
| `l10n_do_hr_bonus_legal` | `l10n_do_hr_course` | `l10n_do_hr_expense` |
| `l10n_do_hr_fleet` | `l10n_do_hr_maintenance` | `l10n_do_hr_news` |
| `l10n_do_hr_news_accounts_receivable` | `l10n_do_hr_news_attendance` | `l10n_do_hr_payroll` |
| `l10n_do_hr_payroll_import_inputs` | `l10n_do_hr_payroll_news` | `l10n_do_hr_payroll_news_attendance` |
| `l10n_do_hr_recruitment` | `l10n_do_hr_recurrent_news` | `l10n_do_ncf_validation` |
| `l10n_do_payroll_bhd_file` | `l10n_do_payroll_bpd_file` | `l10n_do_payroll_brrd_file` |
| `l10n_do_payroll_file_base` | `l10n_do_pos` | `l10n_do_pos_features` |
| `l10n_do_purchase` | `l10n_do_rnc_validation` | `l10n_do_sale` |
| `l10n_do_sale_pos_backend` | `l10n_do_sale_pos_backend_reconcile_payment` | `l10n_do_sign_to_xml` |
| `l10n_do_withholding_certification` | `payment_azul` | `payment_azul_webservices` |
| `payment_bhd` | `payment_salesperson` | `payroll_dynamic_xls_report` |
| `pos_azul` | `pos_cardnet` | `pos_hr_minimal_rights` |
| `product_category_inter_company` | `product_category_multi_company` | `product_fields_tracking` |
| `product_foreign_cost_price` | `product_label_layout` | `product_part_number` |
| `product_price_history` | `product_pricelist_user_restriction` | `product_product_price_widget` |
| `product_segment` | `product_stock_qty_date_widgets` | `purchase_financial_risk` |
| `purchase_financial_risk_features` | `purchase_foreign_cost_update` | `purchase_order_rate` |
| `purchase_partner_fields` | `purchase_picking_default` | `purchase_request_currency` |
| `purchase_request_features` | `qztray_base_features` | `recurring_sale_order_app` |
| `recurring_sale_order_app_features` | `repair_no_negative_allow` | `repair_services` |
| `res_partner_phone_search` | `sale_crm_features` | `sale_financial_risk_features` |
| `sale_mr_inherit_modify` | `sale_order_glasses_description` | `sale_order_rate` |
| `sale_order_time_total` | `sale_order_with_other_locations` | `sale_partner_fields` |
| `sale_pos_backend` | `sale_pos_backend_card_bin_promotion` | `sale_pos_backend_card_bin_promotion_payments` |
| `sale_pos_backend_journal_control` | `sale_pos_backend_multi_journal_payment` | `sale_pos_backend_part_number` |
| `sale_pos_session_link` | `sale_product_generic_readonly` | `sale_stock_features` |
| `sale_stock_product_price_widget` | `sale_stock_qty_date_widgets` | `sale_stock_restriction` |
| `sale_stock_serial` | `sale_subscription_draft_invoice` | `sales_bavel` |
| `scotiabank_statement_import` | `serial_number_report` | `stock_account_fields_tracking` |
| `stock_inventory_forecasted_report` | `stock_landed_costs_features` | `stock_landed_costs_file` |
| `stock_picking_invoice_link_extra` | `stock_warehouse_orderpoint_uom` | `tss_report` |
| `website_currency_convertion` | `website_quotation` | `website_stock_availability` |
| `website_store_pickup` |  |  |

---

## 📦 Inventario Completo &nbsp; `174 módulos`

<details>
<summary>Expandir inventario completo</summary>

| Estado | Módulo | Autor |
|:------:|--------|-------|
| ✅ `PASS` | `acap_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_accountant_cheque` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_auto_transfer_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_bank_charge_import_base` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `account_bank_charge_import_bhd` | Luis Fernandez |
| ✅⚠️ `PASS+W` | `account_bank_charge_import_bpd` | luisfernandez |
| ⚠️  `NOT_LOADED` | `account_bank_statement_import_csv_patch` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_date_filters` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_default_journals` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_financial_risk_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_followup_extra_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_followup_multi_partner` | Luis Fernandez |
| ✅ `PASS` | `account_invoice_rate` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_invoice_read_notification` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_lock_fiscal_date` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_move_route` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_multi_journal_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_multi_journal_payment_authorization_code` | Luis Fernandez |
| ✅ `PASS` | `account_partner_fields` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `account_payment_advance_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_payment_authorization_code` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_card_bin` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_cash_custom_workflow` | Luis Fernandez |
| ✅ `PASS` | `account_payment_compensation` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `account_payment_compensation_news` | Luis Fernandez |
| ✅ `PASS` | `account_payment_compensation_pos` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `account_payment_promotion_discount` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_reconcile_features` | Luis Fernandez |
| ✅ `PASS` | `account_reconcile_payment` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `apap_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `auto_attribute_value` | Luis Fernandez |
| ⏩ `NO_TESTS` | `auto_backup_sh` | Luis Fernandez |
| ✅ `PASS` | `bdi_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bdr_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bhd_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bhd_panama_bank_statement_import` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `blh_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bnc_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bpd_bank_statement_import` | Luis Fernandez |
| ✅ `PASS` | `bpm_bank_statement_import` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `bsc_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `crm_helpdesk_custom` | Luis Fernandez |
| ✅ `PASS` | `delivery_buenvio` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `dgii_reports` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `fleet_account_asset` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_industry_fsm` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `fleet_product_management` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_product_rules` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_product_rules_renting` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `helpdesk_sale_custom` | Fernando Figuereo |
| ⏩ `NO_TESTS` | `helpdesk_team_restrict_visibility` | lfernandez |
| ⏩ `NO_TESTS` | `helpdesk_ticket_signature` | Luis Fernandez |
| ✅ `PASS` | `hms_account` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hms_partner` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `hms_sale_pos_backend` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `hms_sales` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `hr_payroll_import_inputs` | Luis Fernandez |
| ✅ `PASS` | `jmmb_bank_statement_import` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_base` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bdr` | José López |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bhd` | José López |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bpd` | José López |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_ee` | lfernandez |
| 🔴 `INST_FAIL` | `l10n_do_accounting` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_bank_charges_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_banks` | Fernando Figuereo |
| ⚠️  `NOT_LOADED` | `l10n_do_credit_note` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `l10n_do_credit_note_ecf` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_currency_update` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `l10n_do_document_pools` | luisfernandez |
| ✅ `PASS` | `l10n_do_ecf_invoicing` | Erick Cuesto |
| ✅ `PASS` | `l10n_do_ecf_reception` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `l10n_do_ecf_reception_workflow` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_ecf_status_check` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_ecommerce` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_bonus_legal` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_course` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_hr_expense` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `l10n_do_hr_fleet` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_maintenance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_news` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_news_accounts_receivable` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `l10n_do_hr_news_attendance` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll` | luisfernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_import_inputs` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news_attendance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_recruitment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_recurrent_news` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_ncf_validation` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `l10n_do_payroll_bhd_file` | lfernandez |
| ✅ `PASS` | `l10n_do_payroll_bpd_file` | luisfernandez |
| ✅ `PASS` | `l10n_do_payroll_brrd_file` | lfernandez |
| ✅ `PASS` | `l10n_do_payroll_file_base` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_pos` | erick-pcg |
| ⚠️  `NOT_LOADED` | `l10n_do_pos_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_purchase` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_rnc_validation` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sale` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sale_pos_backend` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sale_pos_backend_reconcile_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sign_to_xml` | Luis Fernandez |
| ✅ `PASS` | `l10n_do_withholding_certification` | Fernando R. Figuereo Roa |
| ✅⚠️ `PASS+W` | `payment_azul` | lfernandez |
| ✅ `PASS` | `payment_azul_webservices` | luisfernandez |
| ✅ `PASS` | `payment_bhd` | Erick Cuesto |
| ⏩ `NO_TESTS` | `payment_salesperson` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `payroll_dynamic_xls_report` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `pos_azul` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `pos_cardnet` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `pos_hr_minimal_rights` | Erick Cuesto |
| ✅ `PASS` | `product_category_inter_company` | Luis Fernandez |
| ✅ `PASS` | `product_category_multi_company` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_fields_tracking` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_foreign_cost_price` | Erick Cuesto |
| ⏩ `NO_TESTS` | `product_label_layout` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_part_number` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_price_history` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `product_pricelist_user_restriction` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `product_product_price_widget` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `product_segment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `product_stock_qty_date_widgets` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_financial_risk` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `purchase_financial_risk_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `purchase_foreign_cost_update` | Luis Fernandez |
| ✅ `PASS` | `purchase_order_rate` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `purchase_partner_fields` | Luis Fernandez |
| ✅ `PASS` | `purchase_picking_default` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `purchase_request_currency` | Luis Fernandez |
| ✅ `PASS` | `purchase_request_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `qztray_base_features` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `recurring_sale_order_app` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `recurring_sale_order_app_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `repair_no_negative_allow` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `repair_services` | Luis Fernandez |
| ✅ `PASS` | `res_partner_phone_search` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_crm_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_financial_risk_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_mr_inherit_modify` | Erick Cuesto |
| ✅ `PASS` | `sale_order_glasses_description` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `sale_order_rate` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `sale_order_time_total` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_order_with_other_locations` | luisfernandez |
| ⚠️  `NOT_LOADED` | `sale_partner_fields` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_card_bin_promotion` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_card_bin_promotion_payments` | Luis Fernandez |
| 🔒 `NO_INST` | `sale_pos_backend_discount_display_amount` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_journal_control` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_multi_journal_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_part_number` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_session_link` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_product_generic_readonly` | Luis Fernandez |
| ✅ `PASS` | `sale_stock_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_product_price_widget` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_qty_date_widgets` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `sale_stock_restriction` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_serial` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `sale_subscription_draft_invoice` | Luis Fernandez |
| ✅ `PASS` | `sales_bavel` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `scotiabank_statement_import` | Fernando R. Figuereo Roa |
| ✅ `PASS` | `serial_number_report` | Fernando R. Figuereo Roa |
| ⏩ `NO_TESTS` | `stock_account_fields_tracking` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `stock_inventory_forecasted_report` | Luis Fernandez |
| ✅ `PASS` | `stock_landed_costs_features` | lfernandez |
| ⚠️  `NOT_LOADED` | `stock_landed_costs_file` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `stock_picking_invoice_link_extra` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_warehouse_orderpoint_uom` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `tss_report` | Luis Fernandez |
| ✅ `PASS` | `website_currency_convertion` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_quotation` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_stock_availability` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_store_pickup` | Luis Fernandez |

</details>

---

*Generado automáticamente por `run_tests.sh` · Odoo Pro v17 · 24/07/2026 00:24:15*