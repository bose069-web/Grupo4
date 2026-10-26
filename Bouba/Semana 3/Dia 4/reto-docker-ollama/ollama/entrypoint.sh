#!/bin/sh
# ---------------------------------------------------------------------------
# Arranca Ollama y se asegura de que el modelo está descargado.
#
#   entrypoint.sh                 -> modo normal (contenedor): serve + pull si falta
#   entrypoint.sh --solo-descargar -> se usa en el build para meter el modelo en la imagen
#
# El modelo se guarda en /root/.ollama, que en docker-compose es un VOLUMEN:
# solo se descarga la primera vez; en los siguientes arranques ya está ahí.
# ---------------------------------------------------------------------------
set -e

MODEL="${MODEL_NAME:-gemma4:e4b}"

esperar_servidor() {
  i=0
  until ollama list >/dev/null 2>&1; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
      echo "[ollama] ERROR: el servidor no responde tras 60 s" >&2
      exit 1
    fi
    sleep 1
  done
}

descargar_si_falta() {
  if ollama show "$MODEL" >/dev/null 2>&1; then
    echo "[ollama] Modelo $MODEL ya presente. No se descarga."
  else
    echo "[ollama] Descargando $MODEL (solo la primera vez, puede tardar bastante)..."
    ollama pull "$MODEL"
    echo "[ollama] Modelo $MODEL listo."
  fi
}

ollama serve &
SERVER_PID=$!

# Reenviar la señal de parada (docker stop) al proceso de Ollama
trap 'kill -TERM "$SERVER_PID" 2>/dev/null; wait "$SERVER_PID"; exit 0' TERM INT

esperar_servidor
descargar_si_falta

if [ "$1" = "--solo-descargar" ]; then
  kill -TERM "$SERVER_PID"
  wait "$SERVER_PID" || true
  exit 0
fi

echo "[ollama] Servidor listo en :11434 con el modelo $MODEL"
wait "$SERVER_PID"
