// Renders docs/manuals/l10n_do_hr_payroll_sync/README.md from config.json and
// the screenshots captured across the three instances.
//
// Usage:
//   node render.mjs --config=config.json --img=<imgDir> --out=<README.md>
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

function arg(name, def = undefined) {
    const prefix = `--${name}=`;
    const found = process.argv.find((a) => a.startsWith(prefix));
    return found ? found.slice(prefix.length) : def;
}

const config = JSON.parse(readFileSync(arg("config"), "utf8"));
const imgDir = arg("img");
const outPath = arg("out");

const INSTANCE_LABEL = {
    padre: "padre · PROGRESSA (Casa Matriz) — maestra, con el módulo",
    hija1: "hija 1 · Distribuidora Acme, SRL — cliente, sin el módulo",
    hija2: "hija 2 · Ferretería Bella Vista, SRL — cliente, sin el módulo",
};

const lines = [];
lines.push(`# ${config.title}`, "");
lines.push(
    "> Manual generado con `tools/sync-manual`. Las capturas se rehacen levantando " +
        "las tres instancias con `setup.sh` y ejecutando `generate.sh`.",
    ""
);
if (config.intro) lines.push(config.intro, "");

if (config.requirements?.length) {
    lines.push("## Requisitos previos", "");
    for (const req of config.requirements) lines.push(`- ${req}`);
    lines.push("");
}

// Index of the captured steps, so a reader can jump straight to the part they need.
lines.push("## Contenido", "");
for (const flow of config.flows) {
    // Part headers sit flush; everything they cover is indented under them.
    const indent = flow.section ? "" : "  ";
    lines.push(`${indent}- ${flow.title}`);
}
lines.push("");

for (const flow of config.flows) {
    lines.push(`## ${flow.title}`, "");
    if (flow.instance) {
        lines.push(`**Instancia:** ${INSTANCE_LABEL[flow.instance] || flow.instance}`, "");
    }
    if (flow.description) lines.push(flow.description, "");
    if (flow.staticImage) {
        // Hand-drawn asset (the architecture diagram), not a captured screen.
        lines.push(`![${flow.title}](img/${flow.staticImage})`, "");
    }
    if (flow.image !== false) {
        const file = `${flow.id}.png`;
        if (imgDir && existsSync(join(imgDir, file))) {
            lines.push(`![${flow.title}](img/${file})`, "");
        } else {
            lines.push("> _(captura pendiente: ejecutar `generate.sh`)_", "");
        }
    }
}

if (config.notes) lines.push(config.notes, "");

writeFileSync(outPath, lines.join("\n"));
console.log("wrote", outPath);
