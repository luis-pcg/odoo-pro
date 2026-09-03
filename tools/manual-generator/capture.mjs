// Manual generator: drives Odoo with Playwright from a JSON config and writes
// docs/manuals/<module>/README.md plus one screenshot per flow.
//
//   node capture.mjs --config=configs/<module>.json --db=<db> \
//                    [--base-url=http://localhost:8071] [--out=<dir>] [--headed]
//                    [--only=01-flow-id,02-other] [--render-only] [--name=manual]
//
// --name gives the written files another basename (<name>.md/.html/.pdf), so a
// second manual of the same module -- a short one for end users next to the
// full one -- lives in the same folder without overwriting it.
//
// --render-only rebuilds README.md, manual.html and manual.pdf from the
// screenshots already on disk: text and layout can be iterated on without
// driving Odoo again, which is the slow part.
//
// Config contract (see configs/*.json):
//   module, title, intro, requirements[], notes, flows[]
//   flow: { id, title, description, image?: false, fullPage?: bool,
//           element?: "sel"  -> screenshot just that element (close-up),
//           viewport?: { width?, height? }  -> shorter window for a short page,
//                                             so the shot is not half blank, steps[] }
//   step: one of
//     { goto: "/web#action=..." }        navigate (waits for the web client)
//     { gotoXmlId: "module.xml_id",      open that record's form, resolving the id
//       action: "module.action" }         over RPC: survives a rebuilt database and
//                                        does not depend on the UI language the way
//                                        searching the record by name does. `action`
//                                        is the window action to open it in, and is
//                                        needed for models with no default one
//     { waitFor: "sel", timeout?: ms }   wait for a selector
//     { click: "sel", timeout?: ms }     click the first match
//     { fill: "sel", value: "text" }     type into a field
//     { press: "Enter", sel?: "sel" }    keyboard
//     { scrollTo: "sel" }                scroll the element into view
//     { expand: "sel" }                  grow the viewport to the element's
//                                        scrollHeight, for panes that scroll
//                                        internally (account_reports, settings)
//     { wait: ms }                       plain pause
//
// Captures against an ALREADY RUNNING Odoo (--base-url). That deliberately avoids
// the ephemeral-container traps: no shared filestore (PermissionError while
// regenerating assets) and no cold asset bundles. The first navigation still warms
// the bundles up, so it waits on .o_main_navbar with a long timeout.
import { chromium } from "playwright";
import { mkdirSync, writeFileSync, readFileSync } from "node:fs";
import { join, dirname, isAbsolute, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { renderManualHtml } from "./template.mjs";

function arg(name, def) {
    const prefix = `--${name}=`;
    const found = process.argv.find((a) => a.startsWith(prefix));
    return found ? found.slice(prefix.length) : def;
}

const configPath = arg("config");
const db = arg("db");
if (!configPath || !db) {
    console.error("need --config=configs/<module>.json --db=<database>");
    process.exit(2);
}
const baseUrl = arg("base-url", "http://localhost:8071").replace(/\/+$/, "");
const login = arg("login", "admin");
const password = arg("password", "admin");
const headed = process.argv.includes("--headed");
const renderOnly = process.argv.includes("--render-only");
const name = arg("name", "manual");
const only = (arg("only", "") || "").split(",").filter(Boolean);

const config = JSON.parse(readFileSync(configPath, "utf8"));
// From this script's own location (tools/manual-generator), never from the cwd:
// the output has to land in <repo>/docs/manuals whoever runs it and from where.
const repoRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const outDir = arg("out", join(repoRoot, "docs", "manuals", config.module));
const assetsDir = resolve(dirname(fileURLToPath(import.meta.url)), "assets");
const imgDir = join(outDir, "img");
mkdirSync(imgDir, { recursive: true });

const VIEWPORT = { width: 1600, height: 1000 };

const browser = await chromium.launch({ channel: "chrome", headless: !headed });
const ctx = await browser.newContext({ viewport: VIEWPORT, deviceScaleFactor: 2 });
const page = await ctx.newPage();

const problems = [];

if (!renderOnly) {

// Session cookie first, so every later navigation is already authenticated.
const auth = await ctx.request.post(`${baseUrl}/web/session/authenticate`, {
    headers: { "Content-Type": "application/json" },
    data: { jsonrpc: "2.0", method: "call", params: { db, login, password } },
});
const authJson = await auth.json();
if (!authJson.result || !authJson.result.uid) {
    console.error("auth failed:", JSON.stringify(authJson.error || authJson).slice(0, 400));
    await browser.close();
    process.exit(1);
}
console.log(`auth uid=${authJson.result.uid} db=${db}`);

// Warm up: on a database installed with --no-http the asset bundles are compiled
// on this first request, which can take minutes on one worker.
await page.goto(`${baseUrl}/web`, { waitUntil: "domcontentloaded" });
await page.waitForSelector(".o_main_navbar", { timeout: 300000 });
console.log("web client up");

async function runStep(step, flowId) {
    if (step.goto !== undefined) {
        await page.goto(baseUrl + step.goto, { waitUntil: "domcontentloaded" });
        await page.waitForSelector(".o_main_navbar", { timeout: 60000 });
        return;
    }
    if (step.gotoXmlId !== undefined) {
        const [module, name] = String(step.gotoXmlId).split(".");
        const response = await ctx.request.post(`${baseUrl}/web/dataset/call_kw`, {
            headers: { "Content-Type": "application/json" },
            data: {
                jsonrpc: "2.0",
                method: "call",
                params: {
                    model: "ir.model.data",
                    method: "check_object_reference",
                    args: [module, name],
                    // It checks read access with a plain search, which skips
                    // archived records: without this an inactive record -- a cron
                    // that ships disabled, for one -- resolves to id `false`.
                    kwargs: { context: { active_test: false } },
                },
            },
        });
        const reference = (await response.json()).result;
        if (!reference) {
            problems.push(`${flowId}: no record for ${step.gotoXmlId}`);
            return;
        }
        const [model, id] = reference;
        // The action goes in the hash when the step names one: a bare
        // `#model=...&id=...` leaves the web client without an action to build
        // the form from, and it answers with a client error dialog.
        const hash = step.action
            ? `action=${step.action}&id=${id}&view_type=form`
            : `model=${model}&id=${id}&view_type=form`;
        await page.goto(`${baseUrl}/web#${hash}`, { waitUntil: "domcontentloaded" });
        await page.waitForSelector(".o_main_navbar", { timeout: 60000 });
        return;
    }
    if (step.waitFor !== undefined) {
        await page.waitForSelector(step.waitFor, { timeout: step.timeout || 30000 });
        return;
    }
    if (step.click !== undefined) {
        await page.locator(step.click).first().click({ timeout: step.timeout || 30000 });
        return;
    }
    if (step.fill !== undefined) {
        await page.locator(step.fill).first().fill(String(step.value ?? ""), { timeout: 30000 });
        return;
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
    if (step.press !== undefined) {
        if (step.sel) await page.locator(step.sel).first().press(step.press);
        else await page.keyboard.press(step.press);
        return;
    }
    if (step.scrollTo !== undefined) {
        await page.locator(step.scrollTo).first().scrollIntoViewIfNeeded({ timeout: 30000 });
        return;
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
    if (step.expand !== undefined) {
        const height = await page.evaluate((sel) => {
            const el = document.querySelector(sel);
            return el ? Math.min(el.scrollHeight + 220, 6000) : 0;
        }, step.expand);
        if (height > VIEWPORT.height) await page.setViewportSize({ width: VIEWPORT.width, height });
        return;
    }
    if (step.wait !== undefined) {
        await page.waitForTimeout(step.wait);
        return;
    }
    problems.push(`${flowId}: unknown step ${JSON.stringify(step)}`);
}

for (const flow of config.flows) {
    if (only.length && !only.includes(flow.id)) continue;
    if (flow.image === false) continue;

    console.log(`\n[${flow.id}] ${flow.title}`);
    if (flow.viewport) await page.setViewportSize({ ...VIEWPORT, ...flow.viewport });
    try {
        for (const step of flow.steps || []) await runStep(step, flow.id);
    } catch (error) {
        problems.push(`${flow.id}: ${String(error).split("\n")[0]}`);
        console.log(`   step failed: ${String(error).split("\n")[0]}`);
    }

    // An error dialog on screen means the captured page is not what the manual
    // claims it is: report it instead of shipping a screenshot of a traceback.
    const dialog = await page.$(".o_error_dialog, .o_dialog .modal-content .o_error_detail");
    if (dialog) problems.push(`${flow.id}: Odoo error dialog on screen`);

    // Park the pointer: Playwright leaves it where it last clicked, and a tooltip
    // hanging over a column header is not what the manual is documenting.
    await page.mouse.move(0, 0);
    await page.waitForTimeout(400);

    const shot = join(imgDir, `${flow.id}.png`);
    if (flow.element) {
        // Close-up of one block: keeps a settings panel or a single card readable
        // instead of shrinking the whole page.
        await page.locator(flow.element).first().screenshot({ path: shot });
    } else {
        await page.screenshot({ path: shot, fullPage: !!flow.fullPage });
    }
    console.log(`   -> ${shot.replace(repoRoot + "/", "")}`);

    if (await page.$(".o_viewport, body")) await page.setViewportSize(VIEWPORT);
}

} else {
    console.log("render-only: reusing the screenshots already in img/");
}

// ---------------------------------------------------------------- README.md
const lines = [];
lines.push(`# ${config.title}`, "");
lines.push(
    "> Manual generado con `tools/manual-generator`: " +
        `\`node capture.mjs --config=${configPath} --db=${db}\`. ` +
        "Las capturas se regeneran corriendo ese comando contra la base de pruebas.",
    ""
);
if (config.intro) lines.push(config.intro, "");
if (config.database) lines.push(`**Base de datos de las capturas:** ${config.database}`, "");
if (config.requirements?.length) {
    lines.push("## Requisitos previos", "");
    for (const requirement of config.requirements) lines.push(`- ${requirement}`);
    lines.push("");
}
for (const flow of config.flows) {
    lines.push(`## ${flow.title}`, "");
    if (flow.description) lines.push(flow.description, "");
    if (flow.image !== false) {
        lines.push(`![${flow.title}](img/${flow.id}.png)`, "");
    }
}
if (config.notes) lines.push("## Notas", "", config.notes, "");

const mdPath = join(outDir, name === "manual" ? "README.md" : `${name}.md`);
writeFileSync(mdPath, lines.join("\n"));
console.log(`\nREADME -> ${mdPath.replace(repoRoot + "/", "")}`);

// ------------------------------------------------- manual.html and manual.pdf
// The deliverable is the PDF: same cover, palette and section bars as
// docs/Odoo Pro _ V15 _ POS Backend _ [PRUEBAS] Flujos y configuraciones.pdf.
// The HTML is written next to it so the layout can be checked in a browser
// without reprinting, and because the PDF is built from that very file.
const command = `node capture.mjs --config=${configPath} --db=${db}`;
const htmlPath = join(outDir, `${name}.html`);
writeFileSync(htmlPath, renderManualHtml(config, { assetsDir, imagesDir: "img", command }));
console.log(`HTML   -> ${htmlPath.replace(repoRoot + "/", "")}`);

if (headed) {
    // Chromium only prints from headless; a --headed run is for watching the
    // capture, so it stops at the HTML instead of failing at the last step.
    console.log("PDF    -> skipped (--headed): run without --headed to print it");
} else {
    const pdfPage = await ctx.newPage();
    await pdfPage.goto(`file://${htmlPath}`, { waitUntil: "load" });
    await pdfPage.emulateMedia({ media: "print" });
    const pdfPath = join(outDir, `${name}.pdf`);
    await pdfPage.pdf({ path: pdfPath, printBackground: true, preferCSSPageSize: true });
    await pdfPage.close();
    console.log(`PDF    -> ${pdfPath.replace(repoRoot + "/", "")}`);
}

await browser.close();

if (problems.length) {
    console.log("\nPROBLEMAS:");
    for (const problem of problems) console.log(`  - ${problem}`);
    process.exit(1);
}
console.log(renderOnly ? "\nOK: manual rearmado con las capturas que ya estaban" : "\nOK: todas las capturas se tomaron sin error en pantalla");
