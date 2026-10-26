# ---------------------------------------------------------------------------
# Imagen de la API de chat (FastAPI) + script de chat por terminal (chat.py)
#   - Por defecto arranca la API:        uvicorn app:app
#   - Para el chat por terminal:         docker compose run --rm chat
# ---------------------------------------------------------------------------
FROM python:3.12-slim

# Python sin ficheros .pyc y con la salida sin buffer (los logs salen al momento)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 1) Primero solo las dependencias: esta capa se reutiliza mientras
#    requirements.txt no cambie, aunque cambie el código.
COPY requirements.txt .
RUN pip install -r requirements.txt

# 2) Después el código
COPY app.py chat.py ./

# 3) No ejecutar como root
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 8000

# La imagen slim no trae curl: comprobamos la salud con el propio Python
HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
