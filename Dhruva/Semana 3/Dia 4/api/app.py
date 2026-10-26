# API de chat muy sencilla con Flask.
# Lee de las variables de entorno a qué Ollama conectarse y qué modelo usar.

import os
import threading
import time

import requests
from flask import Flask, jsonify, request

BACKEND_URL = os.getenv("BACKEND_URL", "http://ollama:11434")
MODELO = os.getenv("MODELO", "gemma4:e4b")
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "128"))
ENABLE_RESPONSE_CACHE = os.getenv("ENABLE_RESPONSE_CACHE", "false").lower() == "true"
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "300"))

app = Flask(__name__)
app.json.ensure_ascii = False   # para que las tildes se vean bien en el navegador
response_cache = {}
cache_lock = threading.Lock()


@app.route("/")
def inicio():
    return """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chat Gemma</title>
  <style>
    body { max-width: 760px; margin: 0 auto; padding: 24px; background: #111827; color: #f3f4f6; font-family: system-ui, sans-serif; }
    #messages { min-height: 240px; padding: 16px; background: #1f2937; border-radius: 10px; white-space: pre-wrap; }
    form { display: flex; gap: 8px; margin-top: 16px; }
    input { flex: 1; padding: 12px; border: 1px solid #4b5563; border-radius: 6px; background: #111827; color: inherit; }
    button { padding: 12px 18px; border: 0; border-radius: 6px; background: #2563eb; color: white; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
  </style>
</head>
<body>
  <h1>Chat Gemma</h1>
  <p>Modelo: <span id="model">comprobando...</span></p>
  <div id="messages">Escribe un mensaje para empezar.</div>
  <form id="chat-form">
    <input id="message" autocomplete="off" placeholder="Escribe tu mensaje..." required>
    <button id="send" type="submit">Enviar</button>
  </form>
  <script>
    const messages = document.querySelector("#messages");
    const form = document.querySelector("#chat-form");
    const input = document.querySelector("#message");
    const button = document.querySelector("#send");
    fetch("/health").then(r => r.json()).then(data => {
      document.querySelector("#model").textContent = data.modelo;
    });
    form.addEventListener("submit", async event => {
      event.preventDefault();
      const mensaje = input.value.trim();
      if (!mensaje) return;
      button.disabled = true;
      messages.textContent = "Procesando...";
      try {
        const response = await fetch("/chat", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({mensaje})
        });
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || "Error desconocido");
        messages.textContent = data.respuesta;
        input.value = "";
      } catch (error) {
        messages.textContent = `Error: ${error.message}`;
      } finally {
        button.disabled = false;
        input.focus();
      }
    });
  </script>
</body>
</html>"""


@app.route("/health")
def health():
    try:
        response = requests.get(f"{BACKEND_URL}/api/tags", timeout=5)
        response.raise_for_status()
    except requests.RequestException as error:
        return jsonify({"status": "degraded", "error": str(error), "modelo": MODELO}), 503
    return jsonify({"status": "ok", "backend": BACKEND_URL, "modelo": MODELO})


@app.route("/chat", methods=["GET", "POST"])
def chat():
    # GET  -> /chat?mensaje=hola           (para probar desde el navegador)
    # POST -> {"mensaje": "hola"}          (para el frontend)
    if request.method == "POST":
        mensaje = (request.get_json(silent=True) or {}).get("mensaje", "")
    else:
        mensaje = request.args.get("mensaje", "")

    if not mensaje:
        return jsonify({"error": "Falta el mensaje"}), 400

    cache_key = mensaje.strip()
    if ENABLE_RESPONSE_CACHE:
        with cache_lock:
            cached = response_cache.get(cache_key)
            if cached and cached["expires_at"] > time.time():
                return jsonify({**cached["payload"], "cached": True})

    try:
        r = requests.post(
            f"{BACKEND_URL}/api/chat",
            json={
                "model": MODELO,
                "messages": [{"role": "user", "content": mensaje}],
                "stream": False,
                "options": {"temperature": TEMPERATURE, "num_predict": MAX_TOKENS},
            },
            timeout=300,
        )
        r.raise_for_status()
    except requests.ConnectionError:
        return jsonify({"error": f"No se puede conectar con Ollama en {BACKEND_URL}"}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Error de Ollama: {e}"}), 502

    try:
        datos = r.json()
        respuesta = datos["message"]["content"]
    except (ValueError, KeyError, TypeError):
        return jsonify({"error": "Ollama devolvió una respuesta no válida"}), 502

    datos_uso = r.json().get("eval_count")
    payload = {
        "respuesta": respuesta,
        "backend": BACKEND_URL,
        "output_tokens": datos_uso,
        "cached": False,
    }
    if ENABLE_RESPONSE_CACHE:
        with cache_lock:
            response_cache[cache_key] = {
                "expires_at": time.time() + CACHE_TTL_SECONDS,
                "payload": payload,
            }
    return jsonify(payload)


if __name__ == "__main__":
    # 0.0.0.0 para que se pueda acceder desde fuera del contenedor
    app.run(host="0.0.0.0", port=8000)
