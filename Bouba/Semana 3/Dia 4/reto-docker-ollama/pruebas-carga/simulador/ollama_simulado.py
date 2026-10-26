#!/usr/bin/env python3
"""
OLLAMA SIMULADO - solo para comprobar que carga.py e informe.py funcionan
sin descargar el modelo ni esperar. NO sirve para el informe de entrega:
todo lo que mide es inventado y el informe lo marca como "SIMULADO".

Imita la API de Ollama (/api/chat, /api/tags, /api/show, /api/ps) con:
  - N peticiones en paralelo (--paralelo) y el resto en cola (--cola => 503)
  - velocidad que se reparte entre las peticiones activas, como una CPU real
  - límite de tokens (options.num_predict) y razonamiento opcional (think)
  - métricas falsas de CPU/RAM en /metricas (formato de agente_metricas.py)

Ejemplo:
  python simulador/ollama_simulado.py --puerto 11500 --acelerar 10
  python carga.py --tipo ollama --url http://localhost:11500 --modelo gemma4:e4b \
      --backend local --fase prueba --recursos http://localhost:11500/metricas --timeout 15
"""

import argparse
import asyncio
import hashlib
import json
import random
import time

from aiohttp import web

PALABRAS = (
    "Docker contenedor imagen red volumen servicio puerto Linux servidor sistema permite "
    "configurar aplicación datos usuario proceso archivo memoria rendimiento seguridad "
    "ejemplo primero después además también cada entre forma manera puede debe cuando"
).split()


class Simulador:
    def __init__(self, a):
        self.a = a
        self.activos = 0
        self.esperando = 0
        self.slots = asyncio.Semaphore(a.paralelo)

    # --- Modelo de rendimiento ---------------------------------------------
    def factor_modelo(self, modelo: str) -> float:
        return 1.35 if any(q in modelo for q in ("qat", "q4")) else 1.0

    def tasa(self, modelo: str) -> float:
        """Tokens/s que recibe cada petición activa (la capacidad total crece menos que lineal)."""
        k = max(1, self.activos)
        return self.a.tok_s * self.factor_modelo(modelo) * k ** self.a.escalado / k

    async def dormir(self, segundos: float):
        await asyncio.sleep(segundos / self.a.acelerar)

    @staticmethod
    def longitud(texto: str, minimo: int, maximo: int) -> int:
        h = int(hashlib.md5(texto.encode()).hexdigest(), 16)
        return minimo + h % (maximo - minimo + 1)

    # --- Endpoints -------------------------------------------------------------
    async def chat(self, request: web.Request):
        cuerpo = await request.json()
        modelo = cuerpo.get("model", "gemma4:e4b")
        opciones = cuerpo.get("options") or {}
        texto = " ".join(m.get("content", "") for m in cuerpo.get("messages", []))
        stream = cuerpo.get("stream", True)
        razona = cuerpo.get("think") if cuerpo.get("think") is not None else self.a.razona
        llegada = time.perf_counter()

        if self.esperando >= self.a.cola:
            return web.json_response(
                {"error": "server busy, please try again.  maximum pending requests exceeded"}, status=503)

        self.esperando += 1
        try:
            await self.slots.acquire()
        finally:
            self.esperando -= 1
        self.activos += 1
        try:
            await self.dormir(self.a.latencia_red / 1000)
            tokens_prompt = max(8, len(texto) // 4)
            ini_prompt = time.perf_counter()
            await self.dormir(tokens_prompt / self.a.prefill_tok_s)
            t_prompt = time.perf_counter() - ini_prompt

            n_razon = self.longitud("r" + texto, 120, 380) if razona else 0
            n_contenido = self.longitud(texto, 160, 520)
            limite = opciones.get("num_predict")
            if limite and limite > 0:
                n_razon = min(n_razon, limite)
                n_contenido = min(n_contenido, limite - n_razon)
            truncada = bool(limite) and (n_razon + n_contenido) >= limite
            rng = random.Random(texto)

            respuesta = web.StreamResponse(headers={"Content-Type": "application/x-ndjson", "X-Ollama-Simulado": "1"})
            if stream:
                try:
                    await respuesta.prepare(request)
                except (ConnectionResetError, RuntimeError):
                    return respuesta
            contenido_total = []
            ini_gen = time.perf_counter()
            for i in range(n_razon + n_contenido):
                await self.dormir(1 / self.tasa(modelo))
                palabra = rng.choice(PALABRAS) + " "
                campo = "thinking" if i < n_razon else "content"
                if campo == "content":
                    contenido_total.append(palabra)
                if stream:
                    trozo = {"model": modelo, "message": {"role": "assistant", "content": "", campo: palabra}, "done": False}
                    try:
                        await respuesta.write((json.dumps(trozo) + "\n").encode())
                    except (ConnectionResetError, RuntimeError):
                        return respuesta  # el cliente se ha ido: se libera el hueco
            t_gen = time.perf_counter() - ini_gen

            final = {
                "model": modelo, "message": {"role": "assistant", "content": ""}, "done": True,
                "done_reason": "length" if truncada else "stop",
                "total_duration": int((time.perf_counter() - llegada) * 1e9),
                "load_duration": int(0.05e9),
                "prompt_eval_count": tokens_prompt, "prompt_eval_duration": int(t_prompt * 1e9),
                "eval_count": n_razon + n_contenido, "eval_duration": int(t_gen * 1e9),
                "simulado": True,
            }
            if not stream:
                final["message"]["content"] = "".join(contenido_total)
                return web.json_response(final, headers={"X-Ollama-Simulado": "1"})
            try:
                await respuesta.write((json.dumps(final) + "\n").encode())
                await respuesta.write_eof()
            except (ConnectionResetError, RuntimeError):
                pass
            return respuesta
        finally:
            self.activos -= 1
            self.slots.release()

    async def tags(self, _):
        return web.json_response({"models": [{"name": m} for m in self.a.modelos]})

    async def show(self, request):
        modelo = (await request.json()).get("model", "")
        cuant = self.a.cuantizacion_qat if self.factor_modelo(modelo) > 1 else self.a.cuantizacion
        return web.json_response({"details": {
            "family": "simulado", "parameter_size": self.a.tamano, "quantization_level": cuant}})

    async def ps(self, _):
        return web.json_response({"models": [{"name": m, "model": m, "size": int(self.a.ram_modelo_gb * 1024 ** 3),
                                              "size_vram": 0} for m in self.a.modelos[:1]]})

    async def raiz(self, _):
        return web.Response(text="Ollama is running (SIMULADO)")

    async def metricas(self, _):
        """CPU/RAM inventadas en el formato de agente_metricas.py."""
        k = self.activos
        ruido = random.uniform(-4, 4)
        ram = self.a.ram_modelo_gb + self.a.ram_slot_gb * (self.a.paralelo if k else 0) + 1.2
        if self.a.gpu:
            cpu = 6 + 2 * k + ruido / 2
            gpu = [{"nombre": "GPU simulada", "util_pct": max(0, min(99, 50 + 12 * k + ruido)) if k else 1,
                    "mem_gb": self.a.ram_modelo_gb + self.a.ram_slot_gb * self.a.paralelo, "mem_total_gb": 24}]
            ram = 3.5 + ruido / 10
        else:
            cpu = (min(97, 52 + 12 * k + ruido) if k else 3 + abs(ruido) / 2)
            gpu = []
        return web.json_response({
            "host": "simulado",
            "sistema": {"cpus": 8, "cpu_pct": max(0.0, cpu), "ram_gb": max(0.5, ram), "ram_total_gb": self.a.ram_total_gb},
            "gpu": gpu,
        })


def main():
    p = argparse.ArgumentParser(description="Ollama simulado para probar las pruebas de carga")
    p.add_argument("--puerto", type=int, default=11500)
    p.add_argument("--modelos", nargs="+", default=["gemma4:e4b", "gemma4:e4b-it-qat"])
    p.add_argument("--paralelo", type=int, default=1, help="como OLLAMA_NUM_PARALLEL")
    p.add_argument("--cola", type=int, default=512, help="como OLLAMA_MAX_QUEUE")
    p.add_argument("--tok-s", type=float, default=11, help="tokens/s con una sola petición")
    p.add_argument("--escalado", type=float, default=0.4, help="0 = no escala con el paralelo, 1 = lineal")
    p.add_argument("--prefill-tok-s", type=float, default=90)
    p.add_argument("--latencia-red", type=float, default=0, help="ms añadidos por petición")
    p.add_argument("--razona", action="store_true", help="genera tokens de razonamiento si no se pide think=false")
    p.add_argument("--acelerar", type=float, default=1, help="divide todos los tiempos (para pruebas rápidas)")
    p.add_argument("--cuantizacion", default="Q8_0")
    p.add_argument("--cuantizacion-qat", default="Q4_0")
    p.add_argument("--tamano", default="8.0B")
    p.add_argument("--ram-modelo-gb", type=float, default=9.6)
    p.add_argument("--ram-slot-gb", type=float, default=0.35)
    p.add_argument("--ram-total-gb", type=float, default=15.6)
    p.add_argument("--gpu", action="store_true", help="simula una máquina con GPU")
    a = p.parse_args()

    sim = Simulador(a)
    app = web.Application()
    app.add_routes([
        web.get("/", sim.raiz), web.post("/api/chat", sim.chat), web.get("/api/tags", sim.tags),
        web.post("/api/show", sim.show), web.get("/api/ps", sim.ps), web.get("/metricas", sim.metricas),
    ])
    print(f"Ollama SIMULADO en http://localhost:{a.puerto}  (paralelo={a.paralelo}, acelerar={a.acelerar})")
    web.run_app(app, port=a.puerto, print=None)


if __name__ == "__main__":
    main()
