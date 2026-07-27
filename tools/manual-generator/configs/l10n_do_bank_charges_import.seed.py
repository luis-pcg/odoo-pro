# Seed for the manual of l10n_do_bank_charges_import (Importación de Cargos
# Bancarios RD). Builds, from a CLEAN DB, a Dominican company with:
#
#   * Chart of accounts 'do' (moneda DOP) + diario de compras fiscal con
#     documentos (NCF/e-CF).
#   * Un diario de banco "Cuenta Corriente BPD" apuntando al Banco Popular
#     Dominicano (l10n_do_bank = 'bpd') con la cuenta 0000809972854 — la misma
#     cuenta del archivo de ejemplo bpd_chrgs.csv que se sube en las capturas.
#   * Un producto de servicio "Comisiones bancarias" para asignar a las líneas
#     del asistente.
#
# El proveedor (el banco) NO se siembra: el asistente lo crea automáticamente
# con su RNC al importar, y eso se documenta en el manual. Ejecutado dentro de
# `odoo shell` (`env` disponible). Termina con env.cr.commit().

company = env.ref("base.main_company")
do = env.ref("base.do")

# ── 0. Español ────────────────────────────────────────────────────────────────
es = env["res.lang"]._activate_lang("es_DO")
try:
    env["base.language.install"].create(
        {"lang_ids": [(6, 0, [es.id])], "overwrite": True}
    ).lang_install()
except Exception:
    env.cr.rollback()
env.ref("base.user_admin").lang = "es_DO"
env = env(context=dict(env.context, lang="es_DO"))

# ── 1. Compañía RD + plan contable dominicano ────────────────────────────────
company.write({"name": "Empresa Dominicana SRL", "country_id": do.id, "vat": "131793916"})
company.partner_id.lang = "es_DO"
env["account.chart.template"].try_loading("do", company=company, install_demo=False)

# ── 2. Diarios de compras fiscales (documentos NCF/e-CF) ─────────────────────
# Dos diarios fiscales para que el asistente muestre el campo "Diario de
# Compra" (solo aparece cuando hay más de uno).
purchase_journal = env["account.journal"].search(
    [("type", "=", "purchase"), ("company_id", "=", company.id)], limit=1
)
purchase_journal.write({"name": "Compras Fiscales", "l10n_latam_use_documents": True})
env["account.journal"].create(
    {
        "name": "Compras Informales",
        "code": "CINF",
        "type": "purchase",
        "company_id": company.id,
        "l10n_latam_use_documents": True,
    }
)

# ── 3. Banco Popular + diario de banco de la cuenta del archivo ──────────────
bank = env["res.bank"].search([("l10n_do_bank", "=", "bpd")], limit=1)
if not bank:
    bank = env["res.bank"].create(
        {"name": "Banco Popular Dominicano", "bic": "BPDODOSX", "l10n_do_bank": "bpd"}
    )
bank_journal = env["account.journal"].create(
    {
        "name": "Cuenta Corriente BPD",
        "type": "bank",
        "code": "BPD1",
        "company_id": company.id,
    }
)
bank_journal.set_bank_account("0000809972854")
# journal.bank_id is related to bank_account_id.bank_id, so it must be set on
# the res.partner.bank AFTER set_bank_account (writing it at create is lost).
# Without it _is_bpd_bank() is False and the file is never recognized.
bank_journal.bank_account_id.bank_id = bank.id

# ── 4. Producto de servicio para las líneas de cargos ────────────────────────
env["product.product"].create(
    {
        "name": "Comisiones bancarias",
        "type": "service",
        "purchase_ok": True,
        "supplier_taxes_id": [(5, 0, 0)],
    }
)

env.cr.commit()
print("SEED OK")
