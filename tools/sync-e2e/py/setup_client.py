"""Configure sync_client as a sync client and mint its inbound key.

Run through `odoo shell`. Prints `KEY=<secret>` on stdout for the caller to
capture; the master needs it to authenticate its push calls.
"""

import secrets

from odoo.addons.base.models.res_users import KEY_CRYPT_CONTEXT

key = secrets.token_urlsafe(24)
params = env["ir.config_parameter"].sudo()  # noqa: F821 - provided by odoo shell
params.set_param("l10n_do_payroll_sync.role", "client")
params.set_param("l10n_do_payroll_sync.inbound_api_key_hash", KEY_CRYPT_CONTEXT.hash(key))
params.set_param("l10n_do_payroll_sync.rate_limit_per_minute", 1000)
params.set_param("l10n_do_payroll_sync.target_company_id", str(env.company.id))  # noqa: F821
env.cr.commit()  # noqa: F821

print("KEY=" + key)
