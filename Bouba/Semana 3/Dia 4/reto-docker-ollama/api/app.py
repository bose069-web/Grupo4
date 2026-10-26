"""
API de chat (FastAPI) que hace de intermediaria entre el frontend y Ollama.

El backend de Ollama se elige con la variable de entorno BACKEND_URL:
  - Local   -> http://ollama:11434                (contenedor del propio stack)
  - Remoto  -> http://host.docker.internal:11435  (remoto simulado)
               http://<IP_OTRO_PC_O_VM>:11434     (otro equipo o VM de Azure)

Optimizaciones (todas desactivadas por defecto, se activan por variables de entorno):
  - Caché de respuestas + agrupación de peticiones idénticas simultáneas
      CACHE_ENABLED=true  CACHE_TTL=600  CACHE_MAX_ITEMS=500
  - Parámetros del modelo por defecto
      MODEL_TEMPERATURE  MODEL_NUM_PREDICT (max tokens)  MODEL_NUM_CTX  MODEL_THINK
"""

import asyncio
import hashlib
import json
import os
import time
from collections import OrderedDict
from typing import Any, AsyncIterator, Literal
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field


# --- Configuración por variables de entorno ---------------------------------
def _env_str(nombre: str) -> str | None:
    valor = os.getenv(nombre, "").strip()
    return valor or None


def _env_num(nombre: str, tipo):
    valor = _env_str(nombre)
    return tipo(valor) if valor is not None else None


def _env_bool(nombre: str) -> bool | None:
    valor = _env_str(nombre)
    if valor is None:
        return None
    return valor.lower() in ("1", "true", "si", "sí", "yes", "on")


BACKEND_URL = os.getenv("BACKEND_URL", "http://ollama:11434").rstrip("/")
BACKEND_API_KEY = os.getenv("BACKEND_API_KEY", "")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma4:e4b")
SYSTEM_PROMPT = os.getenv("SYSTEM_PROMPT", "Eres un asistente útil. Responde en español de forma clara y breve.")
REQUEST_TIMEOUT = float(os.getenv("REQUEST_TIMEOUT", "300"))
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Parámetros del modelo (vacío = valor por defecto del modelo)
OPCIONES_POR_DEFECTO = {
    k: v
    for k, v in {
        "temperature": _env_num("MODEL_TEMPERATURE", float),
        "num_predict": _env_num("MODEL_NUM_PREDICT", int),
        "num_ctx": _env_num("MODEL_NUM_CTX", int),
    }.items()
    if v is not None
}
THINK_POR_DEFECTO = _env_bool("MODEL_THINK")  # None = lo que decida el modelo

# Caché
CACHE_ENABLED = bool(_env_bool("CACHE_ENABLED"))
CACHE_TTL = int(os.getenv("CACHE_TTL", "600"))
CACHE_MAX_ITEMS = int(os.getenv("CACHE_MAX_ITEMS", "500"))

BACKEND_HOST = urlparse(BACKEND_URL).hostname or ""
BACKEND_MODE = "local" if BACKEND_HOST in ("ollama", "localhost", "127.0.0.1") else "remoto"

METRICAS_OLLAMA = (
    "total_duration", "load_duration", "prompt_eval_count",
    "prompt_eval_duration", "eval_count", "eval_duration",
)

app = FastAPI(title="Chat API - Reto Docker", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Caché de respuestas -----------------------------------------------------
class CacheRespuestas:
    """
    Caché LRU en memoria con caducidad (TTL).

    Además agrupa peticiones idénticas que llegan a la vez ("single flight"):
    si 10 usuarios preguntan lo mismo al mismo tiempo, solo la primera llega
    a Ollama; las otras 9 esperan su resultado. Sin esto, la caché no sirve
    de nada en un pico de carga, porque todas fallarían a la vez.
    """

    def __init__(self, activa: bool, ttl: int, max_items: int):
        self.activa = activa
        self.ttl = ttl
        self.max_items = max_items
        self._datos: OrderedDict[str, tuple[float, dict]] = OrderedDict()
        self.en_curso: dict[str, asyncio.Future] = {}
        self.reiniciar_contadores()

    def reiniciar_contadores(self):
        self.aciertos = 0   # servidas desde la caché
        self.agrupadas = 0  # esperaron a una petición idéntica en curso
        self.fallos = 0     # tuvieron que ir a Ollama

    def get(self, clave: str) -> dict | None:
        item = self._datos.get(clave)
        if item is None:
            return None
        caduca, valor = item
        if caduca < time.monotonic():
            del self._datos[clave]
            return None
        self._datos.move_to_end(clave)
        return valor

    def set(self, clave: str, valor: dict):
        self._datos[clave] = (time.monotonic() + self.ttl, valor)
        self._datos.move_to_end(clave)
        while len(self._datos) > self.max_items:
            self._datos.popitem(last=False)

    def limpiar(self):
        self._datos.clear()
        self.reiniciar_contadores()

    def estado(self) -> dict:
        return {
            "activa": self.activa, "ttl_s": self.ttl, "max_items": self.max_items,
            "entradas": len(self._datos), "aciertos": self.aciertos,
            "agrupadas": self.agrupadas, "fallos": self.fallos,
        }


cache = CacheRespuestas(CACHE_ENABLED, CACHE_TTL, CACHE_MAX_ITEMS)


# --- Modelos de datos --------------------------------------------------------
class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: list[Message] = Field(..., min_length=1, description="Historial de la conversación")
    model: str | None = Field(None, description="Opcional: sobrescribe MODEL_NAME")
    stream: bool = Field(False, description="true = respuesta NDJSON en formato Ollama (con métricas)")
    options: dict[str, Any] | None = Field(None, description="Opciones de Ollama: temperature, num_predict...")
    think: bool | None = Field(None, description="Razonamiento del modelo (si lo soporta)")


# --- Utilidades --------------------------------------------------------------
def _headers() -> dict:
    return {"Authorization": f"Bearer {BACKEND_API_KEY}"} if BACKEND_API_KEY else {}


def _timeout() -> httpx.Timeout:
    return httpx.Timeout(REQUEST_TIMEOUT, connect=10.0)


def _payload(req: ChatRequest) -> dict:
    messages = [m.model_dump() for m in req.messages]
    if SYSTEM_PROMPT and messages[0]["role"] != "system":
        messages.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
    payload = {"model": req.model or MODEL_NAME, "messages": messages, "stream": True}
    opciones = {**OPCIONES_POR_DEFECTO, **(req.options or {})}
    if opciones:
        payload["options"] = opciones
    think = req.think if req.think is not None else THINK_POR_DEFECTO
    if think is not None:
        payload["think"] = think
    return payload


def _clave(payload: dict) -> str:
    base = {k: payload.get(k) for k in ("model", "messages", "options", "think")}
    return hashlib.sha256(json.dumps(base, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def _backend_error(exc: Exception) -> HTTPException:
    if isinstance(exc, httpx.ConnectError):
        detail = f"No se puede conectar con el backend Ollama en {BACKEND_URL} ({BACKEND_MODE})."
    elif isinstance(exc, httpx.TimeoutException):
        detail = f"El backend {BACKEND_URL} ha tardado demasiado en responder."
    elif isinstance(exc, httpx.HTTPStatusError):
        detail = f"El backend respondió {exc.response.status_code}: {exc.response.text[:300]}"
    else:
        detail = f"Error con el backend: {exc}"
    status = 503 if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 503 else 502
    return HTTPException(status_code=status, detail=detail)


def _marcar_recuperada(fut: asyncio.Future):
    # Evita el aviso "Future exception was never retrieved" si nadie esperaba
    if not fut.cancelled():
        fut.exception()


# --- Núcleo: obtener la respuesta (caché, agrupación u Ollama) ---------------
async def _repetir(resultado: dict, origen: str) -> AsyncIterator[dict]:
    """Reproduce una respuesta guardada con el mismo formato NDJSON que Ollama."""
    mensaje = {"role": "assistant", "content": resultado["content"]}
    if resultado.get("thinking"):
        mensaje["thinking"] = resultado["thinking"]
    yield {"model": resultado["model"], "message": mensaje, "done": False}
    yield {
        "model": resultado["model"],
        "message": {"role": "assistant", "content": ""},
        "done": True,
        "done_reason": resultado.get("done_reason"),
        **resultado["metricas"],
        "cache": origen,
    }


async def _retransmitir(client, upstream, clave, fut) -> AsyncIterator[dict]:
    """Pasa los trozos de Ollama al cliente y guarda la respuesta completa en la caché."""
    contenido, razonamiento, final = [], [], None
    try:
        async for linea in upstream.aiter_lines():
            if not linea:
                continue
            trozo = json.loads(linea)
            if trozo.get("error"):
                yield trozo
                break
            mensaje = trozo.get("message", {})
            contenido.append(mensaje.get("content", ""))
            razonamiento.append(mensaje.get("thinking") or "")
            if trozo.get("done"):
                trozo["cache"] = "miss" if clave else None
                final = trozo
            yield trozo
            if final is not None:
                break
        if final is not None and clave:
            resultado = {
                "model": final.get("model"),
                "content": "".join(contenido),
                "thinking": "".join(razonamiento),
                "done_reason": final.get("done_reason"),
                "metricas": {k: final.get(k) for k in METRICAS_OLLAMA},
            }
            cache.set(clave, resultado)
            if fut is not None and not fut.done():
                fut.set_result(resultado)
    finally:
        if fut is not None:
            if not fut.done():
                fut.set_exception(RuntimeError("generación interrumpida"))
            if cache.en_curso.get(clave) is fut:
                del cache.en_curso[clave]
        await upstream.aclose()
        await client.aclose()


async def _obtener(payload: dict) -> AsyncIterator[dict]:
    """
    Devuelve un iterador de trozos (formato Ollama). Lanza HTTPException si
    no se puede contactar con el backend, ANTES de empezar a responder.
    """
    clave = _clave(payload) if cache.activa else None

    if clave:
        guardada = cache.get(clave)
        if guardada is not None:
            cache.aciertos += 1
            return _repetir(guardada, "hit")
        en_curso = cache.en_curso.get(clave)
        if en_curso is not None:
            try:
                resultado = await asyncio.wait_for(asyncio.shield(en_curso), REQUEST_TIMEOUT)
                cache.agrupadas += 1
                return _repetir(resultado, "agrupada")
            except Exception:  # noqa: BLE001 - la original falló: generamos por nuestra cuenta
                clave = None
        if clave:
            cache.fallos += 1

    fut = None
    if clave:
        fut = asyncio.get_running_loop().create_future()
        fut.add_done_callback(_marcar_recuperada)
        cache.en_curso[clave] = fut

    client = httpx.AsyncClient(timeout=_timeout())
    try:
        request = client.build_request("POST", f"{BACKEND_URL}/api/chat", json=payload, headers=_headers())
        upstream = await client.send(request, stream=True)
        if upstream.is_error:
            await upstream.aread()
            upstream.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        await client.aclose()
        if fut is not None:
            fut.set_exception(exc)
            cache.en_curso.pop(clave, None)
        raise _backend_error(exc)

    return _retransmitir(client, upstream, clave, fut)


async def _numerar(iterador: AsyncIterator[dict]):
    n = 0
    async for elemento in iterador:
        n += 1
        yield n, elemento


# --- Endpoints ---------------------------------------------------------------
@app.get("/health")
async def health():
    """Liveness: la API está viva (no comprueba Ollama). Lo usa el healthcheck de Docker."""
    return {"status": "ok"}


@app.get("/health/backend")
async def health_backend():
    """Comprueba que Ollama responde y que el modelo configurado está disponible."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
            r = await client.get(f"{BACKEND_URL}/api/tags", headers=_headers())
            r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        raise _backend_error(exc)
    models = [m.get("name") for m in r.json().get("models", [])]
    return {
        "status": "ok" if MODEL_NAME in models else "modelo_no_encontrado",
        "backend_url": BACKEND_URL,
        "modo": BACKEND_MODE,
        "modelo": MODEL_NAME,
        "modelos_disponibles": models,
    }


async def _detalles_backend() -> dict:
    """Cuantización y memoria del modelo en el backend (si responde rápido)."""
    detalles: dict[str, Any] = {}
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(4.0)) as client:
            r = await client.post(f"{BACKEND_URL}/api/show", json={"model": MODEL_NAME}, headers=_headers())
            if r.is_success:
                d = r.json().get("details", {})
                detalles.update({
                    "cuantizacion": d.get("quantization_level"),
                    "parametros_modelo": d.get("parameter_size"),
                    "familia": d.get("family"),
                })
            r = await client.get(f"{BACKEND_URL}/api/ps", headers=_headers())
            if r.is_success:
                for m in r.json().get("models", []):
                    if m.get("name") == MODEL_NAME or m.get("model") == MODEL_NAME:
                        detalles.update({
                            "memoria_modelo_bytes": m.get("size"),
                            "memoria_gpu_bytes": m.get("size_vram"),
                            "contexto": m.get("context_length"),
                        })
    except Exception:  # noqa: BLE001
        pass
    return detalles


@app.get("/api/info")
async def info():
    """A qué backend estamos conectados y qué optimizaciones están activas."""
    return {
        "backend_url": BACKEND_URL,
        "modo": BACKEND_MODE,
        "modelo": MODEL_NAME,
        "parametros": {"options": OPCIONES_POR_DEFECTO, "think": THINK_POR_DEFECTO},
        "cache": cache.estado(),
        "backend": await _detalles_backend(),
    }


@app.delete("/api/cache")
async def limpiar_cache():
    """Vacía la caché (lo usa el script de carga antes de cada escenario)."""
    cache.limpiar()
    return cache.estado()


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    """
    stream=false (por defecto): respuesta completa en JSON.
    stream=true: NDJSON en el mismo formato que Ollama, con las métricas
                 (eval_count, eval_duration...) y el campo "cache" en el último trozo.
    """
    trozos = await _obtener(_payload(req))

    if req.stream:
        async def ndjson():
            try:
                async for trozo in trozos:
                    yield json.dumps(trozo, ensure_ascii=False) + "\n"
            finally:
                await trozos.aclose()  # si el cliente corta, se corta también Ollama
        return StreamingResponse(ndjson(), media_type="application/x-ndjson")

    contenido, razonamiento, final = [], [], {}
    try:
        async for n, trozo in _numerar(trozos):
            # Sin streaming FastAPI no se entera de que el cliente se ha ido: lo comprobamos
            # cada pocos trozos para no dejar a Ollama generando para nadie.
            if n % 10 == 0 and await request.is_disconnected():
                break
            if trozo.get("error"):
                raise HTTPException(status_code=502, detail=f"Error del backend: {trozo['error']}")
            mensaje = trozo.get("message", {})
            contenido.append(mensaje.get("content", ""))
            razonamiento.append(mensaje.get("thinking") or "")
            if trozo.get("done"):
                final = trozo
    finally:
        await trozos.aclose()
    return {
        "reply": "".join(contenido),
        "thinking": "".join(razonamiento) or None,
        "modelo": final.get("model", req.model or MODEL_NAME),
        "modo": BACKEND_MODE,
        "cache": final.get("cache"),
        "done_reason": final.get("done_reason"),
        "metricas": {k: final.get(k) for k in METRICAS_OLLAMA},
    }


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """Texto plano trozo a trozo, para que el frontend pinte la respuesta en directo."""
    trozos = await _obtener(_payload(req))

    async def texto():
        try:
            async for trozo in trozos:
                if trozo.get("error"):
                    yield f"\n[error del backend: {trozo['error']}]"
                    break
                yield trozo.get("message", {}).get("content", "")
        finally:
            await trozos.aclose()

    return StreamingResponse(texto(), media_type="text/plain; charset=utf-8")
