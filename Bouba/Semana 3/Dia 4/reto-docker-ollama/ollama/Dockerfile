# ---------------------------------------------------------------------------
# Imagen de Ollama con el modelo Gemma 4 E4B "precargado".
#
# Dos formas de precargar (elige con el build-arg PRELOAD_IN_IMAGE):
#   false (por defecto) -> el modelo se descarga al primer arranque y se guarda
#                          en el volumen "ollama_models". Imagen ligera.
#   true                -> el modelo se descarga DURANTE el build y queda dentro
#                          de la imagen (~10 GB). Útil para llevarla a otra
#                          máquina sin internet (docker save / docker load).
# Gemma 4 necesita Ollama >= 0.20.
# ---------------------------------------------------------------------------
ARG OLLAMA_VERSION=latest
FROM ollama/ollama:${OLLAMA_VERSION}

ARG MODEL_NAME=gemma4:e4b
ARG PRELOAD_IN_IMAGE=false

ENV MODEL_NAME=${MODEL_NAME} \
    OLLAMA_HOST=0.0.0.0:11434 \
    OLLAMA_KEEP_ALIVE=30m

COPY entrypoint.sh /usr/local/bin/entrypoint.sh
# Quita posibles finales de línea de Windows (CRLF) y da permiso de ejecución
RUN sed -i 's/\r$//' /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

RUN if [ "$PRELOAD_IN_IMAGE" = "true" ]; then /usr/local/bin/entrypoint.sh --solo-descargar; fi

EXPOSE 11434

# Sano = el servidor responde Y el modelo está disponible
HEALTHCHECK --interval=15s --timeout=10s --start-period=60m --retries=3 \
  CMD ollama show "$MODEL_NAME" >/dev/null 2>&1 || exit 1

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
