#!/usr/bin/env bash
# =====================================================================
# diagnose_ir3_report.sh
# Descompone las casillas 3 (Sueldos) y 4 (Otras Remuneraciones) del
# reporte IR-3 / archivo TSS por regla salarial y por empleado, para un
# periodo y compañía dados. Muestra el doble-conteo de Horas Nocturnas
# (HNI) — casilla 4 "actual con bug" vs "corregido".
#
# Uso:
#   ./diagnose_ir3_report.sh <DB> <MM/YYYY> [COMPANY_ID]
# Ej:
#   ./diagnose_ir3_report.sh mi_produccion 05/2026 1
# =====================================================================
set -euo pipefail

DB="${1:?Falta la base de datos. Uso: $0 <DB> <MM/YYYY> [COMPANY_ID]}"
PERIOD="${2:?Falta el periodo MM/YYYY. Uso: $0 <DB> <MM/YYYY> [COMPANY_ID]}"
COMPANY="${3:-1}"
PG_CONTAINER="${PG_CONTAINER:-odoo-db}"
PG_USER="${PG_USER:-odoo}"
SQL_FILE="$(dirname "$0")/diagnose_ir3_report.sql"

MONTH="${PERIOD%%/*}"
YEAR="${PERIOD##*/}"
MSTART="$(printf '%04d-%02d-01' "$YEAR" "$MONTH")"
# último día del mes
MEND="$(date -j -v1d -v"${MONTH}"m -v"${YEAR}"y -v+1m -v-1d +%Y-%m-%d 2>/dev/null \
        || date -d "$MSTART +1 month -1 day" +%Y-%m-%d)"

echo "Base=$DB  Periodo=$PERIOD  ($MSTART .. $MEND)  Company=$COMPANY"
echo "----------------------------------------------------------------"

docker cp "$SQL_FILE" "$PG_CONTAINER:/tmp/diagnose_ir3_report.sql"
docker exec "$PG_CONTAINER" psql -U "$PG_USER" -d "$DB" \
    -v company="$COMPANY" -v mstart="$MSTART" -v mend="$MEND" \
    -f /tmp/diagnose_ir3_report.sql
