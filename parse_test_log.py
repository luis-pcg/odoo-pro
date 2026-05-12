#!/usr/bin/env python3
"""parse_test_log.py — Parsea logs de Odoo 19 y genera reporte Markdown"""

import argparse
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── Formato de línea de log ──────────────────────────────────────────────────
LOG_LINE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+"
    r"(?P<pid>\d+)\s+"
    r"(?P<level>INFO|WARNING|ERROR|CRITICAL|DEBUG)\s+"
    r"(?P<db>\S+)\s+"
    r"(?P<logger>\S+):\s*"
    r"(?P<msg>.*)$"
)

# ─── Patrones de instalación ──────────────────────────────────────────────────
RE_LOADING = re.compile(r"Loading module (\S+)\s+\(")
RE_MOD_LOADED = re.compile(r"Module (\S+) loaded in ([\d.]+)s")
RE_INCOMPATIBLE = re.compile(r"The module (\S+) has an incompatible version")

# ─── Patrones de tests ────────────────────────────────────────────────────────

# "account_multi_journal_payment: 6 tests 0.86s ..."  (odoo.tests.stats logger)
RE_TEST_STATS = re.compile(r"^(\S+): (\d+) tests ([\d.]+)s")

# "1 failed, 2 error(s) of 10 tests ..."  (odoo.tests.result logger)
RE_OVERALL_RESULT = re.compile(r"(\d+) failed, (\d+) error\(s\) of (\d+) tests")

# "Module l10n_do_sale: 3 failures, 0 errors of 6 tests"  (odoo.modules.loading, ERROR)
RE_MOD_FAIL = re.compile(r"Module (\S+): (\d+) failures, (\d+) errors of (\d+) tests")

# "FAIL: TestClass.method" / "ERROR: TestClass.method"  (odoo.addons.*.tests.* at ERROR)
# No $ anchor: msg may have "\nTraceback..." appended
RE_TEST_FAIL_LINE = re.compile(r"^(FAIL|ERROR): (.+)")

# "ERROR: setUpClass (odoo.addons.MODULE.tests.FILE.Class)"  (odoo.tests.suite at ERROR)
RE_SETUP_ERR = re.compile(r"ERROR: setUpClass \(odoo\.addons\.([^.]+)\.")

# logger "odoo.addons.MODULE.*" → extraer MODULE
RE_ADDON_LOGGER = re.compile(r"^odoo\.addons\.([^.]+)\.")


# ─── Helpers ──────────────────────────────────────────────────────────────────


def parse_log(path: Path):
    entries = []
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


# ─── Análisis de log de instalación ──────────────────────────────────────────


def analyze_install_log(entries):
    installed = set()
    failed = {}
    incompatible = set()
    loading_now = None

    for e in entries:
        level = e["level"]
        logger = e["logger"]
        msg = e["msg"].strip()

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

    return {
        "installed": installed,
        "failed": failed,
        "incompatible": incompatible,
    }


# ─── Análisis de log de un módulo individual ─────────────────────────────────


def analyze_one_module_log(entries, mod: str, pro_modules: set):
    """
    Analiza el log de UNA ejecución de tests de un módulo específico.
    Retorna dict con: stats, overall, errors (lista), warnings (lista)
    """
    stats = None
    overall = None
    errors = []
    warnings = []
    explicit_fail = None

    for e in entries:
        level = e["level"]
        logger = e["logger"]
        msg = e["msg"].strip()

        # Stats del módulo (odoo.tests.stats)
        if logger == "odoo.tests.stats":
            ms = RE_TEST_STATS.match(msg)
            if ms and ms.group(1) == mod:
                stats = {"tests": int(ms.group(2)), "time": float(ms.group(3))}
            continue

        # Resultado global de la ejecución (odoo.tests.result)
        if logger == "odoo.tests.result":
            mr = RE_OVERALL_RESULT.search(msg)
            if mr:
                overall = {
                    "failed": int(mr.group(1)),
                    "errors": int(mr.group(2)),
                    "total": int(mr.group(3)),
                }
            continue

        # Resumen explícito por módulo (odoo.modules.loading)
        mf = RE_MOD_FAIL.search(msg)
        if mf and level == "ERROR" and "odoo.modules" in logger:
            if mf.group(1) == mod:
                explicit_fail = {
                    "failures": int(mf.group(2)),
                    "errors": int(mf.group(3)),
                    "total": int(mf.group(4)),
                }
            continue

        # FAIL:/ERROR: de logger de addon tests
        mfe = RE_TEST_FAIL_LINE.match(msg)
        if mfe and level == "ERROR" and "odoo.addons" in logger:
            src = module_from_logger(logger)
            if src == mod:
                first_line = mfe.group(2).strip().split("\n")[0][:300]
                errors.append(f"{mfe.group(1)}: {first_line}")
            continue

        # ERROR: setUpClass
        mse = RE_SETUP_ERR.search(msg)
        if mse and level == "ERROR" and "odoo.tests.suite" in logger:
            if mse.group(1) == mod:
                errors.append(msg.strip().split("\n")[0][:300])
            continue

        # Warnings del módulo
        if level == "WARNING" and mod in pro_modules:
            src = module_from_logger(logger)
            if src == mod:
                warnings.append(msg[:200])

    return {
        "stats": stats,
        "overall": overall,
        "explicit_fail": explicit_fail,
        "errors": errors,
        "warnings": warnings,
    }


# ─── Análisis del directorio de logs por módulo ───────────────────────────────


def analyze_module_log_dir(modules_dir: Path, pro_modules: set):
    """
    Lee test_logs/modules/MODULE.log para cada módulo.
    Retorna passed, failed, warnings, overall agregado.
    """
    passed = {}
    failed = {}
    all_warnings = {}
    agg_failed = 0
    agg_errors = 0
    agg_total = 0

    for log_file in sorted(modules_dir.glob("*.log")):
        mod = log_file.stem
        entries = parse_log(log_file)
        r = analyze_one_module_log(entries, mod, pro_modules)

        stats = r["stats"]
        overall = r["overall"]
        explicit = r["explicit_fail"]
        errors = r["errors"]
        warns = r["warnings"]

        if warns:
            all_warnings[mod] = warns

        # Determinar si falló
        has_fail = bool(errors)
        if not has_fail and overall:
            has_fail = overall["failed"] > 0 or overall["errors"] > 0
        if not has_fail and explicit:
            has_fail = explicit["failures"] > 0 or explicit["errors"] > 0

        if has_fail:
            # Contar failures vs errors
            if explicit:
                f_count = explicit["failures"]
                e_count = explicit["errors"]
            elif overall:
                f_count = overall["failed"]
                e_count = overall["errors"]
            else:
                f_count = sum(1 for e in errors if e.startswith("FAIL:"))
                e_count = len(errors) - f_count

            failed[mod] = {
                "failures": f_count,
                "errors": e_count,
                "total": stats["tests"] if stats else (overall["total"] if overall else 0),
                "time": stats["time"] if stats else None,
                "details": errors[:15],
            }
            if overall:
                agg_failed += overall["failed"]
                agg_errors += overall["errors"]
                agg_total += overall["total"]
        elif stats:
            passed[mod] = {
                "tests": stats["tests"],
                "test_time": stats["time"],
            }
            if overall:
                agg_total += overall["total"]
        # else: no stats → módulo sin tests (no se corrieron)

    overall_result = None
    if agg_total > 0 or agg_failed > 0:
        overall_result = {
            "failed": agg_failed,
            "errors": agg_errors,
            "total": agg_total,
        }

    return {
        "passed": passed,
        "failed": failed,
        "warnings": all_warnings,
        "overall": overall_result,
    }


# ─── Generación del reporte ───────────────────────────────────────────────────


def generate_report(
    install_result,
    test_result,
    all_modules: list,
    test_modules: list,
    timestamp: str,
    install_dur: int,
    test_dur: int,
    output_path: Path,
):
    pro_set = set(all_modules)
    test_set = set(test_modules)

    inst_ok = install_result["installed"]
    inst_fail = install_result["failed"]
    incompatible = install_result["incompatible"]

    t_passed = test_result["passed"]
    t_failed = test_result["failed"]
    t_warns = test_result["warnings"]
    overall = test_result.get("overall")

    pro_installed = sorted(pro_set & inst_ok)
    pro_failed_install = {m: v for m, v in inst_fail.items() if m in pro_set}
    pro_no_test_dir = sorted(pro_set - test_set - incompatible)

    total = len(pro_set)
    n_inst = len(pro_installed)
    n_incompat = len(incompatible & pro_set)
    n_tp = len(t_passed)
    n_tf = len(t_failed)
    n_tw = len(t_warns)

    # Total tests: suma de stats o de overall agregado
    if overall:
        total_tests = overall["total"] + sum(v["total"] for v in t_failed.values())
        # Recompute: total = passed tests + failed tests
        total_tests = (
            sum(v["tests"] for v in t_passed.values())
            + sum(v["total"] for v in t_failed.values())
        )
    else:
        total_tests = sum(v["tests"] for v in t_passed.values()) + sum(
            v["total"] for v in t_failed.values()
        )

    try:
        dt = datetime.strptime(timestamp, "%Y%m%d_%H%M%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        dt = timestamp

    lines = []
    a = lines.append

    a("# Odoo Pro v19 — Reporte de Tests")
    a("")
    a(f"> Generado: {dt}")
    a("")

    # ── Resumen ───────────────────────────────────────────────────────────────
    a("## Resumen")
    a("")
    a("| Métrica | Valor |")
    a("|---------|-------|")
    a(f"| Módulos pro descubiertos | {total} |")
    a(f"| Instalados correctamente | {n_inst} |")
    a(f"| Versión incompatible (no instalables) | {n_incompat} |")
    a(f"| Fallaron instalación | {len(pro_failed_install)} |")
    a(f"| Módulos pro con tests | {len(test_set)} |")
    a(f"| Módulos con tests corridos | {n_tp + n_tf} |")
    a(f"| Tests individuales corridos | {total_tests} |")
    if overall:
        a(f"| ↳ Fallaron (assert) | {overall['failed']} |")
        a(f"| ↳ Errores (excepción) | {overall['errors']} |")
    a(f"| ✅ Módulos — todos los tests pasaron | {n_tp} |")
    a(f"| ❌ Módulos — tests fallaron | {n_tf} |")
    a(f"| ⚠️  Módulos con warnings en tests | {n_tw} |")
    a(f"| ⏩ Módulos pro sin directorio tests/ | {len(pro_no_test_dir)} |")
    a(f"| Tiempo fase instalación | {install_dur}s ({install_dur // 60}m {install_dur % 60}s) |")
    a(f"| Tiempo fase tests | {test_dur}s ({test_dur // 60}m {test_dur % 60}s) |")
    a("")

    # ── Tests pasaron ─────────────────────────────────────────────────────────
    a(f"## ✅ Tests pasaron ({n_tp} módulos)")
    a("")
    if t_passed:
        a("| Módulo | Tests | Tiempo |")
        a("|--------|:-----:|:------:|")
        for mod in sorted(t_passed):
            info = t_passed[mod]
            w_tag = " ⚠️" if mod in t_warns else ""
            time_str = f"{info['test_time']}s" if info["test_time"] is not None else "-"
            a(f"| `{mod}`{w_tag} | {info['tests']} | {time_str} |")
    else:
        a("_Ninguno_")
    a("")

    # ── Tests fallaron ────────────────────────────────────────────────────────
    a(f"## ❌ Tests fallaron ({n_tf} módulos)")
    a("")
    if t_failed:
        for mod in sorted(t_failed):
            info = t_failed[mod]
            time_str = f"{info['time']}s" if info.get("time") is not None else "-"
            a(f"### `{mod}`")
            a("")
            a(
                f"- Failures: **{info['failures']}** | Errors: **{info['errors']}** "
                f"| Tests: {info['total']} | Tiempo: {time_str}"
            )
            if info["details"]:
                a("")
                a("```")
                for d in info["details"][:15]:
                    a(d.split("\n")[0])
                if len(info["details"]) > 15:
                    a(f"... ({len(info['details']) - 15} más)")
                a("```")
            a("")
    else:
        a("_Ninguno_ 🎉")
        a("")

    # ── Fallaron instalación ──────────────────────────────────────────────────
    a(f"## 🔴 Fallaron instalación ({len(pro_failed_install)} módulos pro)")
    a("")
    if pro_failed_install:
        a("| Módulo | Error |")
        a("|--------|-------|")
        for mod in sorted(pro_failed_install):
            reason = pro_failed_install[mod].replace("\n", " ")[:200]
            a(f"| `{mod}` | {reason} |")
    else:
        a("_Todos los módulos pro se instalaron correctamente_ ✅")
    a("")

    # ── Versión incompatible ──────────────────────────────────────────────────
    pro_incompat_sorted = sorted(incompatible & pro_set)
    a(f"## 🚫 Versión incompatible ({len(pro_incompat_sorted)} módulos pro)")
    a("")
    if pro_incompat_sorted:
        a("| Módulo |")
        a("|--------|")
        for mod in pro_incompat_sorted:
            a(f"| `{mod}` |")
    else:
        a("_Ninguno_")
    a("")

    # ── Warnings ─────────────────────────────────────────────────────────────
    a(f"## ⚠️  Warnings en tests ({n_tw} módulos)")
    a("")
    if t_warns:
        for mod in sorted(t_warns):
            msgs = t_warns[mod]
            a("<details>")
            a(f"<summary><code>{mod}</code> ({len(msgs)} warnings)</summary>")
            a("")
            a("```")
            for msg in msgs[:5]:
                a(msg)
            if len(msgs) > 5:
                a(f"... ({len(msgs) - 5} más)")
            a("```")
            a("")
            a("</details>")
            a("")
    else:
        a("_Sin warnings_")
        a("")

    # ── Sin tests ─────────────────────────────────────────────────────────────
    a(f"## ⏩ Módulos pro sin directorio tests/ ({len(pro_no_test_dir)})")
    a("")
    if pro_no_test_dir:
        cols = 3
        rows = [pro_no_test_dir[i : i + cols] for i in range(0, len(pro_no_test_dir), cols)]
        a("| | | |")
        a("|---|---|---|")
        for row in rows:
            padded = row + [""] * (cols - len(row))
            cells = " | ".join(f"`{c}`" if c else "" for c in padded)
            a(f"| {cells} |")
    a("")

    # ── Lista completa de módulos pro ─────────────────────────────────────────
    a(f"## 📦 Módulos pro descubiertos ({total})")
    a("")
    a("<details>")
    a("<summary>Ver lista completa con estado</summary>")
    a("")
    a("```")
    for mod in sorted(all_modules):
        if mod in t_passed:
            status = "✅ PASS      "
        elif mod in t_failed:
            status = "❌ FAIL      "
        elif mod in incompatible:
            status = "🚫 INCOMPAT  "
        elif mod in pro_failed_install:
            status = "🔴 INST_FAIL "
        elif mod not in inst_ok:
            status = "⚠️  NOT_LOADED"
        else:
            status = "⏩ NO_TESTS  "
        a(f"{status}  {mod}")
    a("```")
    a("")
    a("</details>")
    a("")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Reporte guardado en: {output_path}")


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--install-log", required=True, type=Path)
    p.add_argument("--modules-log-dir", required=True, type=Path)
    p.add_argument("--modules-file", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--timestamp", required=True)
    p.add_argument("--install-duration", required=True, type=int)
    p.add_argument("--test-duration", required=True, type=int)
    args = p.parse_args()

    all_modules = []
    test_modules = []
    if args.modules_file.exists():
        for line in args.modules_file.read_text().splitlines():
            if line.startswith("ALL_MODULES="):
                all_modules = [m for m in line.split("=", 1)[1].split(",") if m]
            elif line.startswith("TEST_MODULES="):
                test_modules = [m for m in line.split("=", 1)[1].split(",") if m]

    pro_set = set(all_modules)

    print("Parseando log de instalación...")
    install_entries = parse_log(args.install_log)
    install_result = analyze_install_log(install_entries)

    print(f"Parseando logs por módulo en {args.modules_log_dir}...")
    test_result = analyze_module_log_dir(args.modules_log_dir, pro_set)

    n_pass = len(test_result["passed"])
    n_fail = len(test_result["failed"])
    print(f"  → {n_pass} pasaron, {n_fail} fallaron")

    print("Generando reporte...")
    generate_report(
        install_result=install_result,
        test_result=test_result,
        all_modules=all_modules,
        test_modules=test_modules,
        timestamp=args.timestamp,
        install_dur=args.install_duration,
        test_dur=args.test_duration,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
