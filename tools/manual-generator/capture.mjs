// Drives an Odoo web session with Playwright (system Chrome) and captures
// screenshots for each flow defined in a module's manual config.
//
// Usage:
//   node capture.mjs --config=configs/<module>.json --base-url=http://localhost:8094 \
//        --db=<db> --login=admin --password=admin --out=<imgDir> [--headed]
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";
import { join, dirname, isAbsolute } from "node:path";

function arg(name, def = undefined) {
    const prefix = `--${name}=`;
    const found = process.argv.find((a) => a.startsWith(prefix));
    return found ? found.slice(prefix.length) : def;
}

const configPath = arg("config");
const baseUrl = (arg("base-url") || "http://localhost:8069").replace(/\/+$/, "");
const db = arg("db");
const login = arg("login", "admin");
const password = arg("password", "admin");
const outDir = arg("out");
const headed = process.argv.includes("--headed");

if (!configPath || !db || !outDir) {
    console.error("Missing required args: --config, --db, --out");
    process.exit(2);
}

const config = JSON.parse(readFileSync(configPath, "utf8"));
mkdirSync(outDir, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: !headed });
const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
});
const page = await context.newPage();

// Authenticate via JSON-RPC; the session cookie is stored on the context and
// reused by page navigations.
const authResp = await context.request.post(`${baseUrl}/web/session/authenticate`, {
    headers: { "Content-Type": "application/json" },
    data: { jsonrpc: "2.0", method: "call", params: { db, login, password } },
});
const authJson = await authResp.json();
if (!authJson.result || !authJson.result.uid) {
    console.error("Authentication failed:", JSON.stringify(authJson.error || authJson));
    await browser.close();
    process.exit(1);
}
console.log("Authenticated as uid", authJson.result.uid, "on", db);

async function runStep(step) {
    const timeout = step.timeout || 15000;
    if (step.goto) {
        await page.goto(`${baseUrl}${step.goto}`, { waitUntil: "domcontentloaded" });
    }
    if (step.waitFor) {
        await page.waitForSelector(step.waitFor, { timeout });
    }
    if (step.fill) {
        await page.fill(step.fill, step.value ?? "");
    }
    if (step.type) {
        // Types character by character so live widgets (autocomplete) react.
        await page.locator(step.type).pressSequentially(step.value ?? "", { delay: 30 });
    }
    if (step.scrollTo) {
        // Scrolls the element into view (Odoo forms scroll inside .o_content,
        // so fullPage screenshots don't reach content below the fold).
        await page.locator(step.scrollTo).first().scrollIntoViewIfNeeded({ timeout });
    }
    if (step.scrollToLast) {
        // Same as scrollTo but targets the LAST match — e.g. the last payment
        // line of an invoice, so everything above it ends up in view.
        await page.locator(step.scrollToLast).last().scrollIntoViewIfNeeded({ timeout });
    }
    if (step.selectOption) {
        // Native <select> widgets (Odoo widget="selection"). Choose by visible
        // label when given, otherwise by option value.
        const opt = step.label !== undefined ? { label: step.label } : { value: step.value };
        await page.selectOption(step.selectOption, opt, { timeout });
    }
    if (step.click) {
        await page.click(step.click, { timeout });
    }
    if (step.setFile) {
        // Uploads a file into an <input type="file"> (works on hidden inputs,
        // e.g. Odoo binary fields). `path` is resolved relative to the config.
        const filePath = isAbsolute(step.path) ? step.path : join(dirname(configPath), step.path);
        await page.setInputFiles(step.setFile, filePath, { timeout });
    }
    if (step.hover) {
        // Parks the mouse on a neutral element (e.g. the breadcrumb) so no
        // row/cell tooltip is open when the screenshot is taken.
        await page.locator(step.hover).first().hover({ timeout });
    }
    if (step.press) {
        await page.keyboard.press(step.press);
    }
    if (step.waitForHidden) {
        await page.waitForSelector(step.waitForHidden, { state: "hidden", timeout });
    }
    if (typeof step.wait === "number") {
        await page.waitForTimeout(step.wait);
    }
}

let captured = 0;
let failed = 0;
for (const flow of config.flows) {
    if (flow.image === false) {
        continue; // text-only flow, no screenshot
    }
    try {
        for (const step of flow.steps || []) {
            await runStep(step);
        }
        await page.waitForTimeout(600);
        const path = join(outDir, `${flow.id}.png`);
        if (flow.screenshotEl) {
            const el = await page.$(flow.screenshotEl);
            if (el) {
                await el.screenshot({ path });
            } else {
                await page.screenshot({ path, fullPage: true });
            }
        } else {
            await page.screenshot({ path, fullPage: true });
        }
        captured += 1;
        console.log("captured", `${flow.id}.png`);
    } catch (error) {
        failed += 1;
        console.warn(`flow ${flow.id} failed: ${error.message}`);
    }
}

await browser.close();
console.log(`Done. captured=${captured} failed=${failed}`);
process.exit(failed && captured === 0 ? 1 : 0);
