#!/bin/bash
# Health-check del entorno de PRUEBAS de Azul (pruebas.azul.com.do + ACS Modirum).
#
# Distingue un fallo del modulo de una caida del ACS de pruebas (Modirum). Cuando
# las transacciones 3DS se quedan en "pending" para siempre, casi siempre es el
# ACS de Modirum caido (HTTP 502 en el endpoint de challenge), no el modulo.
#
# Uso:   ./azul_health.sh
#   export AZUL_HEALTH_CONTAINER=mi_contenedor   (default: lfernandez_v19)
#   export AZUL_CERT_DIR=/ruta/a/certs           (default: dev_env_odoo_pro-17/certs)
#
# El script auto-aprovisiona dentro del contenedor:
#   /tmp/azul_probe.py   (desde azul_probe.py junto a este script)
#   /tmp/azul_cert.pem   (desde $AZUL_CERT_DIR/progressa.local.crt)
#   /tmp/azul_key.pem    (desde $AZUL_CERT_DIR/progressa-dev-unencrypted.key)

CONTAINER="${AZUL_HEALTH_CONTAINER:-lfernandez_v19}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CERT_DIR="${AZUL_CERT_DIR:-$SCRIPT_DIR/../dev_env_odoo_pro-17/certs}"

# Verificar contenedor vivo
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER}$"; then
  echo "ERROR: contenedor '$CONTAINER' no esta corriendo." >&2
  echo "       Ajusta con: export AZUL_HEALTH_CONTAINER=<nombre>" >&2
  exit 1
fi

# Verificar certs locales
if [[ ! -f "$CERT_DIR/progressa.local.crt" || ! -f "$CERT_DIR/progressa-dev-unencrypted.key" ]]; then
  echo "ERROR: faltan certs mTLS en '$CERT_DIR'." >&2
  echo "       Se esperan: progressa.local.crt y progressa-dev-unencrypted.key" >&2
  echo "       Ajusta con: export AZUL_CERT_DIR=<ruta>" >&2
  exit 1
fi

# Auto-aprovisionar probe + certs dentro del contenedor
docker cp "$SCRIPT_DIR/azul_probe.py" "$CONTAINER:/tmp/azul_probe.py" 2>/dev/null
docker cp "$CERT_DIR/progressa.local.crt" "$CONTAINER:/tmp/azul_cert.pem" 2>/dev/null
docker cp "$CERT_DIR/progressa-dev-unencrypted.key" "$CONTAINER:/tmp/azul_key.pem" 2>/dev/null

echo "== 1. API Azul test (conectividad básica) =="
code=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" "https://pruebas.azul.com.do/webservices/JSON/Default.aspx")
echo "   https://pruebas.azul.com.do -> HTTP $code  (cualquier respuesta = host vivo; 000 = caído/sin red)"

echo
echo "== 2. ACS de pruebas (Modirum) — aquí falla cuando hay 'No autenticada'/SGS-050655 =="
code=$(curl -s --max-time 10 -o /dev/null -w "%{http_code}" -X POST "https://3ds-acs.test.modirum.com/mdpayacs/3ds-method" --data "threeDSMethodData=healthcheck")
case "$code" in
  200) echo "   ACS Modirum -> HTTP 200  ✓ SANO" ;;
  000) echo "   ACS Modirum -> sin respuesta  ✗ CAIDO" ;;
  *)   echo "   ACS Modirum -> HTTP $code  ✗ CAIDO/DEGRADADO (502 = típico de outage)" ;;
esac

echo
echo "== 3. Transacción 3DS real de prueba (mTLS + credenciales + flujo completo) =="
out=$(docker exec "$CONTAINER" python3 /tmp/azul_probe.py 3dsecure 2>&1 | tail -14)
if echo "$out" | grep -q "3D2METHOD\|3D_SECURE"; then
  echo "   ✓ 3DS OPERATIVO: Azul devolvió flujo 3DS (3D2METHOD). Puedes probar pagos."
elif echo "$out" | grep -q "No autenticada\|SGS-05"; then
  echo "   ✗ 3DS CAIDO: API viva pero autenticación 3DS no disponible (ACS down)."
  echo "$out" | grep -E "IsoCode|ResponseMessage|ErrorDescription" | sed 's/^/   /'
elif echo "$out" | grep -qi "ssl\|timeout\|connect"; then
  echo "   ✗ API INACCESIBLE (red/TLS):"
  echo "$out" | tail -2 | sed 's/^/   /'
else
  echo "   ? Respuesta inesperada:"
  echo "$out" | sed 's/^/   /'
fi
