#!/usr/bin/env python3
"""
parse_test_log.py — Parsea logs de Odoo y genera reporte Markdown
"""
import argparse
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


# ─── Patrones de log de Odoo ──────────────────────────────────────────────────
# Formato: YYYY-MM-DD HH:MM:SS,mmm PID LEVEL DBNAME logger: message
LOG_LINE = re.compile(
    r'^(?P<ts>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d+)\s+'
    r'(?P<pid>\d+)\s+'
    r'(?P<level>INFO|WARNING|ERROR|CRITICAL|DEBUG)\s+'
    r'(?P<db>\S+)\s+'
    r'(?P<logger>\S+):\s*'
    r'(?P<msg>.*)$'
)

# Módulo desde logger: odoo.addons.MODULE.tests.* o odoo.addons.MODULE.*
ADDON_LOGGER = re.compile(r'^odoo\.addons\.([^.]+)\.')

# Instalación de módulos
RE_LOADING     = re.compile(r"loading module '?([^''\s]+)'?", re.I)
RE_LOADED_OK   = re.compile(r"(\d+) modules? loaded", re.I)
RE_LOAD_FAIL   = re.compile(r"Module '?([^''\s]+)'? failed|failed to install '?([^''\s]+)'?", re.I)
RE_INIT_FAIL   = re.compile(r"[Ee]rror.*module '?([^''\s]+)'?|'?([^''\s]+)'?.*could not be installed", re.I)

# Tests
RE_RAN         = re.compile(r'Ran (\d+) tests? in ([\d.]+)s')
RE_OK          = re.compile(r'^OK\s*$')
RE_FAILED      = re.compile(r'^FAILED\s*\((.+)\)$')
RE_ERROR_LINE  = re.compile(r'^(ERROR|FAIL):\s+(.+)$')
RE_TEST_START  = re.compile(r'Starting\s+(\S+)')


def parse_log(log_path: Path):
    """Parsea un archivo de log de Odoo. Retorna lista de dicts con campos parsed."""
    entries = []
    if not log_path.exists():
        return entries
    with open(log_path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.rstrip('\n')
            m = LOG_LINE.match(line)
            if m:
                entries.append(m.groupdict())
            elif entries:
                # Línea de continuación (stack trace, etc.)
                entries[-1]['msg'] += '\n' + line
    return entries


def extract_module_from_logger(logger: str) -> str | None:
    m = ADDON_LOGGER.match(logger)
    return m.group(1) if m else None


def analyze_install_log(entries: list) -> dict:
    """
    Retorna:
      installed: set de módulos instalados OK
      failed:    dict {module: reason}
      warnings:  dict {module: [msg, ...]}
    """
    installed = set()
    failed = {}
    warnings = defaultdict(list)
    loading_current = None

    for e in entries:
        level  = e['level']
        logger = e['logger']
        msg    = e['msg'].strip()

        # Detectar qué módulo se estaba cargando
        m = RE_LOADING.search(msg)
        if m and 'odoo.modules' in logger:
            loading_current = m.group(1)

        # Módulo cargado OK — Odoo imprime "X modules loaded in Ys"
        if RE_LOADED_OK.search(msg) and 'odoo.modules' in logger:
            # El módulo actual se instaló; la confirmación global se
            # procesa después, así que marcamos el último que se cargó.
            if loading_current:
                installed.add(loading_current)

        # Fallo de instalación explícito
        mf = RE_LOAD_FAIL.search(msg)
        if mf and level in ('ERROR', 'CRITICAL'):
            mod = mf.group(1) or mf.group(2)
            if mod:
                failed[mod] = msg[:300]
            continue

        # ERROR genérico durante carga de módulo
        if level in ('ERROR', 'CRITICAL') and loading_current:
            if loading_current not in failed:
                failed[loading_current] = msg[:300]

        # WARNING durante instalación
        if level == 'WARNING':
            mod = extract_module_from_logger(logger) or loading_current
            if mod:
                warnings[mod].append(msg[:200])

    return {
        'installed': installed,
        'failed':    failed,
        'warnings':  dict(warnings),
    }


def analyze_test_log(entries: list) -> dict:
    """
    Retorna por módulo:
      passed:   {module: {'ran': N, 'time': X}}
      failed:   {module: {'ran': N, 'errors': [str]}}
      warnings: {module: [str]}
      skipped:  set de módulos con 0 tests
    """
    passed   = {}
    failed   = {}
    warnings = defaultdict(list)
    skipped  = set()

    # Acumular por módulo+logger para manejar múltiples archivos de test
    module_ran    = defaultdict(int)
    module_time   = defaultdict(float)
    module_errors = defaultdict(list)
    module_status = {}  # 'ok' | 'failed'

    for e in entries:
        level  = e['level']
        logger = e['logger']
        msg    = e['msg'].strip()

        mod = extract_module_from_logger(logger)
        if not mod:
            continue

        # "Ran N tests in Xs"
        m = RE_RAN.search(msg)
        if m:
            module_ran[mod]  += int(m.group(1))
            module_time[mod] += float(m.group(2))
            continue

        # "OK"
        if RE_OK.match(msg):
            if mod not in module_status:
                module_status[mod] = 'ok'
            continue

        # "FAILED (failures=N, errors=M)"
        mf = RE_FAILED.match(msg)
        if mf:
            module_status[mod] = 'failed'
            module_errors[mod].append(f"FAILED ({mf.group(1)})")
            continue

        # "FAIL: TestClass.method" / "ERROR: TestClass.method"
        me = RE_ERROR_LINE.match(msg)
        if me:
            module_errors[mod].append(f"{me.group(1)}: {me.group(2)[:200]}")
            continue

        # WARNING
        if level == 'WARNING':
            warnings[mod].append(msg[:200])

        # ERROR en logger de tests (no FAIL: línea) → capturar
        if level == 'ERROR' and 'tests' in logger:
            module_errors[mod].append(msg[:200])

    # Consolidar resultados
    all_mods = set(module_ran) | set(module_status) | set(module_errors)

    for mod in all_mods:
        ran = module_ran.get(mod, 0)
        status = module_status.get(mod, 'ok' if not module_errors.get(mod) else 'failed')

        if ran == 0 and not module_errors.get(mod):
            skipped.add(mod)
            continue

        if status == 'ok' and not module_errors.get(mod):
            passed[mod] = {
                'ran':  ran,
                'time': round(module_time.get(mod, 0.0), 2),
            }
        else:
            failed[mod] = {
                'ran':    ran,
                'time':   round(module_time.get(mod, 0.0), 2),
                'errors': module_errors.get(mod, []),
            }

    return {
        'passed':   passed,
        'failed':   failed,
        'warnings': dict(warnings),
        'skipped':  skipped,
    }


def generate_report(
    install_result: dict,
    test_result:    dict,
    all_modules:    list,
    test_modules:   list,
    timestamp:      str,
    install_dur:    int,
    test_dur:       int,
    output_path:    Path,
):
    installed_ok  = install_result['installed']
    install_fail  = install_result['failed']
    install_warns = install_result['warnings']

    tests_passed  = test_result['passed']
    tests_failed  = test_result['failed']
    test_warns    = test_result['warnings']
    tests_skipped = test_result['skipped']

    # Módulos instalados que no tienen tests
    no_tests = sorted(set(all_modules) - set(test_modules) - set(install_fail))

    # Totales
    total_all    = len(all_modules)
    total_inst   = len(installed_ok) if installed_ok else total_all - len(install_fail)
    total_fail_i = len(install_fail)
    total_tp     = len(tests_passed)
    total_tf     = len(tests_failed)
    total_tw     = len(test_warns)
    total_ran    = sum(v['ran'] for v in tests_passed.values()) + \
                   sum(v['ran'] for v in tests_failed.values())

    dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')

    lines = []
    a = lines.append

    a(f"# Odoo Pro v19 — Reporte de Tests")
    a(f"")
    a(f"> Generado: {dt}")
    a(f"")
    a(f"## Resumen")
    a(f"")
    a(f"| Métrica | Valor |")
    a(f"|---------|-------|")
    a(f"| Total módulos descubiertos | {total_all} |")
    a(f"| Instalados correctamente | {total_inst} |")
    a(f"| Fallaron instalación | {total_fail_i} |")
    a(f"| Módulos con tests | {len(test_modules)} |")
    a(f"| Tests corridos (total assertions) | {total_ran} |")
    a(f"| ✅ Módulos — tests pasaron | {total_tp} |")
    a(f"| ❌ Módulos — tests fallaron | {total_tf} |")
    a(f"| ⚠️  Módulos con warnings | {total_tw} |")
    a(f"| ⏩ Sin tests | {len(no_tests)} |")
    a(f"| Tiempo instalación | {install_dur}s ({install_dur//60}m {install_dur%60}s) |")
    a(f"| Tiempo tests | {test_dur}s ({test_dur//60}m {test_dur%60}s) |")
    a(f"")

    # ── Tests pasados ──────────────────────────────────────────────────────────
    a(f"## ✅ Tests pasaron ({total_tp} módulos)")
    a(f"")
    if tests_passed:
        a(f"| Módulo | Tests corridos | Tiempo |")
        a(f"|--------|----------------|--------|")
        for mod in sorted(tests_passed):
            info = tests_passed[mod]
            warn_tag = " ⚠️" if mod in test_warns else ""
            a(f"| `{mod}`{warn_tag} | {info['ran']} | {info['time']}s |")
    else:
        a(f"_Ninguno_")
    a(f"")

    # ── Tests fallados ─────────────────────────────────────────────────────────
    a(f"## ❌ Tests fallaron ({total_tf} módulos)")
    a(f"")
    if tests_failed:
        for mod in sorted(tests_failed):
            info = tests_failed[mod]
            a(f"### `{mod}`")
            a(f"")
            a(f"- Tests corridos: {info['ran']}")
            a(f"- Tiempo: {info['time']}s")
            if info['errors']:
                a(f"- Errores:")
                a(f"")
                a(f"```")
                for err in info['errors'][:10]:
                    a(err)
                if len(info['errors']) > 10:
                    a(f"... ({len(info['errors']) - 10} más)")
                a(f"```")
            a(f"")
    else:
        a(f"_Ninguno_ 🎉")
        a(f"")

    # ── Fallaron instalación ───────────────────────────────────────────────────
    a(f"## 🔴 Fallaron instalación ({total_fail_i} módulos)")
    a(f"")
    if install_fail:
        a(f"| Módulo | Error |")
        a(f"|--------|-------|")
        for mod in sorted(install_fail):
            reason = install_fail[mod].replace('\n', ' ')[:150]
            a(f"| `{mod}` | {reason} |")
    else:
        a(f"_Todos los módulos se instalaron correctamente_ ✅")
    a(f"")

    # ── Warnings ──────────────────────────────────────────────────────────────
    all_warn_mods = sorted(set(list(test_warns.keys()) + list(install_warns.keys())))
    a(f"## ⚠️  Warnings ({len(all_warn_mods)} módulos)")
    a(f"")
    if all_warn_mods:
        for mod in all_warn_mods:
            msgs = []
            if mod in install_warns:
                msgs += [f"[install] {m}" for m in install_warns[mod][:3]]
            if mod in test_warns:
                msgs += [f"[test] {m}" for m in test_warns[mod][:3]]
            a(f"<details>")
            a(f"<summary><code>{mod}</code> ({len(msgs)} warnings)</summary>")
            a(f"")
            a(f"```")
            for msg in msgs:
                a(msg)
            a(f"```")
            a(f"</details>")
            a(f"")
    else:
        a(f"_Sin warnings_")
        a(f"")

    # ── Sin tests ──────────────────────────────────────────────────────────────
    a(f"## ⏩ Módulos sin tests ({len(no_tests)})")
    a(f"")
    if no_tests:
        # Mostrar en columnas para no ocupar tanto espacio
        cols = 3
        rows = [no_tests[i:i+cols] for i in range(0, len(no_tests), cols)]
        a(f"| | | |")
        a(f"|---|---|---|")
        for row in rows:
            padded = row + [''] * (cols - len(row))
            a(f"| `{'` | `'.join(p) if p else ''}` | `{padded[1]}` | `{padded[2]}` |"
              .replace("| `` |", "| |"))
    a(f"")

    # ── Lista completa de módulos instalados ───────────────────────────────────
    a(f"## 📦 Todos los módulos descubiertos ({total_all})")
    a(f"")
    a(f"<details>")
    a(f"<summary>Ver lista completa</summary>")
    a(f"")
    a(f"```")
    for mod in sorted(all_modules):
        status = "✅" if mod in tests_passed else \
                 "❌" if mod in tests_failed else \
                 "🔴" if mod in install_fail else \
                 "⏩"
        a(f"{status}  {mod}")
    a(f"```")
    a(f"")
    a(f"</details>")
    a(f"")

    output_path.write_text('\n'.join(lines), encoding='utf-8')
    print(f"Reporte guardado en: {output_path}")


def main():
    p = argparse.ArgumentParser(description='Parser de logs de Odoo → reporte MD')
    p.add_argument('--install-log',       required=True, type=Path)
    p.add_argument('--test-log',          required=True, type=Path)
    p.add_argument('--modules-file',      required=True, type=Path)
    p.add_argument('--output',            required=True, type=Path)
    p.add_argument('--timestamp',         required=True)
    p.add_argument('--install-duration',  required=True, type=int)
    p.add_argument('--test-duration',     required=True, type=int)
    args = p.parse_args()

    # Leer listas de módulos
    all_modules  = []
    test_modules = []
    if args.modules_file.exists():
        for line in args.modules_file.read_text().splitlines():
            if line.startswith('ALL_MODULES='):
                all_modules = [m for m in line.split('=', 1)[1].split(',') if m]
            elif line.startswith('TEST_MODULES='):
                test_modules = [m for m in line.split('=', 1)[1].split(',') if m]

    # Parsear logs
    print("Parseando log de instalación...")
    install_entries = parse_log(args.install_log)
    install_result  = analyze_install_log(install_entries)

    print("Parseando log de tests...")
    test_entries   = parse_log(args.test_log)
    test_result    = analyze_test_log(test_entries)

    # Si no se detectaron instalados vía log (Odoo no siempre es explícito),
    # asumir todos los que no fallaron como instalados
    if not install_result['installed'] and all_modules:
        install_result['installed'] = set(all_modules) - set(install_result['failed'])

    print("Generando reporte...")
    generate_report(
        install_result  = install_result,
        test_result     = test_result,
        all_modules     = all_modules,
        test_modules    = test_modules,
        timestamp       = args.timestamp,
        install_dur     = args.install_duration,
        test_dur        = args.test_duration,
        output_path     = args.output,
    )


if __name__ == '__main__':
    main()
