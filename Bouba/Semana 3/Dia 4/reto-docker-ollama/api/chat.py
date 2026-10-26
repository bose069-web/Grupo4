"""
Script de chat por terminal (el del día anterior), adaptado para contenedores.

Cambio clave respecto a la versión "en local": la URL de Ollama ya no está
escrita en el código, se lee de la variable de entorno BACKEND_URL.

Uso dentro del stack:
    docker compose run --rm chat

Uso fuera de Docker:
    BACKEND_URL=http://localhost:11434 python chat.py
"""

import json
import os
import sys

import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:11434").rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:e4b")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Eres un asistente útil. Responde en español de forma clara y breve.")
TIMEOUT = httpx.Timeout(float(os.getenv("REQUEST_TIMEOUT", "300")), connect=10.0)
HEADERS = {"Authorization": f"Bearer {BACKEND_API_KEY}"} if BACKEND_API_KEY else {}


def stream_reply(client: httpx.Client, history: list[dict]) -> str:
    """Envía el historial a Ollama e imprime la respuesta según llega."""
    payload = {"model": MODEL_NAME, "messages": history, "stream": True}
    reply = []
    with client.stream("POST", f"{BACKEND_URL}/api/chat", json=payload, headers=HEADERS) as r:
        if r.is_error:
            r.read()
            raise RuntimeError(f"HTTP {r.status_code}: {r.text[:300]}")
        for line in r.iter_lines():
            if not line:
                continue
            chunk = json.loads(line)
            if chunk.get("error"):
                raise RuntimeError(chunk["error"])
            piece = chunk.get("message", {}).get("content", "")
            print(piece, end="", flush=True)
            reply.append(piece)
            if chunk.get("done"):
                break
    print()
    return "".join(reply)


def main() -> int:
    print(f"Conectado a {BACKEND_URL} | modelo: {MODEL_NAME}")
    print("Escribe tu mensaje. Comandos: /reset (borra historial), /salir\n")
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    with httpx.Client(timeout=TIMEOUT) as client:
        while True:
            try:
                user = input("Tú> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not user:
                continue
            if user in ("/salir", "/exit", "/quit"):
                return 0
            if user == "/reset":
                history = history[:1]
                print("(historial borrado)\n")
                continue

            history.append({"role": "user", "content": user})
            print("IA> ", end="", flush=True)
            try:
                answer = stream_reply(client, history)
            except httpx.ConnectError:
                print(f"\n[error] No se puede conectar con {BACKEND_URL}. ¿Está levantado Ollama?")
                history.pop()
                continue
            except Exception as exc:  # noqa: BLE001
                print(f"\n[error] {exc}")
                history.pop()
                continue
            history.append({"role": "assistant", "content": answer})
            print()


if __name__ == "__main__":
    sys.exit(main())
