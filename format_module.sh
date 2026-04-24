#!/usr/bin/env bash
# format_module.sh - Aplica el mismo formateo que pre-commit al path de un modulo
# Uso: ./format_module.sh <path_del_modulo>
# Ejemplo: ./format_module.sh addons/mi_modulo

set -euo pipefail

MODULE_PATH="${1:-}"

if [[ -z "$MODULE_PATH" ]]; then
    echo "Uso: $0 <path_del_modulo>"
    echo "Ejemplo: $0 addons/mi_modulo"
    exit 1
fi

if [[ ! -d "$MODULE_PATH" ]]; then
    echo "Error: '$MODULE_PATH' no es un directorio valido."
    exit 1
fi

# Normalizar path (quitar trailing slash)
MODULE_PATH="${MODULE_PATH%/}"

echo "==> Formateando modulo: $MODULE_PATH"
echo ""

# Recolectar archivos Python y JS del modulo
PY_FILES=()
while IFS= read -r -d '' f; do
    PY_FILES+=("$f")
done < <(find "$MODULE_PATH" \
    -type f -name "*.py" \
    ! -path "*/static/src/lib/*" \
    ! -path "*/static/lib/*" \
    ! -path "*/build/*" \
    ! -path "*/dist/*" \
    ! -path "*/tests/samples/*" \
    -print0)

INIT_FILES=()
while IFS= read -r -d '' f; do
    INIT_FILES+=("$f")
done < <(find "$MODULE_PATH" \
    -type f -name "__init__.py" \
    ! -path "*/static/src/lib/*" \
    ! -path "*/static/lib/*" \
    ! -path "*/build/*" \
    ! -path "*/dist/*" \
    -print0)

JS_FILES=()
while IFS= read -r -d '' f; do
    JS_FILES+=("$f")
done < <(find "$MODULE_PATH" \
    -type f -name "*.js" \
    ! -path "*/static/src/lib/*" \
    ! -path "*/static/lib/*" \
    ! -path "*/build/*" \
    ! -path "*/dist/*" \
    -print0)

ALL_TEXT_FILES=()
while IFS= read -r -d '' f; do
    ALL_TEXT_FILES+=("$f")
done < <(find "$MODULE_PATH" \
    -type f \
    ! -path "*/static/src/lib/*" \
    ! -path "*/static/lib/*" \
    ! -path "*/build/*" \
    ! -path "*/dist/*" \
    ! -path "*/tests/samples/*" \
    ! -name "*.pot" \
    ! -name "*.po" \
    ! -name "README.rst" \
    ! -name "LICENSE*" \
    ! -name "COPYING*" \
    ! -name "*.svg" \
    -print0)

# ── 1. ruff (linter + autofix) ───────────────────────────────────────────────
if [[ ${#PY_FILES[@]} -gt 0 ]]; then
    if command -v ruff &>/dev/null; then
        echo "[1/5] ruff --fix (linter)"
        ruff check --fix "${PY_FILES[@]}" || true
        echo "[2/5] ruff-format"
        ruff format "${PY_FILES[@]}"
    else
        echo "[SKIP] ruff no encontrado. Instala con: pip install ruff"
    fi
else
    echo "[1/5] ruff: no hay archivos .py"
    echo "[2/5] ruff-format: no hay archivos .py"
fi

# ── 2. isort (solo __init__.py) ──────────────────────────────────────────────
if [[ ${#INIT_FILES[@]} -gt 0 ]]; then
    if command -v isort &>/dev/null; then
        echo "[3/5] isort (__init__.py)"
        isort --profile=black --force-single-line --line-length=119 "${INIT_FILES[@]}"
    else
        echo "[SKIP] isort no encontrado. Instala con: pip install isort"
    fi
else
    echo "[3/5] isort: no hay archivos __init__.py"
fi

# ── 3. trailing whitespace + end-of-file + encoding pragma + line endings ────
echo "[4/5] trailing-whitespace / end-of-file-fixer / encoding-pragma / line-endings"
for f in "${ALL_TEXT_FILES[@]}"; do
    # Solo procesar archivos de texto (heuristico: sin bytes nulos)
    if file "$f" | grep -qE 'text|ASCII|UTF'; then
        # fix-encoding-pragma --remove: eliminar "# -*- coding: ... -*-" en primera linea
        if head -1 "$f" | grep -qP '^\s*#.*coding[:=]'; then
            # Eliminar la primera linea si es pragma de encoding
            if [[ "$(uname)" == "Darwin" ]]; then
                sed -i '' '1{/^[[:space:]]*#.*coding[:=]/d}' "$f"
            else
                sed -i '1{/^[[:space:]]*#.*coding[:=]/d}' "$f"
            fi
        fi

        # mixed-line-ending --fix=lf: convertir CRLF → LF
        if [[ "$(uname)" == "Darwin" ]]; then
            sed -i '' 's/\r$//' "$f"
        else
            sed -i 's/\r$//' "$f"
        fi

        # trailing-whitespace: eliminar espacios al final de cada linea
        if [[ "$(uname)" == "Darwin" ]]; then
            sed -i '' 's/[[:space:]]*$//' "$f"
        else
            sed -i 's/[[:space:]]*$//' "$f"
        fi

        # end-of-file-fixer: asegurar que el archivo termina con exactamente un newline
        if [[ -s "$f" ]]; then
            # Quitar newlines finales extra y agregar exactamente uno
            last_char=$(tail -c 1 "$f" | wc -c)
            if [[ $last_char -gt 0 ]]; then
                # Verificar si termina en newline
                last_byte=$(tail -c 1 "$f" | od -An -tx1 | tr -d ' \n')
                if [[ "$last_byte" != "0a" ]]; then
                    printf '\n' >> "$f"
                fi
            fi
            # Eliminar newlines vacios al final (dejar solo uno)
            # Usamos Python para mayor portabilidad
            python3 -c "
import sys
with open('$f', 'rb') as fh:
    content = fh.read()
content = content.rstrip(b'\n') + b'\n'
with open('$f', 'wb') as fh:
    fh.write(content)
"
        fi
    fi
done

# ── 4. eslint --fix (JS) ─────────────────────────────────────────────────────
if [[ ${#JS_FILES[@]} -gt 0 ]]; then
    if command -v eslint &>/dev/null; then
        echo "[5/5] eslint --fix"
        eslint --color --fix "${JS_FILES[@]}" || true
    else
        echo "[SKIP] eslint no encontrado."
    fi
else
    echo "[5/5] eslint: no hay archivos .js"
fi

echo ""
echo "==> Formateo completado para: $MODULE_PATH"
