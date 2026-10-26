# Chat por terminal (el script del día anterior).
# Usa las mismas variables de entorno que la API.
#   docker compose run --rm api python chat.py

import os

import requests

BACKEND_URL = os.getenv("BACKEND_URL", "http://ollama:11434")
MODELO = os.getenv("MODELO", "gemma4:e4b")

historial = []
print(f"Conectado a {BACKEND_URL} ({MODELO}). Escribe 'salir' para terminar.\n")

while True:
    texto = input("Tú: ").strip()
    if texto.lower() == "salir":
        break
    if not texto:
        continue

    historial.append({"role": "user", "content": texto})
    try:
        r = requests.post(
            f"{BACKEND_URL}/api/chat",
            json={"model": MODELO, "messages": historial, "stream": False},
            timeout=300,
        )
        r.raise_for_status()
    except requests.RequestException as e:
        print(f"Error: {e}\n")
        historial.pop()
        continue

    try:
        respuesta = r.json()["message"]["content"]
    except (ValueError, KeyError, TypeError):
        print(f"Respuesta no válida de Ollama: {r.text[:500]}\n")
        historial.pop()
        continue
    historial.append({"role": "assistant", "content": respuesta})
    print(f"IA: {respuesta}\n")
