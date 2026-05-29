# 🧪 Odoo Pro v17 — Test Report

> **Generado:** 29/05/2026 09:53:43 &nbsp;|&nbsp; **Instalación:** 0s &nbsp;|&nbsp; **Tests:** 1m 43s

---

## 📊 Resumen Ejecutivo

| KPI | Valor | Detalle |
|-----|:-----:|---------|
| **Módulos descubiertos** | 173 | 172 instalables · 1 pendientes migración |
| **Módulos instalados** | 59 / 172 | 1 fallaron · 0 incompatibles |
| **Módulos con tests** | 0 / 53 | 0 pasaron · 0 fallaron |
| **Tests individuales** | 0 | 0 assert · 0 excepciones |
| **Tasa de éxito (módulos)** | 0% | `────────────────────` 0% |
| **Tasa de éxito (tests)** | 0% | `────────────────────` 0% |

### Estado por categoría

| Estado | Módulos | Descripción |
|--------|:-------:|-------------|
| ✅ Pasaron | **0** | módulos con todos los tests en verde |
| ❌ Fallaron | **0** | módulos con fallos o errores |
| ⚠️  Con warnings | **0** | módulos con advertencias |
| ⏩ Sin tests | **119** | módulos sin directorio tests/ |
| 🔒 No instalables | **1** | installable=False — pendientes migración |
| 🚫 Incompatibles | **0** | versión incompatible con v17 |
| 🔴 Error install | **1** | fallaron durante la instalación |

---

## ✅ Tests Pasaron &nbsp; `0 módulos`

> ⚠️  Ningún módulo pasó todos los tests.

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
| ⚠️  `NOT_LOADED` | `acap_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_accountant_cheque` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_auto_transfer_features` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_bank_charge_import_base` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_bank_charge_import_bhd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_bank_charge_import_bpd` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_bank_statement_import_csv_patch` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_date_filters` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_default_journals` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_financial_risk_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_followup_extra_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_followup_multi_partner` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_invoice_rate` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_invoice_read_notification` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_lock_fiscal_date` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_move_route` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_multi_journal_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_multi_journal_payment_authorization_code` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_partner_fields` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_advance_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_payment_authorization_code` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_card_bin` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_cash_custom_workflow` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_compensation` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `account_payment_compensation_news` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_compensation_pos` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `account_payment_promotion_discount` | Luis Fernandez |
| ⏩ `NO_TESTS` | `account_payment_reconcile_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `account_reconcile_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `apap_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `auto_attribute_value` | Luis Fernandez |
| ⏩ `NO_TESTS` | `auto_backup_sh` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `bdi_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `bdr_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `bhd_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `bhd_panama_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `blh_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `bnc_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `bpd_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `bpm_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `bsc_bank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `crm_helpdesk_custom` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `delivery_buenvio` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `dgii_reports` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `fleet_account_asset` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_industry_fsm` | Luis Fernandez |
| ⏩ `NO_TESTS` | `fleet_product_management` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_product_rules` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `fleet_product_rules_renting` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `helpdesk_sale_custom` | Luis Fernandez |
| ⏩ `NO_TESTS` | `helpdesk_ticket_signature` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `hms_account` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hms_partner` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `hms_sale_pos_backend` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hms_sales` | Luis Fernandez |
| ⏩ `NO_TESTS` | `hr_payroll_import_inputs` | Luis Fernandez |
| ⏩ `NO_TESTS` | `jmmb_bank_statement_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_base` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bdr` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bhd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_bpd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_account_batch_payment_ee` | Luis Fernandez |
| 🔴 `INST_FAIL` | `l10n_do_accounting` | DanielAPereyraB |
| ⚠️  `NOT_LOADED` | `l10n_do_bank_charges_import` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_banks` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_credit_note` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_credit_note_ecf` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_currency_update` | Fernando R. Figuereo Roa |
| ⚠️  `NOT_LOADED` | `l10n_do_document_pools` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_ecf_invoicing` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_ecf_reception` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_ecf_reception_workflow` | Daniel Alexander Pereyra Beltran |
| ⚠️  `NOT_LOADED` | `l10n_do_ecf_status_check` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_ecommerce` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_bonus_legal` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_course` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_expense` | Erick Cuesto |
| ⏩ `NO_TESTS` | `l10n_do_hr_fleet` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_maintenance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_news` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_news_accounts_receivable` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_news_attendance` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_import_inputs` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_payroll_news_attendance` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_hr_recruitment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_hr_recurrent_news` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_ncf_validation` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_bhd_file` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_bpd_file` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_brrd_file` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_payroll_file_base` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_pos` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_pos_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_purchase` | Luis Fernandez |
| ⏩ `NO_TESTS` | `l10n_do_rnc_validation` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sale` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sale_pos_backend` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sale_pos_backend_reconcile_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_sign_to_xml` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `l10n_do_withholding_certification` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `payment_azul` | gerald-pcg |
| ⚠️  `NOT_LOADED` | `payment_azul_webservices` | Luis Fernandez |
| ⏩ `NO_TESTS` | `payment_bhd` | Luis Fernandez |
| ⏩ `NO_TESTS` | `payment_salesperson` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `payroll_dynamic_xls_report` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `pos_azul` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `pos_cardnet` | Erick Cuesto |
| ⚠️  `NOT_LOADED` | `pos_hr_minimal_rights` | Erick Cuesto |
| ⏩ `NO_TESTS` | `product_category_inter_company` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_category_multi_company` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_fields_tracking` | Luis Fernandez |
| ⏩ `NO_TESTS` | `product_foreign_cost_price` | Luis Fernandez |
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
| ⏩ `NO_TESTS` | `purchase_order_rate` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `purchase_partner_fields` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `purchase_picking_default` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `purchase_request_currency` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `purchase_request_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `qztray_base_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `recurring_sale_order_app` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `recurring_sale_order_app_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `repair_no_negative_allow` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `repair_services` | Luis Fernandez |
| ⏩ `NO_TESTS` | `res_partner_phone_search` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_crm_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_financial_risk_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_mr_inherit_modify` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_order_glasses_description` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_order_rate` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_order_time_total` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_order_with_other_locations` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_partner_fields` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_card_bin_promotion` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_card_bin_promotion_payments` | Luis Fernandez |
| 🔒 `NO_INST` | `sale_pos_backend_discount_display_amount` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_journal_control` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_multi_journal_payment` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_backend_part_number` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_pos_session_link` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_product_generic_readonly` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_product_price_widget` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_qty_date_widgets` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_restriction` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_stock_serial` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sale_subscription_draft_invoice` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `sales_bavel` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `scotiabank_statement_import` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `serial_number_report` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_account_fields_tracking` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `stock_inventory_forecasted_report` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `stock_landed_costs_features` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `stock_landed_costs_file` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `stock_picking_invoice_link_extra` | Luis Fernandez |
| ⏩ `NO_TESTS` | `stock_warehouse_orderpoint_uom` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `tss_report` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_currency_convertion` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_quotation` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_stock_availability` | Luis Fernandez |
| ⚠️  `NOT_LOADED` | `website_store_pickup` | Luis Fernandez |

</details>

---

*Generado automáticamente por `run_tests.sh` · Odoo Pro v17 · 29/05/2026 09:53:43*