import datetime

MODULES = ['whatsapp_connector', 'whatsapp_connector_chatter', 'whatsapp_connector_crm',
           'whatsapp_connector_sale', 'whatsapp_connector_template_base',
           'whatsapp_connector_send_account', 'whatsapp_connector_send_crm',
           'whatsapp_connector_send_project', 'whatsapp_connector_send_purchase',
           'whatsapp_connector_send_sale', 'whatsapp_connector_send_stock']
NS = {'uid': env.uid, 'active_id': 1, 'active_ids': [1], 'active_model': 'res.partner',
      'context_today': lambda: datetime.date.today(), 'datetime': datetime,
      'allowed_company_ids': env.companies.ids}

# every menu this user actually sees, exactly as the web client builds the tree
menus = env['ir.ui.menu'].load_web_menus(False)
own = {}
for d in env['ir.model.data'].sudo().search([('module', 'in', MODULES), ('model', '=', 'ir.ui.menu')]):
    own[d.res_id] = f'{d.module}.{d.name}'

visible = [(mid, own[mid]) for mid in menus if isinstance(mid, int) and mid in own]
opened, fails = 0, []
print('menus de estos modulos visibles para el usuario: %s de %s' % (len(visible), len(own)))

for mid, ref in visible:
    entry = menus[mid]
    xmlid = entry.get('actionModel') and f"{entry['actionModel']},{entry['actionID']}"
    if not entry.get('actionID'):
        continue
    try:
        # this is the call the web client makes when you click a menu
        action = env['ir.actions.actions'].sudo().browse(entry['actionID']).read(['type'])[0]
        atype = action['type']
        if atype != 'ir.actions.act_window':
            opened += 1
            continue
        act = env['ir.actions.act_window'].sudo().browse(entry['actionID'])
        ctx = eval(act.context, dict(NS)) if act.context else {}
        model = env[act.res_model].with_context(**ctx)
        modes = [m for m in (act.view_mode or '').split(',') if m]
        model.get_views([(False, m) for m in modes] + [(False, 'search')])
        domain = eval(act.domain, dict(NS)) if act.domain else []
        model.web_search_read(domain, {'display_name': {}}, limit=5)
        for mode in modes:
            if mode in ('graph', 'pivot'):
                model.read_group(domain, [], [])
        opened += 1
    except Exception as e:
        fails.append((ref, f'{type(e).__name__}: {e}'.split('\n')[0][:160]))

print('===== CLICS =====')
print('  menus abiertos : %s' % opened)
print('  FALLOS         : %s' % len(fails))
for ref, msg in fails:
    print(f'  {ref}\n      {msg}')
