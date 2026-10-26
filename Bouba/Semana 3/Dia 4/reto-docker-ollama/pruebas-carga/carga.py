#!/usr/bin/env python3
"""
Pruebas de estrés del chat con Gemma 4 (asyncio + aiohttp).

Lanza N usuarios simultáneos (por defecto 5, 10 y 20). Cada usuario hace varias
preguntas seguidas y se mide, por petición:
  - latencia total y tiempo hasta el primer token (TTFT)
  - tokens generados y tokens/segundo (según las métricas de Ollama)
  - errores (timeout, 5xx, conexión, respuesta vacía...)
y, en segundo plano, el uso de CPU, RAM y GPU del backend.

Ejemplos (desde la carpeta pruebas-carga):
  # Backend local a través de la API del stack (http://localhost:8000)
  python carga.py --backend local --fase antes

  # Backend remoto (la API apunta al remoto) midiendo la máquina remota
  python carga.py --backend remoto --fase antes --recursos http://IP_REMOTA:9101

  # Directamente contra un Ollama (sin pasar por la API)
  python carga.py --tipo ollama --url http://localhost:11435 --modelo gemma4:e4b --backend local --fase antes

Los resultados se guardan en resultados/<fase>__<backend>__<fecha>.json (+ .csv).
Después: python informe.py
"""

import argparse
import asyncio
import csv
import json
import platform
import random
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import aiohttp

import metricas
import recursos

VERSION = "1.0"
CARPETA = Path(__file__).resolve().parent
SISTEMA_POR_DEFECTO = "Eres un asistente útil. Responde en español de forma clara y breve."
CAMPOS_CSV = [
    "escenario", "usuario", "n", "prompt_id", "repetido", "t_inicio", "t_fin", "latencia", "ttft",
    "ttft_contenido", "estado", "error_tipo", "error", "http_status", "tokens_entrada", "tokens_salida",
    "t_prompt", "t_generacion", "t_carga", "t_total_servidor", "tok_s", "cache", "done_reason",
    "chars_contenido", "chars_razonamiento",
]


class ErrorBackend(Exception):
    pass


# --- Una petición --------------------------------------------------------------
async def peticion(session: aiohttp.ClientSession, cfg, prompt: str, t0: float) -> dict:
    cuerpo = {"messages": [{"role": "user", "content": prompt}], "stream": True}
    if cfg.tipo == "ollama":
        cuerpo["messages"].insert(0, {"role": "system", "content": cfg.sistema})
    if cfg.modelo:
        cuerpo["model"] = cfg.modelo
    if cfg.opciones:
        cuerpo["options"] = cfg.opciones
    if cfg.think is not None:
        cuerpo["think"] = cfg.think

    r = {campo: None for campo in CAMPOS_CSV}
    inicio = time.perf_counter()
    r["t_inicio"] = round(inicio - t0, 3)
    chars_contenido = chars_razon = 0
    final = None
    try:
        async with session.post(cfg.url_chat, json=cuerpo, timeout=aiohttp.ClientTimeout(total=cfg.timeout)) as resp:
            r["http_status"] = resp.status
            if resp.headers.get("X-Ollama-Simulado"):
                cfg.simulado = True
            if resp.status != 200:
                texto = await resp.text()
                raise ErrorBackend(f"HTTP {resp.status}: {texto[:200]}")

            pendiente = b""

            def procesar(linea: bytes):
                nonlocal chars_contenido, chars_razon, final
                if not linea.strip():
                    return
                trozo = json.loads(linea)
                if trozo.get("error"):
                    raise ErrorBackend(str(trozo["error"])[:200])
                mensaje = trozo.get("message") or {}
                contenido = mensaje.get("content") or ""
                razon = mensaje.get("thinking") or ""
                if (contenido or razon) and r["ttft"] is None:
                    r["ttft"] = time.perf_counter() - inicio
                if contenido and r["ttft_contenido"] is None:
                    r["ttft_contenido"] = time.perf_counter() - inicio
                chars_contenido += len(contenido)
                chars_razon += len(razon)
                if trozo.get("done"):
                    final = trozo

            async for bloque in resp.content.iter_any():
                pendiente += bloque
                while b"\n" in pendiente:
                    linea, pendiente = pendiente.split(b"\n", 1)
                    procesar(linea)
            procesar(pendiente)

        if final is None:
            raise ErrorBackend("la respuesta terminó sin el mensaje final (done)")
        if final.get("simulado"):
            cfg.simulado = True
        if chars_contenido == 0:
            r["error_tipo"] = "respuesta_vacia"
            raise ErrorBackend("el modelo no devolvió texto (¿se agotó num_predict razonando?)")
        r["estado"] = "ok"
    except (asyncio.TimeoutError, TimeoutError):
        r.update(estado="error", error_tipo="timeout", error=f"sin respuesta completa en {cfg.timeout:.0f}s")
    except ErrorBackend as exc:
        tipo = r["error_tipo"] or (f"http_{r['http_status']}" if r["http_status"] not in (None, 200) else "backend")
        r.update(estado="error", error_tipo=tipo, error=str(exc))
    except aiohttp.ClientConnectorError as exc:
        r.update(estado="error", error_tipo="conexion", error=str(exc)[:200])
    except aiohttp.ClientError as exc:
        r.update(estado="error", error_tipo="red", error=f"{type(exc).__name__}: {exc}"[:200])
    except json.JSONDecodeError as exc:
        r.update(estado="error", error_tipo="respuesta_invalida", error=str(exc)[:200])

    fin = time.perf_counter()
    r["t_fin"] = round(fin - t0, 3)
    r["latencia"] = fin - inicio
    r["chars_contenido"], r["chars_razonamiento"] = chars_contenido, chars_razon
    if final:
        ns = 1e9
        r["tokens_entrada"] = final.get("prompt_eval_count")
        r["tokens_salida"] = final.get("eval_count")
        r["t_prompt"] = (final.get("prompt_eval_duration") or 0) / ns or None
        r["t_generacion"] = (final.get("eval_duration") or 0) / ns or None
        r["t_carga"] = (final.get("load_duration") or 0) / ns or None
        r["t_total_servidor"] = (final.get("total_duration") or 0) / ns or None
        r["cache"] = final.get("cache")
        r["done_reason"] = final.get("done_reason")
        if r["tokens_salida"] and r["t_generacion"] and r["cache"] not in metricas.ES_CACHE:
            r["tok_s"] = r["tokens_salida"] / r["t_generacion"]
    return r


# --- Escenario: N usuarios simultáneos -----------------------------------------
def plan_de_prompts(cfg, usuarios: int, n_prompts: int) -> list[list[int]]:
    """
    Qué pregunta hace cada usuario. Es determinista (misma semilla => mismas
    preguntas), así "antes" y "después" o local y remoto reciben la misma carga.
    Con --zipf > 0 unas preguntas se repiten más que otras, como en un chat real.
    """
    rng = random.Random(f"{cfg.semilla}-{usuarios}")
    pesos = [1 / (i + 1) ** cfg.zipf for i in range(n_prompts)]
    ids = rng.choices(range(n_prompts), weights=pesos, k=usuarios * cfg.peticiones_por_usuario)
    k = cfg.peticiones_por_usuario
    return [ids[u * k:(u + 1) * k] for u in range(usuarios)]


async def usuario(uid, session, cfg, plan, prompts, t0, resultados, escenario):
    rng = random.Random(f"{cfg.semilla}-{escenario}-{uid}")
    await asyncio.sleep(rng.uniform(0, 0.5))  # todos casi a la vez
    for n, prompt_id in enumerate(plan):
        if n > 0 and cfg.pensar > 0:
            await asyncio.sleep(rng.uniform(0, cfg.pensar))  # "tiempo de lectura" del usuario
        r = await peticion(session, cfg, prompts[prompt_id], t0)
        r.update(escenario=escenario, usuario=uid, n=n, prompt_id=prompt_id)
        resultados.append(r)


async def limpiar_cache(session, cfg):
    if cfg.tipo != "api" or not cfg.limpiar_cache:
        return
    try:
        async with session.delete(cfg.url.rstrip("/") + "/api/cache", timeout=aiohttp.ClientTimeout(total=10)):
            pass
    except Exception:  # noqa: BLE001
        pass


async def escenario(session, cfg, usuarios: int, prompts: list[str], t0: float) -> list[dict]:
    await limpiar_cache(session, cfg)
    resultados: list[dict] = []
    planes = plan_de_prompts(cfg, usuarios, len(prompts))
    total = usuarios * cfg.peticiones_por_usuario
    inicio = time.perf_counter()

    async def progreso():
        while True:
            await asyncio.sleep(10)
            ok = sum(r["estado"] == "ok" for r in resultados)
            print(f"    {len(resultados)}/{total} terminadas (ok {ok}, error {len(resultados) - ok})"
                  f" - {time.perf_counter() - inicio:.0f} s", flush=True)

    tarea_progreso = asyncio.create_task(progreso())
    try:
        await asyncio.gather(*(
            usuario(u, session, cfg, planes[u], prompts, t0, resultados, usuarios) for u in range(usuarios)
        ))
    finally:
        tarea_progreso.cancel()

    # ¿La pregunta ya se había hecho antes en este escenario? (para interpretar la caché)
    vistos = set()
    for r in sorted(resultados, key=lambda x: x["t_inicio"]):
        r["repetido"] = r["prompt_id"] in vistos
        vistos.add(r["prompt_id"])
    return resultados


# --- Información del backend y calentamiento ---------------------------------
async def info_backend(session, cfg) -> dict:
    base = cfg.url.rstrip("/")
    t = aiohttp.ClientTimeout(total=15)
    if cfg.tipo == "api":
        async with session.get(base + "/api/info", timeout=t) as r:
            r.raise_for_status()
            return await r.json()

    async with session.get(base + "/api/tags", timeout=t) as r:
        r.raise_for_status()
        modelos = [m.get("name") for m in (await r.json()).get("models", [])]
    if cfg.modelo not in modelos:
        raise SystemExit(f"El modelo '{cfg.modelo}' no está en {base}. Disponibles: {', '.join(modelos) or 'ninguno'}")
    info = {"backend_url": base, "modelo": cfg.modelo, "backend": {}}
    async with session.post(base + "/api/show", json={"model": cfg.modelo}, timeout=t) as r:
        if r.status == 200:
            d = (await r.json()).get("details", {})
            info["backend"] = {"cuantizacion": d.get("quantization_level"), "parametros_modelo": d.get("parameter_size")}
    return info


async def calentar(session, cfg) -> dict:
    """Primera petición para que el modelo se cargue en memoria (no cuenta en las métricas)."""
    print("Calentamiento: cargando el modelo en memoria...", flush=True)
    r = await peticion(session, cfg, "Responde solo con la palabra: listo", time.perf_counter())
    if r["estado"] != "ok":
        print(f"  AVISO: el calentamiento falló ({r['error_tipo']}: {r['error']})")
    else:
        print(f"  listo en {r['latencia']:.1f} s (carga del modelo {metricas.fmt(r['t_carga'])} s)")
    return {k: r[k] for k in ("estado", "error_tipo", "latencia", "t_carga", "tokens_salida", "tok_s")}


def preparar_fuentes_auto(cfg) -> list[str]:
    if cfg.recursos:
        return cfg.recursos
    if cfg.backend.lower().startswith("local"):
        return ["docker:ollama", "host", "gpu"]
    return ["docker:ollama-remoto", "host"]


# --- Guardado ----------------------------------------------------------------
def nombre_seguro(texto: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", texto).strip("-") or "x"


def guardar(ruta: Path, datos: dict):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ruta)
    with ruta.with_suffix(".csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS_CSV, extrasaction="ignore")
        w.writeheader()
        for p in datos["peticiones"]:
            w.writerow(p)


# --- Programa principal --------------------------------------------------------
async def main_async(cfg):
    prompts = [l.strip() for l in Path(cfg.prompts).read_text(encoding="utf-8").splitlines()
               if l.strip() and not l.lstrip().startswith("#")]
    if not prompts:
        raise SystemExit(f"No hay preguntas en {cfg.prompts}")
    usuarios_lista = [int(x) for x in cfg.usuarios.split(",")]

    sello = datetime.now().strftime("%Y%m%d-%H%M%S")
    ruta = Path(cfg.salida) / f"{nombre_seguro(cfg.fase)}__{nombre_seguro(cfg.backend)}__{sello}.json"
    t0 = time.perf_counter()

    conector = aiohttp.TCPConnector(limit=max(usuarios_lista) + 10)
    async with aiohttp.ClientSession(connector=conector) as session:
        try:
            info = await info_backend(session, cfg)
        except SystemExit:
            raise
        except Exception as exc:  # noqa: BLE001
            raise SystemExit(f"No se puede contactar con {cfg.url}: {exc}")

        modelo = cfg.modelo or info.get("modelo")
        print(f"\n=== Prueba de carga: fase '{cfg.fase}', backend '{cfg.backend}' ===")
        print(f"Destino: {cfg.url} ({cfg.tipo})  ->  Ollama {info.get('backend_url')}  modelo {modelo}"
              f"  cuantización {info.get('backend', {}).get('cuantizacion') or '?'}")
        if cfg.tipo == "api":
            p = info.get("parametros", {})
            print(f"Optimizaciones en la API: caché {'SÍ' if info.get('cache', {}).get('activa') else 'no'}"
                  f" | opciones {p.get('options') or 'por defecto'} | think {p.get('think')}")

        # Fuentes de recursos
        muestreadores, hardware = [], {}
        for especificacion in preparar_fuentes_auto(cfg):
            m = recursos.crear(especificacion)
            try:
                hardware[m.nombre] = await m.preparar()
                muestreadores.append(m)
                print(f"Recursos: midiendo {m.nombre} {hardware[m.nombre]}")
            except Exception as exc:  # noqa: BLE001
                await m.cerrar()
                print(f"Recursos: {m.nombre} no disponible ({exc}), se omite")
        if not cfg.backend.lower().startswith("local") and not any(m.nombre.startswith("agente") for m in muestreadores):
            print("  AVISO: para medir CPU/RAM de una máquina remota real usa --recursos http://IP:9101"
                  " (agente_metricas.py en esa máquina)")

        calentamiento = None if cfg.sin_calentamiento else await calentar(session, cfg)

        datos = {
            "meta": {
                "version": VERSION, "fase": cfg.fase, "backend": cfg.backend, "tipo": cfg.tipo, "url": cfg.url,
                "modelo": modelo, "inicio": datetime.now().isoformat(timespec="seconds"), "fin": None,
                "completo": False, "simulado": False,
                "config": {
                    "usuarios": usuarios_lista, "peticiones_por_usuario": cfg.peticiones_por_usuario,
                    "timeout_s": cfg.timeout, "pensar_max_s": cfg.pensar, "semilla": cfg.semilla,
                    "zipf": cfg.zipf, "n_prompts": len(prompts), "opciones": cfg.opciones, "think": cfg.think,
                },
                "backend_info": info, "hardware": hardware, "calentamiento": calentamiento,
                "cliente": {"equipo": platform.node(), "so": platform.platform(), "python": platform.python_version()},
            },
            "escenarios": [], "peticiones": [], "recursos": [],
        }

        monitor = recursos.Monitor(muestreadores, cfg.intervalo_recursos, t0)
        monitor.iniciar()
        try:
            for i, n in enumerate(usuarios_lista, 1):
                print(f"\nEscenario {i}/{len(usuarios_lista)}: {n} usuarios x {cfg.peticiones_por_usuario}"
                      f" peticiones (timeout {cfg.timeout:.0f} s)", flush=True)
                resultados = await escenario(session, cfg, n, prompts, t0)
                await asyncio.sleep(cfg.intervalo_recursos + 0.5)  # última muestra de recursos
                resumen = metricas.resumir_escenario(resultados, monitor.muestras)
                datos["escenarios"].append(resumen)
                datos["peticiones"] += resultados
                datos["recursos"] = monitor.muestras
                datos["meta"]["simulado"] = cfg.simulado
                guardar(ruta, datos)  # se guarda tras cada escenario por si se interrumpe
                print(metricas.tabla_consola([resumen]))
                if resumen["errores_por_tipo"]:
                    print(f"  errores: {resumen['errores_por_tipo']}")
                if i < len(usuarios_lista):
                    print(f"  pausa de {cfg.pausa:.0f} s para que el backend se vacíe...", flush=True)
                    await asyncio.sleep(cfg.pausa)
        finally:
            await monitor.parar()

        datos["meta"].update(fin=datetime.now().isoformat(timespec="seconds"), completo=True,
                             simulado=cfg.simulado, recursos_errores=monitor.errores)
        datos["recursos"] = monitor.muestras
        guardar(ruta, datos)

    print(f"\n=== Resumen fase '{cfg.fase}', backend '{cfg.backend}' ===")
    print(metricas.tabla_consola(datos["escenarios"]))
    print(f"\nResultados: {ruta}\n            {ruta.with_suffix('.csv')}")
    print("Siguiente paso: python informe.py")


def leer_args(argv=None):
    p = argparse.ArgumentParser(
        description="Pruebas de estrés del chat (asyncio + aiohttp)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--backend", required=True, help="etiqueta del backend: local, remoto, azure...")
    p.add_argument("--fase", required=True, help="etiqueta de la fase: antes, despues, opt-cache...")
    p.add_argument("--url", default="http://localhost:8000", help="URL de la API (o de Ollama con --tipo ollama)")
    p.add_argument("--tipo", choices=["api", "ollama"], default="api", help="a qué se conecta el script")
    p.add_argument("--modelo", help="modelo (obligatorio con --tipo ollama)")
    p.add_argument("--usuarios", default="5,10,20", help="escenarios: usuarios simultáneos")
    p.add_argument("--peticiones-por-usuario", type=int, default=2)
    p.add_argument("--timeout", type=float, default=120, help="segundos máximos por petición")
    p.add_argument("--pensar", type=float, default=2, help="pausa máxima (s) entre preguntas de un usuario")
    p.add_argument("--pausa", type=float, default=15, help="pausa (s) entre escenarios")
    p.add_argument("--prompts", default=str(CARPETA / "prompts.txt"))
    p.add_argument("--zipf", type=float, default=1.0, help="0 = preguntas al azar; >0 = unas se repiten más")
    p.add_argument("--semilla", type=int, default=42)
    p.add_argument("--opciones", type=json.loads, help="opciones de Ollama en JSON, p. ej. '{\"num_predict\":256}'")
    p.add_argument("--think", type=lambda s: s.lower() in ("1", "true", "si", "sí"), help="true/false")
    p.add_argument("--sistema", default=SISTEMA_POR_DEFECTO, help="prompt de sistema (solo --tipo ollama)")
    p.add_argument("--recursos", action="append",
                   help="docker:<servicio>, host, gpu o http://IP:9101 (repetible). Por defecto: automático")
    p.add_argument("--intervalo-recursos", type=float, default=2.0)
    p.add_argument("--sin-calentamiento", action="store_true")
    p.add_argument("--no-limpiar-cache", dest="limpiar_cache", action="store_false",
                   help="no vaciar la caché de la API antes de cada escenario")
    p.add_argument("--salida", default=str(CARPETA / "resultados"))
    cfg = p.parse_args(argv)
    if cfg.tipo == "ollama" and not cfg.modelo:
        p.error("con --tipo ollama hay que indicar --modelo")
    base = cfg.url.rstrip("/")
    cfg.url_chat = base + "/api/chat"
    cfg.simulado = False
    return cfg


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cfg = leer_args()
    try:
        asyncio.run(main_async(cfg))
    except KeyboardInterrupt:
        print("\nInterrumpido. Los escenarios ya terminados están guardados en la carpeta de resultados.")


if __name__ == "__main__":
    main()
