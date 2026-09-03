// Standard layout for the QA manuals: the one in
// docs/Odoo Pro _ V15 _ POS Backend _ [PRUEBAS] Flujos y configuraciones.pdf.
//
// Everything a reader sees comes from here, so a new manual only writes content
// in configs/<module>.json and still comes out looking like the rest of them:
//
//   cover page  ->  illustration, Progressa logo, "Aseguramiento de Calidad"
//   Datos Generales  ->  bordered table, module name and technical name
//   Leyenda casos de uso  ->  the two markers the checklists use
//   Revisión casos de uso  ->  nested checklist with the pass/fail marker
//   blue section bars  ->  one per group of flows
//   flow  ->  lettered heading, justified paragraph, screenshot
//
// The palette and the typeface are the ones measured on that PDF: #0091c4 for
// the bars, borders and markers, #073763 for the headings, Open Sans throughout.
// The font is vendored under assets/fonts so a manual generated on a machine
// with no network still comes out with the right letters.
import { readFileSync } from "node:fs";
import { join } from "node:path";

const ACCENT = "#0091c4";
const NAVY = "#073763";
const INK = "#202124";

const OK_MARK = "✅";
const FAIL_MARK = "🚫";

function dataUri(path, mime) {
    return `data:${mime};base64,${readFileSync(path).toString("base64")}`;
}

function escapeHtml(text) {
    return String(text)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

/** The slice of Markdown the configs actually use: bold, italic, code, links. */
function inline(text) {
    return escapeHtml(text)
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
        .replace(/(^|[\s(])\*([^*]+)\*/g, "$1<em>$2</em>")
        .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
}

/** Paragraphs and dash lists out of a config string. */
function blocks(text) {
    const out = [];
    let list = [];
    const flushList = () => {
        if (list.length) out.push(`<ul class="plain">${list.join("")}</ul>`);
        list = [];
    };
    for (const chunk of String(text).split(/\n\s*\n/)) {
        const lines = chunk.split("\n").map((line) => line.trim()).filter(Boolean);
        if (!lines.length) continue;
        if (lines.every((line) => line.startsWith("- ") || line.startsWith("* "))) {
            for (const line of lines) list.push(`<li>${inline(line.slice(2))}</li>`);
            continue;
        }
        flushList();
        out.push(`<p>${lines.map(inline).join("<br />")}</p>`);
    }
    flushList();
    return out.join("\n");
}

/** `a.`, `b.` ... like the reference manual numbers its steps inside a section. */
function letter(index) {
    return String.fromCharCode(97 + (index % 26));
}

function caseItem(item) {
    const mark = item.ok === false ? FAIL_MARK : OK_MARK;
    const note = item.note ? ` <span class="case-note">${inline(item.note)}</span>` : "";
    return `<li>${inline(item.label)} <span class="mark">${mark}</span>${note}</li>`;
}

function caseGroup(group) {
    const items = (group.items || []).map(caseItem).join("");
    return `
        <li class="case-group">${inline(group.title)}
            <ul class="case-items">${items}</ul>
        </li>`;
}

function caseBlock(block) {
    const groups = (block.groups || []).map(caseGroup).join("");
    const items = (block.items || []).map(caseItem).join("");
    return `
    <li class="case-block">${inline(block.title)}
        <ul class="case-groups">${groups}${items}</ul>
    </li>`;
}

function coverPage(config, assets) {
    const cover = config.cover || {};
    const program = cover.program || "Aseguramiento de Calidad";
    const subject = cover.subject || config.title || config.module;
    return `
    <section class="cover">
        <img class="cover-art" src="${assets.illustration}" alt="" />
        <div class="cover-brand">
            <img src="${assets.logo}" alt="Progressa Corporate Group" />
            <span class="cover-block"></span>
        </div>
        <div class="cover-titles">
            <h1>${escapeHtml(program)}</h1>
            <p>${escapeHtml(subject)}</p>
        </div>
    </section>`;
}

function generalTable(config) {
    // A manual with no `general` block still gets the table: the module and its
    // technical name are the two rows every one of these documents opens with.
    const rows = config.general?.length
        ? config.general
        : [
              { label: "Módulo", value: (config.cover?.subject || config.title || "").toUpperCase() },
              { label: "Nombre técnico", value: `\`${config.module}\`` },
          ];
    const body = rows
        .map(
            (row) => `
            <tr>
                <th>${inline(row.label)}</th>
                <td>${(Array.isArray(row.value) ? row.value : [row.value])
                    .map((value) => `<div>${inline(value)}</div>`)
                    .join("")}</td>
            </tr>`
        )
        .join("");
    // The legend explains the marks of the checklist: with no checklist it is noise.
    const legend = config.cases?.length
        ? `
    <p class="legend-title">Leyenda casos de uso</p>
    <p class="legend">
        <span class="mark">${OK_MARK}</span> = Funcionó<br />
        <span class="mark">${FAIL_MARK}</span> = No Funcionó
    </p>`
        : "";
    return `
    <h1>Datos Generales</h1>
    <table class="general">${body}</table>
${legend}`;
}

function casesSection(config) {
    if (!config.cases?.length) return "";
    return `
    <h1>Revisión casos de uso</h1>
    <ul class="case-blocks">${config.cases.map(caseBlock).join("")}</ul>`;
}

function flowSection(flow, index, imagesDir) {
    const image =
        flow.image === false
            ? ""
            : `<figure><img src="${imagesDir}/${flow.id}.png" alt="${escapeHtml(flow.title)}" /></figure>`;
    // The letter is the reference manual's step marker, so a title that already
    // carries its own "3." loses it here instead of reading "c. 3. ...".
    const title = String(flow.title).replace(/^\s*\d+[.)]\s*/, "");
    return `
    <div class="flow">
        <h3><span class="flow-letter">${letter(index)}.</span> ${inline(title)}</h3>
        ${flow.description ? blocks(flow.description) : ""}
        ${image}
    </div>`;
}

/** Flows grouped by `flow.section`, each group under its own blue bar. */
function flowSections(config, imagesDir) {
    const groups = [];
    for (const flow of config.flows || []) {
        const title = flow.section || config.banner || "Flujos y configuraciones";
        const last = groups[groups.length - 1];
        if (last && last.title === title) last.flows.push(flow);
        else groups.push({ title, flows: [flow] });
    }
    return groups
        .map(
            (group) => `
    <div class="bar">${escapeHtml(group.title)}</div>
    ${group.flows.map((flow, index) => flowSection(flow, index, imagesDir)).join("")}`
        )
        .join("");
}

/**
 * @param {object} config  the manual config, as read from configs/<module>.json
 * @param {object} options
 * @param {string} options.assetsDir  where progressa-logo.png and friends live
 * @param {string} [options.imagesDir="img"]  screenshot folder, relative to the HTML
 * @param {string} [options.command]  the command that regenerates the manual
 */
export function renderManualHtml(config, options) {
    const { assetsDir, imagesDir = "img", command } = options;
    const assets = {
        logo: dataUri(join(assetsDir, "progressa-logo.png"), "image/png"),
        illustration: dataUri(join(assetsDir, "cover-illustration.png"), "image/png"),
        font: dataUri(join(assetsDir, "fonts", "open-sans.woff2"), "font/woff2"),
    };

    const requirements = config.requirements?.length
        ? `
    <h2>Requisitos previos</h2>
    <ul class="plain">${config.requirements.map((item) => `<li>${inline(item)}</li>`).join("")}</ul>`
        : "";

    return `<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8" />
<title>${escapeHtml(config.title || config.module)}</title>
<style>
@font-face {
    font-family: "Open Sans";
    src: url(${assets.font}) format("woff2");
    font-weight: 300 800;
    font-style: normal;
}

@page { size: letter; margin: 20mm 18mm; }

* { box-sizing: border-box; }

body {
    margin: 0;
    color: ${INK};
    font-family: "Open Sans", "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.45;
}

/* Cover ---------------------------------------------------------------- */
.cover {
    height: 100%;
    page-break-after: always;
    text-align: center;
    padding-top: 6mm;
}
.cover-art { width: 74%; max-height: 118mm; object-fit: contain; }
.cover-brand {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4mm;
    margin: 6mm 0 8mm;
}
.cover-brand img { width: 62mm; }
.cover-block { width: 15mm; height: 34mm; background: ${ACCENT}; }
.cover-titles { border-top: 2.5px solid #000; border-bottom: 2.5px solid #000; padding: 6mm 0; }
.cover-titles h1 { margin: 0 0 4mm; font-size: 26pt; }
.cover-titles p { margin: 0; font-size: 13pt; font-weight: 700; }

/* Headings ------------------------------------------------------------- */
h1 { font-size: 19pt; margin: 0 0 6mm; }
h2 { font-size: 14pt; margin: 8mm 0 3mm; }
h3 { font-size: 11.5pt; color: ${NAVY}; margin: 7mm 0 2mm; }
.flow-letter { color: ${ACCENT}; }

p { margin: 0 0 3mm; text-align: justify; }
code {
    font-family: "SFMono-Regular", Menlo, Consolas, monospace;
    font-size: 0.92em;
    background: #f4f6f8;
    padding: 0 2px;
}
a { color: ${ACCENT}; text-decoration: none; }

/* Datos Generales ------------------------------------------------------ */
table.general { width: 100%; border-collapse: collapse; margin-bottom: 8mm; }
table.general th,
table.general td { border: 1px solid ${ACCENT}; padding: 2mm 3mm; text-align: left; vertical-align: top; }
table.general th { width: 34%; font-weight: 700; }

.legend-title { font-weight: 700; margin-bottom: 1.5mm; }
.legend { margin-bottom: 8mm; }
.mark { font-family: "Apple Color Emoji", "Segoe UI Emoji", "Noto Color Emoji", sans-serif; }

/* Checklists ----------------------------------------------------------- */
ul.case-blocks { list-style: none; padding-left: 4mm; margin: 0; }
li.case-block {
    color: ${NAVY};
    font-weight: 700;
    text-transform: uppercase;
    margin-bottom: 4mm;
}
li.case-block::before { content: "❖  "; color: ${ACCENT}; }
ul.case-groups { list-style: none; padding-left: 7mm; margin: 1.5mm 0 0; }
li.case-group { color: ${INK}; font-weight: 400; text-transform: none; margin-bottom: 1mm; }
li.case-group::before { content: "➢  "; color: ${NAVY}; }
ul.case-items { list-style: none; padding-left: 7mm; margin: 0.5mm 0 2mm; }
ul.case-items li { color: ${INK}; font-weight: 400; text-transform: none; }
ul.case-items li::before { content: "▪  "; color: ${INK}; }
.case-note { color: #5f6368; font-size: 0.92em; }

ul.plain { margin: 0 0 4mm; padding-left: 6mm; }
ul.plain li { margin-bottom: 1mm; }

/* Section bars and flows ----------------------------------------------- */
.bar {
    background: ${ACCENT};
    color: #fff;
    font-weight: 700;
    padding: 2.4mm 3mm;
    margin: 10mm 0 5mm;
    page-break-after: avoid;
}
.flow h3 { page-break-after: avoid; }
figure { margin: 3mm 0 6mm; page-break-inside: avoid; text-align: center; }
/* Capped so a full-page capture does not eat a page on its own, and never
   stretched: these are screenshots, a wrong aspect ratio reads as a bug. */
figure img { max-width: 100%; max-height: 165mm; border: 1px solid #e2e5e9; }

.intro { margin-bottom: 6mm; }
.source {
    margin: 10mm 0 0;
    padding-top: 3mm;
    border-top: 1px solid #e2e5e9;
    color: #5f6368;
    font-size: 8.5pt;
    text-align: left;
}
</style>
</head>
<body>
${coverPage(config, assets)}
${generalTable(config)}
${config.intro ? `<div class="intro">${blocks(config.intro)}</div>` : ""}
${config.database ? `<p><strong>Base de datos de las capturas:</strong> ${inline(config.database)}</p>` : ""}
${requirements}
${casesSection(config)}
${flowSections(config, imagesDir)}
${config.notes ? `<h2>Notas</h2>${blocks(config.notes)}` : ""}
${command ? `<p class="source">Generado con <code>${escapeHtml(command)}</code>.</p>` : ""}
</body>
</html>`;
}
