from datetime import timedelta

from odoo import fields

lang = env['res.lang']._activate_lang('es_DO')
env['base.language.install'].create({'lang_ids': [(6, 0, lang.ids)]}).lang_install()
admin = env.ref('base.user_admin')
admin.write({'tour_enabled': False, 'lang': 'es_DO'})
company = env.company
if not env['account.journal'].search([('company_id', '=', company.id), ('type', '=', 'sale')], limit=1):
    env['account.chart.template'].try_loading('generic_coa', company, install_demo=False)

partner = env['res.partner'].create({'name': 'Distribuidora Caribe SRL'})
today = fields.Date.context_today(admin)
for days in (0, 1, 5, 15, 45):
    move = env['account.move'].create({
        'move_type': 'out_invoice',
        'partner_id': partner.id,
        'invoice_date': today - timedelta(days=days),
        'invoice_line_ids': [(0, 0, {'name': 'Servicio de consultoría', 'quantity': 1, 'price_unit': 1000.0 + days})],
    })
    move.action_post()
for days in (0, 1, 5):
    payment = env['account.payment'].create({
        'partner_type': 'customer',
        'payment_type': 'inbound',
        'partner_id': partner.id,
        'amount': 500.0 + days,
        'date': today - timedelta(days=days),
    })
    payment.action_post()
env.cr.commit()
