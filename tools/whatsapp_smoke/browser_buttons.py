from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8099'
NOISE = ('favicon', 'beforeunload')   # chromium noise, not the page's doing
errors, console, results = [], [], []


def check(label, extra=''):
    bad = [t for t in console if not any(n in t[1].lower() for n in NOISE)]
    ok = not errors and not bad
    print(f'  [{"OK " if ok else "FALLO"}] {label}{extra}')
    for e in errors:
        print(f'        pageerror: {e[:200]}')
    for _t, t in bad:
        print(f'        console:   {t[:200]}')
    errors.clear(); console.clear(); results.append(ok)
    return ok


with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1600, 'height': 950})
    page.on('console', lambda m: console.append((m.type, m.text)) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.on('dialog', lambda d: d.accept())

    page.goto(f'{BASE}/web/login', wait_until='domcontentloaded')
    page.fill('input[name="login"]', 'admin'); page.fill('input[name="password"]', 'admin')
    page.click('button[type="submit"]'); page.wait_for_selector('.o_main_navbar', timeout=30000)
    console.clear(); errors.clear()

    for label, url in [('Presupuesto (send_sale)', f'{BASE}/odoo/sale.order/new'),
                       ('Factura (send_account)', f'{BASE}/odoo/action-account.action_move_out_invoice_type/new'),
                       ('Compra (send_purchase)', f'{BASE}/odoo/purchase.order/new'),
                       ('Transferencia (send_stock)', f'{BASE}/odoo/action-stock.action_picking_tree_all/new'),
                       ('Lead (send_crm)', f'{BASE}/odoo/action-crm.crm_lead_all_leads/new'),
                       ('Tarea (send_project)', f'{BASE}/odoo/action-project.action_view_all_task/new')]:
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_timeout(2500)
        btn = page.query_selector('button.oe_stat_button:has(.fa-whatsapp), button:has(.fa-whatsapp)')
        check(label, f'   boton WhatsApp presente: {bool(btn)}')

    # the send wizard itself, opened from a sale order button
    page.goto(f'{BASE}/odoo/action-whatsapp_connector.acrux_chat_message_wizard_action', wait_until='domcontentloaded')
    page.wait_for_timeout(2500)
    page.screenshot(path='/tmp/shots/wizard.png')
    check('Asistente de envio de mensaje')
    browser.close()

print('\nRESULTADO: %s/%s sin errores' % (sum(results), len(results)))
