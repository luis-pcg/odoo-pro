// Captures the payroll-sync manual across three live Odoo instances.
//
// Same step vocabulary as tools/manual-generator/capture.mjs, plus two things
// that manual needs and a single-instance run cannot express:
//
//   * "instance": which of the three databases the screenshot is taken on;
//     each one gets its own authenticated browser context.
//   * "exec": shell commands run before the steps, so a screenshot can show
//     the state produced by an action (a delivery, a failure, a pull).
//   * "viewport": a taller window for one screenshot. Odoo forms scroll inside
//     their own container, so a full-page shot of a long form clips it.
//
// Usage:
//   node capture.mjs --config=config.json --out=<imgDir> \
//        --instances='padre=http://localhost:8101|manual_padre,...' [--headed]
import { chromium } from "playwright";
import { readFileSync, mkdirSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const HERE = dirname(fileURLToPath(import.meta.url));

function arg(name, def = undefined) {
    const prefix = `--${name}=`;
    const found = process.argv.find((a) => a.startsWith(prefix));
    return found ? found.slice(prefix.length) : def;
}

const configPath = arg("config", join(HERE, "config.json"));
const outDir = arg("out");
const login = arg("login", "admin");
const password = arg("password", "admin");
const headed = process.argv.includes("--headed");

// padre=http://localhost:8101|manual_padre,hija1=...
const instances = {};
for (const chunk of (arg("instances") || "").split(",").filter(Boolean)) {
    const [name, rest] = chunk.split("=");
    const [url, db] = rest.split("|");
    instances[name] = { url: url.replace(/\/+$/, ""), db };
}

if (!outDir || !Object.keys(instances).length) {
    console.error("Missing required args: --out, --instances");
    process.exit(2);
}

const config = JSON.parse(readFileSync(configPath, "utf8"));
mkdirSync(outDir, { recursive: true });

const DEFAULT_VIEWPORT = { width: 1440, height: 900 };

const browser = await chromium.launch({ channel: "chrome", headless: !headed });

// One authenticated context per instance: the session cookie of one database
// is meaningless to the others.
const sessions = {};
for (const [name, inst] of Object.entries(instances)) {
    const context = await browser.newContext({
        viewport: DEFAULT_VIEWPORT,
        deviceScaleFactor: 2,
    });
    const authResp = await context.request.post(`${inst.url}/web/session/authenticate`, {
        headers: { "Content-Type": "application/json" },
        data: { jsonrpc: "2.0", method: "call", params: { db: inst.db, login, password } },
    });
    const authJson = await authResp.json();
    if (!authJson.result || !authJson.result.uid) {
        console.error(`Authentication failed on ${name}:`, JSON.stringify(authJson.error || authJson));
        await browser.close();
        process.exit(1);
    }
    sessions[name] = { ...inst, context, page: await context.newPage() };
    console.log(`authenticated on ${name} (${inst.db}) as uid ${authJson.result.uid}`);
}

async function runStep(page, baseUrl, step) {
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
        await page.locator(step.type).pressSequentially(step.value ?? "", { delay: 30 });
    }
    if (step.scrollTo) {
        await page.locator(step.scrollTo).first().scrollIntoViewIfNeeded({ timeout });
    }
    if (step.selectOption) {
        const opt = step.label !== undefined ? { label: step.label } : { value: step.value };
        await page.selectOption(step.selectOption, opt, { timeout });
    }
    if (step.click) {
        await page.click(step.click, { timeout });
    }
    if (step.clickText) {
        await page.getByText(step.clickText, { exact: step.exact ?? false }).first().click({ timeout });
    }
    if (step.hover) {
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

async function runExec(command) {
    // Commands are declared in the config, not built from page content.
    const { stdout, stderr } = await execFileAsync("bash", ["-lc", command], {
        cwd: HERE,
        timeout: 180000,
        maxBuffer: 8 * 1024 * 1024,
    });
    const line = (stdout || stderr).trim().split("\n").filter(Boolean).pop() || "";
    console.log(`  exec: ${command} -> ${line}`);
}

// --only=25-corridas,18-escala-isr re-shoots a few screens against the
// environment as it already stands, without replaying the whole script.
const only = (arg("only") || "").split(",").map((s) => s.trim()).filter(Boolean);

let captured = 0;
let failed = 0;
for (const flow of config.flows) {
    if (only.length && !only.includes(flow.id)) {
        continue;
    }
    try {
        for (const command of flow.exec || []) {
            await runExec(command);
        }
        if (flow.image === false) {
            continue; // text-only section, may still carry exec side effects
        }
        const session = sessions[flow.instance || "padre"];
        if (!session) {
            throw new Error(`unknown instance '${flow.instance}'`);
        }
        if (flow.viewport) {
            await session.page.setViewportSize(flow.viewport);
        }
        for (const step of flow.steps || []) {
            await runStep(session.page, session.url, step);
        }
        if (flow.expandGroups) {
            // A grouped list shows only the group headers, which hides exactly
            // the rows the manual is pointing at.
            for (let i = 0; i < 8; i += 1) {
                const collapsed = await session.page.$(".o_group_header:not(.o_group_open)");
                if (!collapsed) break;
                await collapsed.click();
                await session.page.waitForTimeout(400);
            }
        }
        await session.page.waitForTimeout(600);
        const path = join(outDir, `${flow.id}.png`);
        if (flow.screenshotEl) {
            const el = await session.page.$(flow.screenshotEl);
            if (el) {
                await el.screenshot({ path });
            } else {
                await session.page.screenshot({ path, fullPage: true });
            }
        } else {
            await session.page.screenshot({ path, fullPage: true });
        }
        if (flow.viewport) {
            await session.page.setViewportSize(DEFAULT_VIEWPORT);
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
