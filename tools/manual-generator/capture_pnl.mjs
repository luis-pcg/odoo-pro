// Captures the DR "Estado de Resultados" (Profit & Loss) report screen for a
// given DB, to document the sequence/structure bug (broken vs fixed).
import { chromium } from "playwright";
import { mkdirSync } from "node:fs";
import { join } from "node:path";

function arg(name, def) {
    const p = `--${name}=`;
    const f = process.argv.find((a) => a.startsWith(p));
    return f ? f.slice(p.length) : def;
}
const baseUrl = (arg("base-url", "http://localhost:8092")).replace(/\/+$/, "");
const db = arg("db");
const out = arg("out");
const tag = arg("tag", "report");
const login = arg("login", "admin");
const password = arg("password", "admin");
const headed = process.argv.includes("--headed");
if (!db || !out) { console.error("need --db --out"); process.exit(2); }
mkdirSync(out, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: !headed });
const ctx = await browser.newContext({ viewport: { width: 1500, height: 950 }, deviceScaleFactor: 2 });
const page = await ctx.newPage();

const auth = await ctx.request.post(`${baseUrl}/web/session/authenticate`, {
    headers: { "Content-Type": "application/json" },
    data: { jsonrpc: "2.0", method: "call", params: { db, login, password } },
});
const aj = await auth.json();
if (!aj.result || !aj.result.uid) { console.error("auth failed:", JSON.stringify(aj.error || aj)); await browser.close(); process.exit(1); }
console.log("auth uid", aj.result.uid, "on", db);

// Boot the web client first, then open the report action.
await page.goto(`${baseUrl}/odoo`, { waitUntil: "domcontentloaded" });
await page.waitForSelector(".o_main_navbar", { timeout: 30000 });
await page.goto(`${baseUrl}/odoo/action-l10n_do_reports.action_account_report_do_pl`, { waitUntil: "domcontentloaded" });
// Wait for either the report table or an error dialog to appear.
await Promise.race([
    page.waitForSelector(".o_content table, .o_account_reports_table, .table", { timeout: 25000 }).catch(() => {}),
    page.waitForSelector(".o_dialog .modal-content, .o_error_dialog", { timeout: 25000 }).catch(() => {}),
]);
await page.waitForTimeout(2500);
const errDialog = await page.$(".o_dialog .modal-content, .o_error_dialog");
const shot = join(out, `${tag}.png`);
await page.screenshot({ path: shot, fullPage: true });
console.log("captured", shot, "errorDialogVisible:", !!errDialog);

await browser.close();
