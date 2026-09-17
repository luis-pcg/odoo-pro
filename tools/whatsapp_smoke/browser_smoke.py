import sys, json, time
from playwright.sync_api import sync_playwright

BASE = 'http://localhost:8099'
SHOTS = '/tmp/shots'
errors, console = [], []


def hook(page):
    page.on('console', lambda m: console.append((m.type, m.text)) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append(str(e)))


def check(page, label):
    bad = [t for t in console if 'favicon' not in t[1].lower()]
    status = 'OK ' if not errors and not bad else 'FALLO'
    print(f'  [{status}] {label}')
    for e in errors:
        print(f'        pageerror: {e[:200]}')
    for _t, t in bad:
        print(f'        console:   {t[:200]}')
    ok = not errors and not bad
    errors.clear()
    console.clear()
    return ok


with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox'])
    page = browser.new_page(viewport={'width': 1600, 'height': 950})
    hook(page)
    results = []

    page.goto(f'{BASE}/web/login', wait_until='domcontentloaded')
    page.fill('input[name="login"]', 'admin')
    page.fill('input[name="password"]', 'admin')
    page.click('button[type="submit"]')
    page.wait_for_selector('.o_main_navbar, .o_home_menu', timeout=30000)
    page.wait_for_timeout(1500)
    results.append(check(page, 'login'))

    # the ChatRoom client action, the part the ORM cannot test
    page.goto(f'{BASE}/odoo/action-whatsapp_connector.acrux_live_chat_action', wait_until='domcontentloaded')
    page.wait_for_timeout(3500)
    page.screenshot(path=f'{SHOTS}/chatroom.png')
    results.append(check(page, 'ChatRoom (client action OWL)'))
    body = page.inner_text('body')[:400].replace('\n', ' / ')
    print(f'        pantalla: {body[:200]}')

    # the regular back-office screens
    for label, xmlid, extra in [
        ('Conversaciones', 'whatsapp_connector.view_whatsapp_connector_conversation_action', True),
        ('Connectors', 'whatsapp_connector.whatsapp_connector_connector_action', True),
        ('Mensajes', 'whatsapp_connector.view_whatsapp_connector_message_action', True),
        ('Etapas', 'whatsapp_connector.view_whatsapp_conversation_stage_action', False),
        ('Reglas de seguimiento', 'whatsapp_connector.view_acrux_chat_connector_followup_rule_action', True),
        ('Respuestas por defecto', 'whatsapp_connector.view_whatsapp_connector_default_answer_action', True),
        ('Plantillas WABA', 'whatsapp_connector.view_whatsapp_template_waba_action', False),
        ('Config IA', 'whatsapp_connector.view_whatsapp_connector_ai_config_action', False),
        ('Cola de trabajo', 'whatsapp_connector.view_acrux_chat_work_queue_action', False),
        ('Informe: tiempo de respuesta', 'whatsapp_connector.view_agent_answer_time_report_action', False),
        ('Informe: conversaciones', 'whatsapp_connector.view_conversation_init_report_action', False),
        ('Informe: ventas por mes', 'whatsapp_connector_sale.act_sales_by_month_graph', False),
    ]:
        page.goto(f'{BASE}/odoo/action-{xmlid}', wait_until='domcontentloaded')
        page.wait_for_timeout(1800)
        ok = check(page, label)
        if extra and ok:
            # open the first row's form view too
            row = page.query_selector('.o_data_row .o_data_cell, .o_kanban_record')
            if row:
                row.click()
                page.wait_for_timeout(1600)
                ok = check(page, f'{label} -> formulario')
        results.append(ok)
    page.screenshot(path=f'{SHOTS}/last.png')
    browser.close()

print('\nRESULTADO: %s/%s pantallas sin errores' % (sum(results), len(results)))
