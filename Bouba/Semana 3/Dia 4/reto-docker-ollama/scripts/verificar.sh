#!/usr/bin/env bash
# -----------------------------------------------------------------------------
# Comprueba el stack de extremo a extremo (Linux, macOS, WSL o Git Bash).
#   ./scripts/verificar.sh
# -----------------------------------------------------------------------------
set -u
API="http://localhost:${API_PORT:-8000}"
WEB="http://localhost:${WEB_PORT:-8080}"
FALLOS=0
ok() { printf '  \033[32m[OK]\033[0m %s\n' "$1"; }
ko() { printf '  \033[31m[FALLO]\033[0m %s\n' "$1"; FALLOS=$((FALLOS + 1)); }

echo "1) Estado de los contenedores"
docker compose ps

echo; echo "2) La API está viva"
curl -fsS "$API/health" >/dev/null && ok "API responde en $API" || ko "La API no responde en $API"

echo; echo "3) La API llega al backend Ollama"
if INFO=$(curl -fsS "$API/health/backend"); then ok "$INFO"; else ko "La API no llega a Ollama (mira: docker compose logs api)"; fi

echo; echo "4) El frontend y su proxy hacia la API"
curl -fsS -o /dev/null "$WEB/" && ok "Frontend en $WEB" || ko "El frontend no responde en $WEB"
curl -fsS "$WEB/api/info" >/dev/null && ok "Proxy nginx /api -> api:8000 funciona" || ko "El proxy del frontend no llega a la API"

echo; echo "5) Pregunta de prueba al modelo (puede tardar en CPU)"
if R=$(curl -fsS -m 300 -X POST "$API/api/chat" -H 'Content-Type: application/json' \
      -d '{"messages":[{"role":"user","content":"Responde solo con la palabra: funciona"}]}'); then
  ok "$R"
else
  ko "El modelo no ha respondido"
fi

echo
if [ "$FALLOS" -eq 0 ]; then echo "Todo correcto."; else echo "$FALLOS comprobación(es) fallida(s)."; fi
exit "$FALLOS"
