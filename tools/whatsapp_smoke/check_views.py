import datetime

MODULES = [
    'whatsapp_connector', 'whatsapp_connector_chatter', 'whatsapp_connector_crm',
    'whatsapp_connector_sale', 'whatsapp_connector_template_base',
    'whatsapp_connector_send_account', 'whatsapp_connector_send_crm',
    'whatsapp_connector_send_project', 'whatsapp_connector_send_purchase',
    'whatsapp_connector_send_sale', 'whatsapp_connector_send_stock',
]
fails, checked = [], {'view': 0, 'qweb': 0, 'action': 0, 'read': 0, 'menu': 0, 'abstract': 0}
AS = AS_LOGIN
EVAL_NS = {'uid': env.uid, 'active_id': 1, 'active_ids': [1], 'active_model': 'res.partner',
           'context_today': lambda: datetime.date.today(), 'datetime': datetime,
           'time': __import__('time'), 'allowed_company_ids': env.companies.ids}


def xmlids(model):
    data = env['ir.model.data'].sudo().search([('module', 'in', MODULES), ('model', '=', model)])
    return [(f'{d.module}.{d.name}', d.res_id) for d in data]


def fail(kind, ref, exc):
    fails.append((kind, f'{AS}|{ref}', f'{type(exc).__name__}: {exc}'.split('\n')[0][:200]))


def safe_eval_dict(src):
    try:
        return eval(src, dict(EVAL_NS)) if src else {}
    except Exception:
        return {}


# 1. every view: the arch the web client actually receives, inherits applied
for ref, rid in xmlids('ir.ui.view'):
    view = env['ir.ui.view'].sudo().browse(rid)
    if not view.exists():
        fail('view', ref, Exception('record missing'))
        continue
    if view.model and env[view.model]._abstract:
        checked['abstract'] += 1   # template for other models to inherit, never opened on its own
        continue
    if view.type == 'qweb' or not view.model:
        checked['qweb'] += 1
        try:
            view.sudo()._check_xml()
        except Exception as e:
            fail('qweb', ref, e)
        continue
    checked['view'] += 1
    try:
        env[view.model].get_view(view.id, view.type)
    except Exception as e:
        fail('view', f'{ref} [{view.model}/{view.type}]', e)

# 2. every window action: all its view modes, then an actual read of records
for ref, rid in xmlids('ir.actions.act_window'):
    act = env['ir.actions.act_window'].sudo().browse(rid)
    if not act.exists():
        fail('action', ref, Exception('record missing'))
        continue
    checked['action'] += 1
    ctx = safe_eval_dict(act.context)
    modes = [m for m in (act.view_mode or '').split(',') if m]
    model = env[act.res_model].with_context(**ctx)
    try:
        model.get_views([(False, m) for m in modes] + [(False, 'search')])
    except Exception as e:
        fail('action', f'{ref} [{act.res_model}: {act.view_mode}]', e)
        continue
    checked['read'] += 1
    try:
        domain = eval(act.domain, dict(EVAL_NS)) if act.domain else []
        model.web_search_read(domain, {'display_name': {}}, limit=5)
        for mode in modes:
            if mode in ('graph', 'pivot'):
                model.read_group(domain, [], [])
    except Exception as e:
        fail('read', f'{ref} [{act.res_model}]', e)

# 3. menus, and the tree as the web client loads it
for ref, rid in xmlids('ir.ui.menu'):
    menu = env['ir.ui.menu'].sudo().browse(rid)
    if not menu.exists():
        fail('menu', ref, Exception('record missing'))
        continue
    checked['menu'] += 1
    try:
        if menu.action:
            env[menu.action._name].browse(menu.action.id).read(['name'])
    except Exception as e:
        fail('menu', f'{ref} -> {menu.action}', e)
try:
    env['ir.ui.menu'].load_web_menus(False)
except Exception as e:
    fail('menu', 'load_web_menus', e)

# 4. server actions and reports declared by the modules
for ref, rid in xmlids('ir.actions.report'):
    rep = env['ir.actions.report'].sudo().browse(rid)
    try:
        rep.read()
        env['ir.ui.view'].sudo().search([('key', '=', rep.report_name)])._check_xml()
    except Exception as e:
        fail('report', ref, e)

print('\n===== RESUMEN =====')
for k, v in checked.items():
    print('  %-22s %s' % (k, v))
print('  %-22s %s' % ('FALLOS', len(fails)))
for kind, ref, msg in fails:
    print(f'  [{kind}] {ref}\n         {msg}')
