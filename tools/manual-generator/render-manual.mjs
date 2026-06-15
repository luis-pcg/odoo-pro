// Renders docs/manuals/<module>/README.md from a module's manual config and the
// screenshots captured by capture.mjs.
//
// Usage:
//   node render-manual.mjs --config=configs/<module>.json --img=<imgDir> --out=<README.md>
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";

function arg(name, def = undefined) {
    const prefix = `--${name}=`;
    const found = process.argv.find((a) => a.startsWith(prefix));
    return found ? found.slice(prefix.length) : def;
}

const configPath = arg("config");
const imgDir = arg("img");
const outPath = arg("out");
const config = JSON.parse(readFileSync(configPath, "utf8"));

const lines = [];
lines.push(`# ${config.title}`, "");
lines.push(
    "> Manual generado con `tools/manual-generator`. Las capturas se regeneran " +
        "ejecutando el generador contra una base `test_v19_<módulo>`.",
    ""
);
if (config.intro) {
    lines.push(config.intro, "");
}
if (config.requirements && config.requirements.length) {
    lines.push("## Requisitos previos", "");
    for (const req of config.requirements) {
        lines.push(`- ${req}`);
    }
    lines.push("");
}
for (const flow of config.flows) {
    lines.push(`## ${flow.title}`, "");
    if (flow.description) {
        lines.push(flow.description, "");
    }
    if (flow.image !== false) {
        const file = `${flow.id}.png`;
        if (imgDir && existsSync(join(imgDir, file))) {
            lines.push(`![${flow.title}](img/${file})`, "");
        } else {
            lines.push("> _(captura pendiente: ejecutar el generador)_", "");
        }
    }
}
if (config.notes) {
    lines.push("## Notas", "");
    lines.push(config.notes, "");
}

writeFileSync(outPath, lines.join("\n"));
console.log("wrote", outPath);
