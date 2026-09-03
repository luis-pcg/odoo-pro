// Rasterizes assets/arquitectura.svg into the manual's image folder.
//
// The diagram ships as SVG so it stays editable, but the manual embeds a PNG:
// every markdown viewer renders it, and it sits next to the screenshots at the
// same 2x scale.
//
// Usage: node make-diagram.mjs --out=<imgDir>
import { chromium } from "playwright";
import { readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));

function arg(name, def = undefined) {
    const prefix = `--${name}=`;
    const found = process.argv.find((a) => a.startsWith(prefix));
    return found ? found.slice(prefix.length) : def;
}

const outDir = arg("out");
const svgPath = arg("svg", join(HERE, "assets", "arquitectura.svg"));
const name = arg("name", "29-arquitectura.png");
if (!outDir) {
    console.error("Missing required arg: --out");
    process.exit(2);
}

const svg = readFileSync(svgPath, "utf8");
const width = Number(/width="(\d+)"/.exec(svg)?.[1] || 1280);
const height = Number(/height="(\d+)"/.exec(svg)?.[1] || 880);

const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await browser.newPage({
    viewport: { width, height },
    deviceScaleFactor: 2,
});
await page.setContent(
    `<!doctype html><html><body style="margin:0;background:#fff">${svg}</body></html>`,
    { waitUntil: "load" }
);
await page.waitForTimeout(300);
await page.screenshot({ path: join(outDir, name) });
await browser.close();
console.log("wrote", join(outDir, name));
