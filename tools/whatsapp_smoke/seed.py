from odoo import fields as F

company = env.company
connector = env['acrux.chat.connector'].create({
    'name': 'Progressa WhatsApp',
    'connector_type': 'apichat.io',
    'company_id': company.id,
    'source': '18095550101',
    'odoo_url': 'http://localhost:8092',
    'token': 'dev-token',
    'uuid': 'dev-uuid-0001',
})
stages = env['acrux.chat.conversation.stage'].search([], limit=3)
tag = env['acrux.chat.conversation.tag'].create({'name': 'Urgente'})
partner = env['res.partner'].create({'name': 'Cliente de prueba', 'phone': '+1 809 555 0102'})

convs = env['acrux.chat.conversation']
for i, (name, number, status) in enumerate([
        ('Juan Perez', '18095550102', 'new'),
        ('Maria Gomez', '18095550103', 'current'),
        ('Pedro Diaz', '18095550104', 'done')]):
    c = env['acrux.chat.conversation'].create({
        'name': name, 'number': number, 'connector_id': connector.id,
        'status': status, 'res_partner_id': partner.id if i == 0 else False,
        'agent_id': env.user.id if status in ('current', 'done') else False,
        'tag_ids': [(4, tag.id)] if i == 0 else False,
        'stage_id': stages[i % len(stages)].id if stages else False,
    })
    convs |= c
    for j, (text, from_me) in enumerate([('Hola, buenas', False), ('Buenas, en que puedo ayudar?', True),
                                         ('Quiero cotizar', False)]):
        env['acrux.chat.message'].create({
            'contact_id': c.id, 'text': text, 'from_me': from_me,
            'ttype': 'text', 'date_message': F.Datetime.now(),
        })

env['acrux.chat.default.answer'].create({'name': 'Saludo', 'text': 'Hola, gracias por escribir.'})
env.cr.commit()
print('SEED OK  connector=%s  conversaciones=%s  mensajes=%s  etapas=%s' % (
    connector.id, len(convs), env['acrux.chat.message'].search_count([]),
    env['acrux.chat.conversation.stage'].search_count([])))
print('reglas de seguimiento del connector: %s' % len(connector.message_followup_rule_ids))
