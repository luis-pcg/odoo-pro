#!/usr/bin/env python3
"""parse_test_log.py — Genera reporte profesional de tests Odoo 17 (Markdown + PDF)."""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Patrones de log ─────────────────────────────────────────────────────────

LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<level>INFO|WARNING|ERROR|CRITICAL|DEBUG)\s+"
    r"(?P<db>\S+)\s+"
    r"(?P<logger>\S+):\s*"
    r"(?P<msg>.*)$"
)

RE_LOADING     = re.compile(r"Loading module (\S+)\s+\(")
RE_MOD_LOADED  = re.compile(r"Module (\S+) loaded in ([\d.]+)s")
RE_INCOMPATIBLE = re.compile(r"The module (\S+) has an incompatible version")
RE_TEST_STATS  = re.compile(r"^(\S+): (\d+) tests ([\d.]+)s")
RE_OVERALL     = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")
RE_MOD_FAIL    = re.compile(r"Module (\S+): (\d+) failures, (\d+) errors of (\d+) tests")
RE_FAIL_LINE   = re.compile(r"^(FAIL|ERROR): (.+)")
RE_SETUP_ERR   = re.compile(r"ERROR: setUpClass \(odoo\.addons\.([^.]+)\.")
RE_ADDON_LOGGER = re.compile(r"^odoo\.addons\.([^.]+)\.")


# ─── Parseo de logs ──────────────────────────────────────────────────────────

def parse_log(path: Path) -> list:
    entries: list = []
    if not path.exists():
        return entries
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            m = LOG_LINE.match(line)
            if m:
                entries.append(m.groupdict())
            elif entries:
                entries[-1]["msg"] += "\n" + line
    return entries


def module_from_logger(logger: str) -> Optional[str]:
    m = RE_ADDON_LOGGER.match(logger)
    return m.group(1) if m else None


def analyze_install_log(entries: list) -> dict:
    installed: set = set()
    failed: dict   = {}
    incompatible: set = set()
    loading_now = None

    for e in entries:
        level, logger, msg = e["level"], e["logger"], e["msg"].strip()

        ml = RE_LOADING.search(msg)
        if ml and "odoo.modules" in logger:
            loading_now = ml.group(1)

        mk = RE_MOD_LOADED.search(msg)
        if mk and "odoo.modules" in logger:
            installed.add(mk.group(1))

        mi = RE_INCOMPATIBLE.search(msg)
        if mi:
            incompatible.add(mi.group(1))

        if level in ("ERROR", "CRITICAL") and loading_now:
            if "odoo.modules" in logger or "odoo.registry" in logger:
                if loading_now not in installed and loading_now not in failed:
                    failed[loading_now] = msg[:400]

    return {"installed": installed, "failed": failed, "incompatible": incompatible}


def analyze_one_module_log(entries: list, mod: str, pro_modules: set) -> dict:
    stats = overall = explicit_fail = None
    errors: list = []
    warnings: list = []

    for e in entries:
        level, logger, msg = e["level"], e["logger"], e["msg"].strip()

        if logger == "odoo.tests.stats":
            ms = RE_TEST_STATS.match(msg)
            if ms and ms.group(1) == mod:
                stats = {"tests": int(ms.group(2)), "time": float(ms.group(3))}
            continue

        if logger == "odoo.tests.result":
            mr = RE_OVERALL.search(msg)
            if mr:
                overall = {"failed": int(mr.group(1)), "errors": int(mr.group(2)), "total": int(mr.group(3))}
            continue

        mf = RE_MOD_FAIL.search(msg)
        if mf and level == "ERROR" and "odoo.modules" in logger:
            if mf.group(1) == mod:
                explicit_fail = {"failures": int(mf.group(2)), "errors": int(mf.group(3)), "total": int(mf.group(4))}
            continue

        mfe = RE_FAIL_LINE.match(msg)
        if mfe and level == "ERROR" and "odoo.addons" in logger:
            if module_from_logger(logger) == mod:
                errors.append(f"{mfe.group(1)}: {mfe.group(2).strip().split(chr(10))[0][:300]}")
            continue

        mse = RE_SETUP_ERR.search(msg)
        if mse and level == "ERROR" and "odoo.tests.suite" in logger:
            if mse.group(1) == mod:
                errors.append(msg.strip().split("\n")[0][:300])
            continue

        if level == "WARNING" and mod in pro_modules:
            if module_from_logger(logger) == mod:
                warnings.append(msg[:200])

    return {"stats": stats, "overall": overall, "explicit_fail": explicit_fail,
            "errors": errors, "warnings": warnings}


def analyze_ci_log(ci_log_path: Path, test_modules: list, pro_modules: set) -> tuple:
    """Parse single CI log (all modules in one file).

    Cannot reuse analyze_one_module_log because the global odoo.tests.result
    line (e.g. '41 failed ... of 252 tests') would contaminate every module's
    result. This function detects failures only via module-specific loggers.
    """
    entries = parse_log(ci_log_path)
    install_result = analyze_install_log(entries)

    passed: dict = {}
    failed: dict = {}
    all_warnings: dict = {}

    for mod in test_modules:
        stats = None
        errors: list = []
        warnings: list = []

        for e in entries:
            level, logger, msg = e["level"], e["logger"], e["msg"].strip()

            # Per-module stats: "module_name: N tests Xs"
            if logger == "odoo.tests.stats":
                ms = RE_TEST_STATS.match(msg)
                if ms and ms.group(1) == mod:
                    stats = {"tests": int(ms.group(2)), "time": float(ms.group(3))}
                continue

            # FAIL/ERROR from this module's test code (logger = odoo.addons.MODULE.*)
            mfe = RE_FAIL_LINE.match(msg)
            if mfe and level == "ERROR" and "odoo.addons" in logger:
                if module_from_logger(logger) == mod:
                    errors.append(f"{mfe.group(1)}: {mfe.group(2).strip().split(chr(10))[0][:300]}")
                continue

            # setUpClass error attributed to this module
            mse = RE_SETUP_ERR.search(msg)
            if mse and level == "ERROR" and "odoo.tests.suite" in logger:
                if mse.group(1) == mod:
                    errors.append(msg.strip().split("\n")[0][:300])
                continue

            # Explicit per-module failure summary from Odoo modules loader
            mf = RE_MOD_FAIL.search(msg)
            if mf and level == "ERROR" and "odoo.modules" in logger:
                if mf.group(1) == mod:
                    errors.append(
                        f"Module {mod}: {mf.group(2)} failures, "
                        f"{mf.group(3)} errors of {mf.group(4)} tests"
                    )
                continue

            # Warnings from this module
            if level == "WARNING" and mod in pro_modules:
                if module_from_logger(logger) == mod:
                    warnings.append(msg[:200])

        if warnings:
            all_warnings[mod] = warnings

        if errors:
            f_count = sum(1 for err in errors if err.startswith("FAIL:"))
            e_count = len(errors) - f_count
            failed[mod] = {
                "failures": f_count,
                "errors":   e_count,
                "total":    stats["tests"] if stats else 0,
                "time":     stats["time"]  if stats else None,
                "details":  errors[:15],
            }
        elif stats:
            passed[mod] = {"tests": stats["tests"], "test_time": stats["time"]}

    # Global summary from the one odoo.tests.result line in the CI log
    agg_failed = agg_errors = agg_total = 0
    for e in reversed(entries):
        mr = RE_OVERALL.search(e["msg"])
        if mr:
            agg_failed = int(mr.group(1))
            agg_errors = int(mr.group(2))
            agg_total  = int(mr.group(3))
            break

    overall_result = None
    if agg_total > 0 or agg_failed > 0 or agg_errors > 0:
        overall_result = {"failed": agg_failed, "errors": agg_errors, "total": agg_total}

    test_result = {
        "passed": passed, "failed": failed,
        "warnings": all_warnings, "overall": overall_result,
    }
    return install_result, test_result


def analyze_module_log_dir(modules_dir: Path, pro_modules: set) -> dict:
    passed: dict = {}
    failed: dict = {}
    all_warnings: dict = {}
    agg_failed = agg_errors = agg_total = 0

    for log_file in sorted(modules_dir.glob("*.log")):
        mod = log_file.stem
        r   = analyze_one_module_log(parse_log(log_file), mod, pro_modules)

        stats, overall, explicit = r["stats"], r["overall"], r["explicit_fail"]
        errors, warns = r["errors"], r["warnings"]

        if warns:
            all_warnings[mod] = warns

        has_fail = bool(errors)
        if not has_fail and overall:
            has_fail = overall["failed"] > 0 or overall["errors"] > 0
        if not has_fail and explicit:
            has_fail = explicit["failures"] > 0 or explicit["errors"] > 0

        if has_fail:
            f_count = (explicit or overall or {}).get("failures", 0) or (explicit or overall or {}).get("failed", 0)
            e_count = (explicit or overall or {}).get("errors", 0)
            if not f_count and errors:
                f_count = sum(1 for e in errors if e.startswith("FAIL:"))
                e_count = len(errors) - f_count

            failed[mod] = {
                "failures": f_count,
                "errors":   e_count,
                "total": stats["tests"] if stats else (overall["total"] if overall else 0),
                "time":  stats["time"]  if stats else None,
                "details": errors[:15],
            }
            if overall:
                agg_failed += overall["failed"]
                agg_errors += overall["errors"]
                agg_total  += overall["total"]
        elif stats:
            passed[mod] = {"tests": stats["tests"], "test_time": stats["time"]}
            if overall:
                agg_total += overall["total"]

    overall_result = None
    if agg_total > 0 or agg_failed > 0:
        overall_result = {"failed": agg_failed, "errors": agg_errors, "total": agg_total}

    return {"passed": passed, "failed": failed, "warnings": all_warnings, "overall": overall_result}


# ─── Helpers de formato ───────────────────────────────────────────────────────

def _progress_bar(value: int, total: int, width: int = 20) -> str:
    """Barra de progreso ASCII para markdown."""
    if total == 0:
        return f"`{'─' * width}` 0%"
    pct = value / total
    filled = round(pct * width)
    bar = "█" * filled + "░" * (width - filled)
    return f"`{bar}` {pct:.0%}"


def _badge(text: str, kind: str) -> str:
    """Pseudo-badge en markdown usando texto formateado."""
    icons = {"pass": "✅", "fail": "❌", "warn": "⚠️", "skip": "⏩",
             "lock": "🔒", "incompat": "🚫", "error": "🔴", "info": "ℹ️"}
    return f"{icons.get(kind, '')} **{text}**"


def _fmt_dur(seconds: int) -> str:
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"


# ─── Generación del reporte Markdown ─────────────────────────────────────────

def generate_report(
    install_result: dict,
    test_result: dict,
    all_modules: list,
    test_modules: list,
    not_installable: list,
    module_authors: dict,
    timestamp: str,
    install_dur: int,
    test_dur: int,
    output_path: Path,
) -> None:

    pro_set      = set(all_modules)
    test_set     = set(test_modules)
    not_inst_set = set(not_installable)

    inst_ok            = install_result["installed"]
    inst_fail          = install_result["failed"]
    incompatible       = install_result["incompatible"]
    t_passed           = test_result["passed"]
    t_failed           = test_result["failed"]
    t_warns            = test_result["warnings"]
    overall            = test_result.get("overall")
    pro_failed_install = {m: v for m, v in inst_fail.items() if m in pro_set}
    pro_no_test_dir    = sorted(pro_set - test_set - incompatible)

    total      = len(pro_set) + len(not_inst_set)
    n_inst     = len(pro_set & inst_ok)
    n_incompat = len(incompatible & pro_set)
    n_not_inst = len(not_inst_set)
    n_tp       = len(t_passed)
    n_tf       = len(t_failed)
    n_tw       = len(t_warns)
    n_tested   = n_tp + n_tf

    total_tests = (sum(v["tests"] for v in t_passed.values())
                   + sum(v["total"] for v in t_failed.values()))
    pass_rate   = round(n_tp / n_tested * 100) if n_tested else 0
    test_pass_rate = (round((total_tests - (overall["failed"] + overall["errors"])) / total_tests * 100)
                      if (overall and total_tests) else pass_rate)

    try:
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%d/%m/%Y %H:%M:%S")
    except ValueError:
        dt = timestamp

    lines: list = []
    a = lines.append

    # ── Encabezado ────────────────────────────────────────────────────────────
    a("# 🧪 Odoo Pro v17 — Test Report")
    a("")
    a(f"> **Generado:** {dt} &nbsp;|&nbsp; "
      f"**Instalación:** {_fmt_dur(install_dur)} &nbsp;|&nbsp; "
      f"**Tests:** {_fmt_dur(test_dur)}")
    a("")
    a("---")
    a("")

    # ── KPIs ──────────────────────────────────────────────────────────────────
    a("## 📊 Resumen Ejecutivo")
    a("")
    a("| KPI | Valor | Detalle |")
    a("|-----|:-----:|---------|")
    a(f"| **Módulos descubiertos** | {total} | {len(pro_set)} instalables · {n_not_inst} pendientes migración |")
    a(f"| **Módulos instalados** | {n_inst} / {len(pro_set)} | {len(pro_failed_install)} fallaron · {n_incompat} incompatibles |")
    a(f"| **Módulos con tests** | {n_tested} / {len(test_set)} | {n_tp} pasaron · {n_tf} fallaron |")
    a(f"| **Tests individuales** | {total_tests} | "
      f"{overall['failed'] if overall else 0} assert · {overall['errors'] if overall else 0} excepciones |")
    a(f"| **Tasa de éxito (módulos)** | {pass_rate}% | {_progress_bar(n_tp, n_tested)} |")
    a(f"| **Tasa de éxito (tests)** | {test_pass_rate}% | {_progress_bar(total_tests - (overall['failed'] + overall['errors'] if overall else 0), total_tests)} |")
    a("")

    # ── Estado rápido ─────────────────────────────────────────────────────────
    a("### Estado por categoría")
    a("")
    cats = [
        ("✅ Pasaron",        n_tp,              "módulos con todos los tests en verde"),
        ("❌ Fallaron",       n_tf,              "módulos con fallos o errores"),
        ("⚠️  Con warnings",  n_tw,              "módulos con advertencias"),
        ("⏩ Sin tests",      len(pro_no_test_dir), "módulos sin directorio tests/"),
        ("🔒 No instalables", n_not_inst,        "installable=False — pendientes migración"),
        ("🚫 Incompatibles",  n_incompat,        "versión incompatible con v17"),
        ("🔴 Error install",  len(pro_failed_install), "fallaron durante la instalación"),
    ]
    a("| Estado | Módulos | Descripción |")
    a("|--------|:-------:|-------------|")
    for label, count, desc in cats:
        a(f"| {label} | **{count}** | {desc} |")
    a("")
    a("---")
    a("")

    # ── Tests pasaron ─────────────────────────────────────────────────────────
    a(f"## ✅ Tests Pasaron &nbsp; `{n_tp} módulos`")
    a("")
    if t_passed:
        a("| Módulo | Tests | Tiempo | Autor | Estado |")
        a("|--------|:-----:|:------:|-------|:------:|")
        for mod in sorted(t_passed):
            info    = t_passed[mod]
            w_icon  = " ⚠️" if mod in t_warns else ""
            t_str   = f"{info['test_time']}s" if info["test_time"] is not None else "—"
            author  = module_authors.get(mod, "—")
            badge   = "✅" if mod not in t_warns else "✅⚠️"
            a(f"| `{mod}`{w_icon} | {info['tests']} | {t_str} | {author} | {badge} |")
    else:
        a("> ⚠️  Ningún módulo pasó todos los tests.")
    a("")

    # ── Tests fallaron ────────────────────────────────────────────────────────
    a(f"## ❌ Tests Fallaron &nbsp; `{n_tf} módulos`")
    a("")
    if t_failed:
        for mod in sorted(t_failed):
            info   = t_failed[mod]
            t_str  = f"{info['time']}s" if info.get("time") is not None else "—"
            author = module_authors.get(mod, "—")

            a(f"### ❌ `{mod}`")
            a("")
            a(f"> **Autor:** {author} &nbsp;|&nbsp; "
              f"**Fallos:** {info['failures']} &nbsp;|&nbsp; "
              f"**Errores:** {info['errors']} &nbsp;|&nbsp; "
              f"**Tests:** {info['total']} &nbsp;|&nbsp; "
              f"**Tiempo:** {t_str}")
            a("")
            if info["details"]:
                a("**Detalle de fallos:**")
                a("")
                a("```")
                for d in info["details"][:15]:
                    a(d.split("\n")[0])
                if len(info["details"]) > 15:
                    a(f"… ({len(info['details']) - 15} más)")
                a("```")
            a("")
    else:
        a("> 🎉 **¡Todos los módulos con tests pasaron!**")
        a("")

    a("---")
    a("")

    # ── Fallos de instalación ─────────────────────────────────────────────────
    a(f"## 🔴 Fallos de Instalación &nbsp; `{len(pro_failed_install)} módulos`")
    a("")
    if pro_failed_install:
        a("| Módulo | Causa del fallo |")
        a("|--------|-----------------|")
        for mod in sorted(pro_failed_install):
            reason = pro_failed_install[mod].replace("\n", " ").replace("|", "\\|")[:250]
            a(f"| `{mod}` | {reason} |")
    else:
        a("> ✅ Todos los módulos se instalaron correctamente.")
    a("")

    # ── Incompatibles ─────────────────────────────────────────────────────────
    pro_incompat = sorted(incompatible & pro_set)
    a(f"## 🚫 Versión Incompatible &nbsp; `{len(pro_incompat)} módulos`")
    a("")
    if pro_incompat:
        cols = 4
        a("| " + " | ".join(["Módulo"] * cols) + " |")
        a("|" + "|".join(["-----"] * cols) + "|")
        for i in range(0, len(pro_incompat), cols):
            row = pro_incompat[i:i+cols]
            row += [""] * (cols - len(row))
            a("| " + " | ".join(f"`{m}`" if m else "" for m in row) + " |")
    else:
        a("> ✅ Ningún módulo con versión incompatible.")
    a("")

    # ── No instalables ────────────────────────────────────────────────────────
    not_inst_sorted = sorted(not_inst_set)
    a(f"## 🔒 Pendientes de Migración a v17 &nbsp; `{n_not_inst} módulos`")
    a("")
    a("> Módulos con `installable = False`. Excluidos del proceso de instalación y tests.")
    a("")
    if not_inst_sorted:
        cols = 3
        a("| " + " | ".join(["Módulo"] * cols) + " |")
        a("|" + "|".join(["------"] * cols) + "|")
        for i in range(0, len(not_inst_sorted), cols):
            row = not_inst_sorted[i:i+cols]
            row += [""] * (cols - len(row))
            a("| " + " | ".join(f"`{m}`" if m else "" for m in row) + " |")
    a("")

    # ── Warnings ─────────────────────────────────────────────────────────────
    if t_warns:
        a(f"## ⚠️  Warnings en Tests &nbsp; `{n_tw} módulos`")
        a("")
        for mod in sorted(t_warns):
            msgs = t_warns[mod]
            a(f"<details><summary><code>{mod}</code> — {len(msgs)} warnings</summary>")
            a("")
            a("```text")
            for msg in msgs[:5]:
                a(textwrap.shorten(msg, width=200))
            if len(msgs) > 5:
                a(f"… ({len(msgs) - 5} más)")
            a("```")
            a("</details>")
            a("")

    # ── Sin tests ─────────────────────────────────────────────────────────────
    if pro_no_test_dir:
        a(f"## ⏩ Sin Directorio de Tests &nbsp; `{len(pro_no_test_dir)} módulos`")
        a("")
        cols = 3
        a("| " + " | ".join(["Módulo"] * cols) + " |")
        a("|" + "|".join(["------"] * cols) + "|")
        for i in range(0, len(pro_no_test_dir), cols):
            row = pro_no_test_dir[i:i+cols]
            row += [""] * (cols - len(row))
            a("| " + " | ".join(f"`{m}`" if m else "" for m in row) + " |")
        a("")

    a("---")
    a("")

    # ── Inventario completo ────────────────────────────────────────────────────
    STATUS_MAP = {
        "pass":     ("✅", "PASS"),
        "fail":     ("❌", "FAIL"),
        "warn":     ("⚠️ ", "WARN"),
        "incompat": ("🚫", "INCOMPAT"),
        "inst_fail":("🔴", "INST_FAIL"),
        "not_load": ("⚠️ ", "NOT_LOADED"),
        "no_test":  ("⏩", "NO_TESTS"),
        "no_inst":  ("🔒", "NO_INST"),
    }

    a(f"## 📦 Inventario Completo &nbsp; `{total} módulos`")
    a("")
    a("<details>")
    a("<summary>Expandir inventario completo</summary>")
    a("")
    a("| Estado | Módulo | Autor |")
    a("|:------:|--------|-------|")

    for mod in sorted(all_modules + not_installable):
        author = module_authors.get(mod, "—")
        if mod in not_inst_set:
            icon, label = "🔒", "NO_INST"
        elif mod in t_passed:
            icon, label = ("✅⚠️", "PASS+W") if mod in t_warns else ("✅", "PASS")
        elif mod in t_failed:
            icon, label = "❌", "FAIL"
        elif mod in incompatible:
            icon, label = "🚫", "INCOMPAT"
        elif mod in pro_failed_install:
            icon, label = "🔴", "INST_FAIL"
        elif mod not in inst_ok:
            icon, label = "⚠️ ", "NOT_LOADED"
        else:
            icon, label = "⏩", "NO_TESTS"

        a(f"| {icon} `{label}` | `{mod}` | {author} |")

    a("")
    a("</details>")
    a("")

    # ── Footer ────────────────────────────────────────────────────────────────
    a("---")
    a("")
    a(f"*Generado automáticamente por `run_tests.sh` · Odoo Pro v17 · {dt}*")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  ✅ Markdown  → {output_path}")


# ─── Generación PDF ──────────────────────────────────────────────────────────

CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       font-size: 13px; line-height: 1.6; color: #1a1a2e; max-width: 1100px;
       margin: 0 auto; padding: 20px 30px; }
h1   { color: #0f3460; border-bottom: 3px solid #e94560; padding-bottom: 8px; font-size: 24px; }
h2   { color: #16213e; border-bottom: 1px solid #ddd; padding-bottom: 4px;
       margin-top: 28px; font-size: 17px; }
h3   { color: #0f3460; font-size: 14px; margin-top: 18px; }
table { border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 12px; }
th   { background: #0f3460; color: #fff; padding: 7px 10px; text-align: left; }
td   { padding: 5px 10px; border-bottom: 1px solid #eee; }
tr:nth-child(even) { background: #f8f9fa; }
tr:hover { background: #e8f4f8; }
code { background: #f0f4f8; padding: 1px 5px; border-radius: 3px;
       font-family: 'Fira Code', 'Consolas', monospace; font-size: 11px; color: #c7254e; }
pre  { background: #1e2a38; color: #abb2bf; padding: 12px 16px; border-radius: 6px;
       overflow-x: auto; font-size: 11px; line-height: 1.5; }
pre code { background: transparent; color: inherit; padding: 0; }
blockquote { border-left: 4px solid #e94560; margin: 10px 0; padding: 8px 16px;
             background: #fff5f5; color: #555; border-radius: 0 4px 4px 0; }
details { border: 1px solid #ddd; border-radius: 6px; padding: 8px 12px; margin: 10px 0; }
summary { cursor: pointer; font-weight: 600; color: #0f3460; }
hr      { border: none; border-top: 2px solid #e94560; margin: 20px 0; }
@media print {
  body { padding: 10px 20px; }
  h2 { page-break-before: auto; }
}
"""


def generate_pdf(md_path: Path, pdf_path: Path) -> bool:
    """Convierte Markdown → HTML → PDF usando pandoc + Chrome headless."""
    html_path = md_path.with_suffix(".html")

    # 1. pandoc: md → html5 standalone con CSS embebido
    pandoc = shutil.which("pandoc")
    if not pandoc:
        print("  ⚠️  pandoc no encontrado — saltando PDF")
        return False

    css_file = md_path.parent / ".report_style.css"
    css_file.write_text(CSS, encoding="utf-8")

    try:
        subprocess.run(
            [pandoc, str(md_path),
             "-f", "gfm+raw_html",
             "-t", "html5",
             "--standalone",
             "--metadata", f"title=Odoo Pro v17 — Test Report",
             "--css", str(css_file),
             "-o", str(html_path)],
            check=True, capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"  ❌ pandoc error: {e.stderr.decode()[:200]}")
        return False

    # 2. Chrome headless: html → pdf
    chrome_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        shutil.which("google-chrome"),
        shutil.which("chromium"),
        shutil.which("chromium-browser"),
    ]
    chrome = next((c for c in chrome_candidates if c and Path(c).exists()), None)

    if not chrome:
        print("  ⚠️  Chrome/Chromium no encontrado — saltando PDF")
        css_file.unlink(missing_ok=True)
        return False

    try:
        subprocess.run(
            [chrome,
             "--headless",
             "--disable-gpu",
             "--no-sandbox",
             "--disable-dev-shm-usage",
             f"--print-to-pdf={pdf_path}",
             "--print-to-pdf-no-header",
             str(html_path.resolve())],
            check=True, capture_output=True, timeout=60,
        )
        print(f"  ✅ PDF       → {pdf_path}")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        print(f"  ❌ Chrome PDF error: {e}")
        return False
    finally:
        html_path.unlink(missing_ok=True)
        css_file.unlink(missing_ok=True)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    p = argparse.ArgumentParser(description="Genera reporte de tests Odoo Pro v17")
    # Modo CI: un solo log con todos los módulos
    p.add_argument("--ci-log",           type=Path,   default=None,
                   help="Log único del modo --ci (reemplaza --install-log y --modules-log-dir)")
    # Modo debug: logs separados por módulo
    p.add_argument("--install-log",      type=Path,   default=None)
    p.add_argument("--modules-log-dir",  type=Path,   default=None)
    p.add_argument("--modules-file",     required=True, type=Path)
    p.add_argument("--output",           required=True, type=Path)
    p.add_argument("--timestamp",        required=True)
    p.add_argument("--install-duration", required=True, type=int)
    p.add_argument("--test-duration",    required=True, type=int)
    p.add_argument("--no-pdf",           action="store_true")
    args = p.parse_args()

    ci_mode = args.ci_log is not None

    if not ci_mode and (args.install_log is None or args.modules_log_dir is None):
        p.error("Sin --ci-log se requieren --install-log y --modules-log-dir")

    all_modules: list     = []
    test_modules: list    = []
    not_installable: list = []
    module_authors: dict  = {}

    if args.modules_file.exists():
        for line in args.modules_file.read_text().splitlines():
            if line.startswith("ALL_MODULES="):
                all_modules = [m for m in line.split("=", 1)[1].split(",") if m]
            elif line.startswith("TEST_MODULES="):
                test_modules = [m for m in line.split("=", 1)[1].split(",") if m]
            elif line.startswith("NOT_INSTALLABLE="):
                not_installable = [m for m in line.split("=", 1)[1].split(",") if m]
            elif line.startswith("MODULE_AUTHORS="):
                for entry in line.split("=", 1)[1].split(","):
                    if ":" in entry:
                        mod, author = entry.split(":", 1)
                        if mod:
                            module_authors[mod] = author.strip()

    if ci_mode:
        print(f"Modo CI: parseando log único {args.ci_log}...")
        install_result, test_result = analyze_ci_log(
            args.ci_log, test_modules, set(all_modules)
        )
    else:
        print("Parseando log de instalación...")
        install_result = analyze_install_log(parse_log(args.install_log))
        print(f"Parseando logs de módulos en {args.modules_log_dir}...")
        test_result = analyze_module_log_dir(args.modules_log_dir, set(all_modules))

    n_p, n_f = len(test_result["passed"]), len(test_result["failed"])
    print(f"  → {n_p} pasaron · {n_f} fallaron")

    print("Generando reporte...")
    generate_report(
        install_result=install_result,
        test_result=test_result,
        all_modules=all_modules,
        test_modules=test_modules,
        not_installable=not_installable,
        module_authors=module_authors,
        timestamp=args.timestamp,
        install_dur=args.install_duration,
        test_dur=args.test_duration,
        output_path=args.output,
    )

    if not args.no_pdf:
        print("Generando PDF...")
        pdf_path = args.output.with_suffix(".pdf")
        generate_pdf(args.output, pdf_path)


if __name__ == "__main__":
    main()
