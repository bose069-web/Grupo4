# API de chat muy sencilla con Flask.
# Lee de las variables de entorno a qué Ollama conectarse y qué modelo usar.

import os

import requests
from flask import Flask, jsonify, request

BACKEND_URL = os.getenv("BACKEND_URL", "http://ollama:11434")
MODELO = os.getenv("MODELO", "gemma4:e4b")

app = Flask(__name__)
app.json.ensure_ascii = False   # para que las tildes se vean bien en el navegador


@app.route("/")
def inicio():
    # Para comprobar a qué backend está conectada la API
    return jsonify({"backend": BACKEND_URL, "modelo": MODELO})


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

    try:
        r = requests.post(
            f"{BACKEND_URL}/api/chat",
            json={
                "model": MODELO,
                "messages": [{"role": "user", "content": mensaje}],
                "stream": False,
            },
            timeout=300,
        )
        r.raise_for_status()
    except requests.ConnectionError:
        return jsonify({"error": f"No se puede conectar con Ollama en {BACKEND_URL}"}), 502
    except requests.RequestException as e:
        return jsonify({"error": f"Error de Ollama: {e}"}), 502

    respuesta = r.json()["message"]["content"]
    return jsonify({"respuesta": respuesta, "backend": BACKEND_URL})


if __name__ == "__main__":
    # 0.0.0.0 para que se pueda acceder desde fuera del contenedor
    app.run(host="0.0.0.0", port=8000)
