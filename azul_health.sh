#!/bin/bash
# Health-check del entorno de PRUEBAS de Azul (pruebas.azul.com.do + ACS Modirum).
# Uso: ./azul_health.sh   (requiere el contenedor lfernandez_v17 corriendo)

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
out=$(docker exec lfernandez_v17 python3 /tmp/azul_probe.py 3dsecure 2>&1 | tail -14)
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
