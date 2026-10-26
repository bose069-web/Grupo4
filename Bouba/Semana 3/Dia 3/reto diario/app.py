import os
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

BACKEND_URL = os.getenv("BACKEND_URL", "http://ollama:11434").rstrip("/")
BACKEND_MODE = os.getenv("BACKEND_MODE", "local")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma3:1b")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300"))

app = FastAPI(title="Reto diario API", version="1.0.0")


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    model: str | None = None


def backend_headers() -> dict[str, str]:
    if BACKEND_API_KEY:
        return {"Authorization": f"Bearer {BACKEND_API_KEY}"}
    return {}


def backend_timeout() -> httpx.Timeout:
    return httpx.Timeout(REQUEST_TIMEOUT, connect=10.0)


def backend_error(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.TimeoutException):
        detail = f"Ollama no respondió en {REQUEST_TIMEOUT:g} segundos."
    elif isinstance(exc, httpx.HTTPStatusError):
        detail = f"Ollama respondió HTTP {exc.response.status_code}."
    else:
        detail = f"No se pudo conectar con Ollama en {BACKEND_URL}."
    return HTTPException(status_code=502, detail=detail)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/backend")
async def health_backend() -> dict:
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            response = await client.get(
                f"{BACKEND_URL}/api/tags", headers=backend_headers()
            )
            response.raise_for_status()
    except Exception as exc:
        raise backend_error(exc) from exc

    models = [model.get("name") for model in response.json().get("models", [])]
    return {
        "status": "ok" if MODEL_NAME in models else "model_not_found",
        "backend_url": BACKEND_URL,
        "mode": BACKEND_MODE,
        "model": MODEL_NAME,
        "available_models": models,
    }


@app.get("/api/info")
async def info() -> dict[str, str]:
    return {
        "backend_url": BACKEND_URL,
        "mode": BACKEND_MODE,
        "model": MODEL_NAME,
    }


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict[str, str]:
    payload = {
        "model": request.model or MODEL_NAME,
        "messages": [message.model_dump() for message in request.messages],
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=backend_timeout()) as client:
            response = await client.post(
                f"{BACKEND_URL}/api/chat",
                json=payload,
                headers=backend_headers(),
            )
            response.raise_for_status()
    except Exception as exc:
        raise backend_error(exc) from exc

    result = response.json()
    return {
        "reply": result.get("message", {}).get("content", ""),
        "model": result.get("model", payload["model"]),
        "mode": BACKEND_MODE,
    }