#!/bin/bash
# Captures the manual from the three running instances and renders it into
# docs/manuals/l10n_do_hr_payroll_sync/.
#
#   ./generate.sh              # requires setup.sh to have run
#   ./generate.sh --setup      # runs setup.sh first (full rebuild)
#   ./generate.sh --headed     # watch the browser do it

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

GEN_DIR="$ROOT_DIR/tools/manual-generator"     # playwright lives here already
OUT_DIR="$ROOT_DIR/docs/manuals/l10n_do_hr_payroll_sync"
IMG_DIR="$OUT_DIR/img"
HEADED=""
DO_SETUP=false

for a in "$@"; do
  [[ "$a" == "--headed" ]] && HEADED="--headed"
  [[ "$a" == "--setup" ]] && DO_SETUP=true
done

if [[ "$DO_SETUP" == "true" ]]; then
  "$HERE/setup.sh"
fi

for inst in "${INSTANCES[@]}"; do
  wait_http "$(url_of "$inst")" 5 || {
    echo "ERROR: $inst no responde en $(url_of "$inst"). Corre primero tools/sync-manual/setup.sh" >&2
    exit 1
  }
done

mkdir -p "$IMG_DIR"

if [[ ! -d "$GEN_DIR/node_modules/playwright" ]]; then
  echo "Instalando dependencias de Node (playwright)..."
  ( cd "$GEN_DIR" && PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 npm install --no-audit --no-fund )
fi

# ESM resolves imports from the script's own directory, so borrow the
# generator's node_modules instead of installing playwright twice.
[[ -e "$HERE/node_modules" ]] || ln -s "$GEN_DIR/node_modules" "$HERE/node_modules"

INSTANCE_ARG=""
for inst in "${INSTANCES[@]}"; do
  [[ -n "$INSTANCE_ARG" ]] && INSTANCE_ARG+=","
  INSTANCE_ARG+="${inst}=$(url_of "$inst")|$(db_of "$inst")"
done

echo "[1/3] Rasterizando el diagrama de arquitectura..."
node "$HERE/make-diagram.mjs" --out="$IMG_DIR" --name=26-arquitectura.png

echo "[2/3] Capturando pantallas en las tres instancias..."
NODE_PATH="$GEN_DIR/node_modules" node "$HERE/capture.mjs" \
  --config="$HERE/config.json" \
  --instances="$INSTANCE_ARG" \
  --login=admin --password=admin \
  --out="$IMG_DIR" \
  $HEADED

echo "[3/3] Renderizando el manual..."
node "$HERE/render.mjs" \
  --config="$HERE/config.json" \
  --img="$IMG_DIR" \
  --out="$OUT_DIR/README.md"

echo ""
echo "Manual generado: $OUT_DIR/README.md"
echo "Capturas       : $IMG_DIR"
