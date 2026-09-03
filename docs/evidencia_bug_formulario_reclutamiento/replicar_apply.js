const puppeteer = require('puppeteer-core');

const CHROME = process.env.HOME +
  '/.cache/puppeteer/chrome/mac_arm-148.0.7778.97/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const BASE = 'http://localhost:8092';
const DB = 'test_web_recruit';
const TAG = process.argv[2] || 'run';

(async () => {
  const browser = await puppeteer.launch({
    executablePath: CHROME,
    headless: true,
    args: ['--no-sandbox', '--disable-dev-shm-usage'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 1400 });
  await page.setExtraHTTPHeaders({ 'X-Odoo-Database': DB, 'Accept-Language': 'es-419,es' });

  const posts = [];
  page.on('response', (r) => {
    if (r.url().includes('/website/form/')) posts.push(`${r.status()} ${r.url()}`);
  });

  // Navegar como candidato: lista de vacantes -> vacante publicada -> postular
  await page.goto(`${BASE}/es/jobs`, { waitUntil: 'networkidle2' });
  await page.goto(`${BASE}/es/jobs/chief-technical-officer-1`, { waitUntil: 'networkidle2' });
  await page.goto(`${BASE}/es/jobs/apply/chief-technical-officer-1`, { waitUntil: 'networkidle2' });

  const fill = async (name, value) => {
    const sel = `form#hr_recruitment_form [name="${name}"]`;
    const el = await page.$(sel);
    if (!el) return `MISSING:${name}`;
    await el.click({ clickCount: 3 }).catch(() => {});
    await page.type(sel, value, { delay: 5 });
    return `ok:${name}`;
  };

  console.log('campos:', [
    await fill('partner_name', `Candidato ${TAG}`),
    await fill('email_from', `candidato.${TAG}@example.com`),
    await fill('partner_phone', '8095551234'),
    await fill('linkedin_profile', 'https://linkedin.com/in/candidato'),
    await fill('short_introduction', 'Postulacion de prueba desde navegador'),
  ].join(' '));

  const hidden = await page.evaluate(() => {
    const f = document.querySelector('form#hr_recruitment_form');
    return Object.fromEntries(
      [...f.querySelectorAll('input[type=hidden]')].map((i) => [i.name, i.value])
    );
  });
  console.log('ocultos:', JSON.stringify(hidden));

  await page.click('form#hr_recruitment_form .s_website_form_send, form#hr_recruitment_form a.s_website_form_send, form#hr_recruitment_form button[type=submit]');
  await new Promise((r) => setTimeout(r, 6000));

  const result = await page.evaluate(() => {
    const el = document.querySelector('#s_website_form_result, #o_website_form_result');
    return el ? el.innerText.trim() : '(sin bloque de resultado)';
  });

  console.log('POSTS:', posts.join(' | '));
  console.log('URL_FINAL:', page.url());
  console.log('MENSAJE:', JSON.stringify(result));
  await page.screenshot({ path: `${__dirname}/apply_${TAG}.png`, fullPage: false });
  await browser.close();
})();
