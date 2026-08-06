# Seed para replicar el bug "UncaughtPromiseError > TypeError (reading 'message')"
# al guardar un pago de transferencia interna (account.payment) con
# simplify_access_management instalado.
# Crea: plan contable genérico (diarios Bank y Cash), un usuario demo y un
# perfil de acceso del módulo.

# Plan contable genérico → crea los diarios Bank (BNK1) y Cash (CSH1) y el
# transfer account de la compañía, necesarios para transferencias internas.
env['account.chart.template'].try_loading('generic_coa', company=env.company, install_demo=False)

bank = env['account.journal'].search([('type', '=', 'bank')], limit=1)
cash = env['account.journal'].search([('type', '=', 'cash')], limit=1)
assert bank and cash, 'Faltan diarios bank/cash tras cargar el plan contable'

demo_user = env['res.users'].create({
    'name': 'Vendedor Demo',
    'login': 'vendedor_demo',
    'password': 'vendedor_demo',
    'groups_id': [(6, 0, [env.ref('base.group_user').id])],
})

# El create() de access.management llama request.registry.clear_cache() y en
# `odoo shell` no existe request (LocalProxy desligado): se sustituye el global
# del módulo por un objeto simple mientras dura el create.
import odoo.addons.simplify_access_management.models.access_management as am_mod


class _FakeRequest:
    pass


_fake = _FakeRequest()
_fake.registry = env.registry
_fake.env = env
_orig_request = am_mod.request
am_mod.request = _fake
try:
    env['access.management'].create({
        'name': 'Perfil Almacén — demo',
        'user_ids': [(6, 0, demo_user.ids)],
    })
finally:
    am_mod.request = _orig_request

env.cr.commit()
print('SEED OK', bank.name, '/', cash.name)
