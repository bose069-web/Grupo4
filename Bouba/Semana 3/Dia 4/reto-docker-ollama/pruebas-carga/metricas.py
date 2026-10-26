"""
Cálculo de métricas a partir de los resultados brutos de carga.py.
Lo usan carga.py (resumen en consola) e informe.py (tablas y gráficas).
"""

import math
from collections import Counter

ES_CACHE = {"hit", "agrupada"}  # respuestas que no pasaron por el modelo


def percentil(valores, p: float):
    v = sorted(x for x in valores if x is not None)
    if not v:
        return None
    k = (len(v) - 1) * p / 100
    f, c = math.floor(k), math.ceil(k)
    return v[f] + (v[c] - v[f]) * (k - f)


def media(valores):
    v = [x for x in valores if x is not None]
    return sum(v) / len(v) if v else None


def maximo(valores):
    v = [x for x in valores if x is not None]
    return max(v) if v else None


def _pct(parte, total):
    return 100.0 * parte / total if total else None


def resumir_recursos(muestras: list[dict], desde: float, hasta: float) -> dict:
    """Media y máximo por fuente dentro de la ventana de tiempo del escenario."""
    por_fuente: dict[str, list[dict]] = {}
    for m in muestras:
        if desde <= m["t"] <= hasta:
            por_fuente.setdefault(m["fuente"], []).append(m)
    resumen = {}
    for fuente, ms in por_fuente.items():
        resumen[fuente] = {
            "nivel": ms[0].get("nivel"),
            "muestras": len(ms),
            "cpu_media_pct": media(m.get("cpu_pct") for m in ms),
            "cpu_max_pct": maximo(m.get("cpu_pct") for m in ms),
            "ram_media_gb": media(m.get("ram_gb") for m in ms),
            "ram_max_gb": maximo(m.get("ram_gb") for m in ms),
            "ram_total_gb": maximo(m.get("ram_total_gb") for m in ms),
            "gpu_media_pct": media(m.get("gpu_pct") for m in ms),
            "gpu_max_pct": maximo(m.get("gpu_pct") for m in ms),
            "gpu_mem_max_gb": maximo(m.get("gpu_mem_gb") for m in ms),
        }
    return resumen


def recurso_principal(recursos: dict) -> dict:
    """
    Elige qué fuente representa al backend: el contenedor de Ollama si se midió,
    si no el sistema completo. La GPU se toma de cualquier fuente que la tenga.
    """
    def prioridad(item):
        fuente, r = item
        if r.get("nivel") == "contenedor":
            return 0
        return 1 if fuente.startswith("agente") else 2  # la máquina remota antes que el equipo cliente

    candidatos = sorted(
        ((f, r) for f, r in recursos.items() if r.get("nivel") in ("contenedor", "sistema")
         and r.get("cpu_media_pct") is not None),
        key=prioridad,
    )
    elegido = {"fuente": candidatos[0][0], **candidatos[0][1]} if candidatos else {}
    for r in recursos.values():
        if r.get("gpu_media_pct") is not None:
            elegido.update({k: r[k] for k in ("gpu_media_pct", "gpu_max_pct", "gpu_mem_max_gb")})
            break
    return elegido


def resumir_escenario(peticiones: list[dict], muestras: list[dict]) -> dict:
    ok = [p for p in peticiones if p["estado"] == "ok"]
    generadas = [p for p in ok if p.get("cache") not in ES_CACHE]
    errores = [p for p in peticiones if p["estado"] != "ok"]

    desde = min((p["t_inicio"] for p in peticiones), default=0.0)
    hasta = max((p["t_fin"] for p in peticiones), default=0.0)
    duracion = max(hasta - desde, 1e-9)

    espera = [
        p["latencia"] - (p.get("t_prompt") or 0) - (p.get("t_generacion") or 0)
        for p in generadas if p.get("t_generacion") is not None
    ]
    latencia_generadas = media(p["latencia"] for p in generadas)
    chars_razon = sum(p.get("chars_razonamiento") or 0 for p in ok)
    chars_total = chars_razon + sum(p.get("chars_contenido") or 0 for p in ok)
    hay_cache = any(p.get("cache") is not None for p in ok)

    return {
        "usuarios": peticiones[0]["escenario"] if peticiones else None,
        "peticiones": len(peticiones),
        "ok": len(ok),
        "errores": len(errores),
        "tasa_error_pct": _pct(len(errores), len(peticiones)),
        "errores_por_tipo": dict(Counter(p["error_tipo"] for p in errores)),
        "ventana": [round(desde, 2), round(hasta, 2)],
        "duracion_s": duracion,
        "latencia_media_s": media(p["latencia"] for p in ok),
        "latencia_p50_s": percentil([p["latencia"] for p in ok], 50),
        "latencia_p95_s": percentil([p["latencia"] for p in ok], 95),
        "latencia_max_s": maximo(p["latencia"] for p in ok),
        "ttft_p50_s": percentil([p["ttft"] for p in ok], 50),
        "ttft_p95_s": percentil([p["ttft"] for p in ok], 95),
        "tok_s_por_peticion": media(p.get("tok_s") for p in generadas),
        "tok_s_total": sum(p.get("tokens_salida") or 0 for p in generadas) / duracion,
        "peticiones_por_min": 60.0 * len(ok) / duracion,
        "tokens_salida_media": media(p.get("tokens_salida") for p in ok),
        "cache_pct": _pct(sum(p.get("cache") in ES_CACHE for p in ok), len(ok)) if hay_cache else None,
        "repetidos_pct": _pct(sum(bool(p.get("repetido")) for p in peticiones), len(peticiones)),
        "espera_media_s": media(espera),
        "prefill_media_s": media(p.get("t_prompt") for p in generadas),
        "generacion_media_s": media(p.get("t_generacion") for p in generadas),
        "espera_pct": _pct(media(espera) or 0, latencia_generadas) if espera and latencia_generadas else None,
        "truncadas_pct": _pct(sum(p.get("done_reason") == "length" for p in ok), len(ok)),
        "razonamiento_pct": _pct(chars_razon, chars_total),
        "recursos": resumir_recursos(muestras, desde, hasta),
    }


# --- Formato para consola ------------------------------------------------------
def fmt(valor, decimales=1, sufijo=""):
    if valor is None:
        return "-"
    return f"{valor:.{decimales}f}{sufijo}"


def tabla_consola(resumenes: list[dict]) -> str:
    cab = ["usuarios", "ok/total", "err%", "p50 s", "p95 s", "TTFT p95", "tok/s pet", "tok/s total", "cache%", "CPU%", "RAM GB"]
    filas = []
    for r in resumenes:
        rp = recurso_principal(r["recursos"])
        filas.append([
            str(r["usuarios"]), f"{r['ok']}/{r['peticiones']}", fmt(r["tasa_error_pct"], 0),
            fmt(r["latencia_p50_s"]), fmt(r["latencia_p95_s"]), fmt(r["ttft_p95_s"]),
            fmt(r["tok_s_por_peticion"]), fmt(r["tok_s_total"]), fmt(r["cache_pct"], 0),
            fmt(rp.get("cpu_media_pct"), 0), fmt(rp.get("ram_max_gb")),
        ])
    anchos = [max([len(c)] + [len(f[i]) for f in filas]) for i, c in enumerate(cab)]
    lineas = ["  ".join(c.rjust(a) for c, a in zip(cab, anchos))]
    lineas.append("  ".join("-" * a for a in anchos))
    lineas += ["  ".join(v.rjust(a) for v, a in zip(f, anchos)) for f in filas]
    return "\n".join(lineas)
