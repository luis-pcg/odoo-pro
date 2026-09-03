#!/bin/bash
# Build the three-instance environment the manual is captured from:
#
#   padre  http://localhost:8101   master, the only one with the sync module
#   hija1  http://localhost:8102   client, only l10n_do_hr_payroll
#   hija2  http://localhost:8103   client, only l10n_do_hr_payroll
#
#   ./setup.sh                 full rebuild of the three databases
#   ./setup.sh --no-rebuild    keep them, just re-pair and restart the servers

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$HERE/lib.sh"

CREDS="$HERE/creds.env"
REBUILD=true
for arg in "$@"; do
  [[ "$arg" == "--no-rebuild" ]] && REBUILD=false
done

echo "=================================================="
echo " Manual de sincronización — entorno de 3 instancias"
for inst in "${INSTANCES[@]}"; do
  printf '  %-6s %-16s %-26s %s\n' "$inst" "$(role_of "$inst")" "$(modules_of "$inst")" "$(url_of "$inst")"
done
echo "=================================================="

stop_servers

if [[ "$REBUILD" == "true" ]]; then
  echo "[1/5] Creando las tres bases (con es_DO)..."
  for inst in "${INSTANCES[@]}"; do
    drop_db "$(db_of "$inst")"
    # Match Odoo's own failure lines only: docutils logs "(ERROR/3)" while
    # rendering manifest descriptions, which is not an install failure.
    if odoo_cli "$inst" --without-demo=all --log-level=warn --stop-after-init --no-http \
         --load-language=es_DO -i "$(modules_of "$inst")" 2>&1 \
         | grep -E "(CRITICAL|ERROR) $(db_of "$inst")|Traceback \(most recent"; then
      echo "ERROR: falló la instalación en $(db_of "$inst")" >&2; exit 1
    fi
    echo "   $(db_of "$inst") lista con $(modules_of "$inst")"
  done
else
  echo "[1/5] Reusando las bases existentes (--no-rebuild)."
fi

echo "[2/5] Idioma, compañía, país y permisos en cada instancia..."
for inst in "${INSTANCES[@]}"; do
  put_args "$(printf '{"company": "%s", "role": "%s"}' "$(company_of "$inst")" "$(role_of "$inst")")"
  out="$(run_py "$inst" bootstrap.py | grep '^OK' || true)"
  [[ -z "$out" ]] && { echo "ERROR: bootstrap falló en $inst" >&2; exit 1; }
  echo "   $inst: $out"
done

# macOS ships bash 3.2, which has no associative arrays.
set_key() { eval "KEY_$1=\$2"; }
get_key() { eval "printf '%s' \"\${KEY_$1:-}\""; }

echo "[3/5] Hijas: emitiendo la llave de API que usará el padre..."
for inst in hija1 hija2; do
  put_args '{"name": "Sincronización de nómina"}'
  key="$(run_py "$inst" mint_key.py | grep '^KEY=' | cut -d= -f2- || true)"
  [[ -z "$key" ]] && { echo "ERROR: sin llave de API en $inst" >&2; exit 1; }
  set_key "$inst" "$key"
  echo "   $inst lista"
done

echo "[4/5] Padre: registrando las dos hijas como bases de datos de la flota..."
for inst in hija1 hija2; do
  put_args "$(printf '{"name": "%s", "url": "%s", "db": "%s", "key": "%s"}' \
    "$(company_of "$inst")" "$(internal_url_of "$inst")" "$(db_of "$inst")" "$(get_key "$inst")")"
  out="$(run_py padre register_client.py | grep '^PROJECT_ID=' || true)"
  [[ -z "$out" ]] && { echo "ERROR: no se registró $inst en el padre" >&2; exit 1; }
  echo "   $(company_of "$inst") registrada ($out)"
done

{
  echo "# Generado por setup.sh — credenciales del entorno del manual."
  for inst in hija1 hija2; do
    echo "API_KEY_${inst}='$(get_key "$inst")'"
  done
} > "$CREDS"
echo "   credenciales en $CREDS"

echo "[5/5] Levantando los tres servidores..."
for inst in "${INSTANCES[@]}"; do
  start_server "$inst"
done
for inst in "${INSTANCES[@]}"; do
  wait_http "$(url_of "$inst")" || {
    echo "ERROR: $inst no levantó" >&2
    docker logs "$(container_of "$inst")" 2>&1 | tail -30 >&2
    exit 1
  }
done

echo ""
echo "Entorno listo."
for inst in "${INSTANCES[@]}"; do
  printf '  %-6s %s   (admin/admin)   %s\n' "$inst" "$(url_of "$inst")" "$(company_of "$inst")"
done
echo "Genera el manual con:  tools/sync-manual/generate.sh"
echo "Baja el entorno con:   tools/sync-manual/teardown.sh"
