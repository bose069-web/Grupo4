#!/usr/bin/env python3
"""
Genera el informe comparativo de las pruebas de carga:
  - local vs remoto en cada escenario (5, 10, 20 usuarios)
  - antes vs después de las optimizaciones
  - cuellos de botella detectados automáticamente
  - gráficas de rendimiento y de uso de recursos

Uso (desde la carpeta pruebas-carga):
  python informe.py                          # última ejecución de cada fase + backend
  python informe.py --fases antes,despues    # elegir fases y su orden

Salida en informe/:
  informe.html   (autocontenido, para ver o imprimir a PDF)
  informe.md     (para el repositorio; usa las imágenes de graficas/)
  graficas/*.png
  resumen.csv    (una fila por fase, backend y escenario)

Si existe conclusiones.md en esta carpeta, se añade al final del informe.
"""

import argparse
import base64
import csv
import html
import json
import re
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

import metricas as M  # noqa: E402

CARPETA = Path(__file__).resolve().parent

# --- Umbrales para detectar cuellos de botella (ajústalos si quieres) ----------
UMBRAL_TTFT_P95 = 10.0   # s: más de esto hasta ver la primera palabra = mala experiencia
UMBRAL_ERRORES = 5.0     # % de peticiones fallidas
UMBRAL_CPU = 85.0        # % de CPU media
UMBRAL_GPU = 90.0        # % de GPU media
UMBRAL_RAM = 0.90        # fracción de la RAM disponible
UMBRAL_COLA = 50.0       # % de la latencia esperando turno
UMBRAL_ESCALADO = 1.15   # si al subir usuarios los tokens/s totales crecen menos de un 15% => saturado

# --- Estilo de las gráficas (paleta categórica validada para daltonismo) -------
PALETA = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SUPERFICIE, TINTA, TINTA2, TENUE = "#fcfcfb", "#0b0b0b", "#52514e", "#898781"
REJILLA, EJE, BANDA = "#e1e0d9", "#c3c2b7", "#f0efec"
CRITICO, BUENO_TXT = "#d03b3b", "#006300"

plt.rcParams.update({
    "figure.facecolor": SUPERFICIE, "axes.facecolor": SUPERFICIE, "savefig.facecolor": SUPERFICIE,
    "font.family": "sans-serif", "font.size": 9.5, "text.color": TINTA,
    "axes.edgecolor": EJE, "axes.linewidth": 0.8, "axes.labelcolor": TINTA2,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": REJILLA, "grid.linewidth": 0.8,
    "xtick.color": TENUE, "ytick.color": TENUE, "xtick.labelcolor": TINTA2, "ytick.labelcolor": TINTA2,
    "legend.frameon": False,
})


# =============================================================================
#  Carga de datos
# =============================================================================
def cargar(carpeta: Path) -> dict:
    """Última ejecución de cada (fase, backend)."""
    ejecuciones = {}
    for ruta in sorted(carpeta.glob("*.json")):
        try:
            d = json.loads(ruta.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            print(f"AVISO: no se puede leer {ruta.name}: {exc}")
            continue
        if "meta" not in d or not d.get("escenarios"):
            continue
        clave = (d["meta"]["fase"], d["meta"]["backend"])
        if clave not in ejecuciones or d["meta"]["inicio"] > ejecuciones[clave]["meta"]["inicio"]:
            d["_archivo"] = ruta.name
            ejecuciones[clave] = d
    return ejecuciones


def ordenar_fases(ejecuciones: dict, pedidas: list[str] | None) -> list[str]:
    if pedidas:
        return [f for f in pedidas if any(k[0] == f for k in ejecuciones)]
    primera = {}
    for (fase, _), d in ejecuciones.items():
        primera[fase] = min(primera.get(fase, d["meta"]["inicio"]), d["meta"]["inicio"])

    def orden(f):
        n = f.lower()
        return (0, "") if n == "antes" else (2, "") if n in ("despues", "después") else (1, primera[f])
    return sorted(primera, key=orden)


def ordenar_backends(ejecuciones: dict) -> list[str]:
    backends = {b for _, b in ejecuciones}
    return sorted(backends, key=lambda b: (not b.lower().startswith("local"), b))


# =============================================================================
#  Métricas
# =============================================================================
def rp(r):
    return M.recurso_principal(r.get("recursos", {}))


# clave: (etiqueta, unidad, función, qué es mejor, decimales)
METRICAS = {
    "p50": ("Latencia p50", "s", lambda r: r["latencia_p50_s"], "menor", 1),
    "p95": ("Latencia p95", "s", lambda r: r["latencia_p95_s"], "menor", 1),
    "ttft95": ("TTFT p95", "s", lambda r: r["ttft_p95_s"], "menor", 1),
    "tok_pet": ("tok/s por petición", "", lambda r: r["tok_s_por_peticion"], "mayor", 1),
    "tok_total": ("tok/s totales", "", lambda r: r["tok_s_total"], "mayor", 1),
    "pet_min": ("Peticiones/min", "", lambda r: r["peticiones_por_min"], "mayor", 1),
    "err": ("Errores", "%", lambda r: r["tasa_error_pct"], "menor", 0),
    "cache": ("Aciertos de caché", "%", lambda r: r.get("cache_pct"), "mayor", 0),
    "espera": ("Espera en cola", "%", lambda r: r.get("espera_pct"), "menor", 0),
    # Más CPU/GPU no es ni bueno ni malo (puede ser mejor aprovechamiento): sin color
    "cpu": ("CPU media", "%", lambda r: rp(r).get("cpu_media_pct"), None, 0),
    "ram": ("RAM máx.", "GB", lambda r: rp(r).get("ram_max_gb"), "menor", 1),
    "gpu": ("GPU media", "%", lambda r: rp(r).get("gpu_media_pct"), None, 0),
}


def valor(r, clave):
    try:
        return METRICAS[clave][2](r)
    except (KeyError, TypeError):
        return None


def fmt(v, dec=1, sufijo=""):
    return "—" if v is None else f"{v:.{dec}f}{sufijo}"


def escenario(d, usuarios):
    for r in d["escenarios"]:
        if r["usuarios"] == usuarios:
            return r
    return None


# =============================================================================
#  Tablas (se pintan en Markdown y en HTML)
# =============================================================================
class Tabla:
    def __init__(self, cabecera, filas, nota=None):
        self.cabecera = cabecera
        self.filas = [[c if isinstance(c, tuple) else (str(c), "") for c in f] for f in filas]
        self.nota = nota


def celda_delta(antes, despues, clave):
    """'84.2 → 31.0 ▼63%' con clase mejor/peor según la métrica."""
    _, unidad, _, mejor, dec = METRICAS[clave]
    texto = f"{fmt(antes, dec)} → {fmt(despues, dec)}"
    if antes is None or despues is None:
        return (texto, "")
    if clave in ("err", "cache", "espera", "cpu", "gpu"):  # porcentajes: diferencia en puntos
        diff = despues - antes
        if abs(diff) < 0.5:
            return (texto + " =", "")
        texto += f" {'▲' if diff > 0 else '▼'}{abs(diff):.0f} pt"
    else:
        if antes == 0:
            return (texto, "")
        diff = (despues - antes) / antes * 100
        if abs(diff) < 1:
            return (texto + " =", "")
        texto += f" {'▲' if diff > 0 else '▼'}{abs(diff):.0f}%"
    if mejor is None:
        return (texto, "")
    bueno = (diff < 0) if mejor == "menor" else (diff > 0)
    return (texto, "mejor" if bueno else "peor")


# =============================================================================
#  Gráficas
# =============================================================================
class Graficas:
    def __init__(self, ejecuciones, fases, backends, carpeta: Path):
        self.e, self.fases, self.backends = ejecuciones, fases, backends
        self.carpeta = carpeta
        carpeta.mkdir(parents=True, exist_ok=True)
        self.usuarios = sorted({r["usuarios"] for d in ejecuciones.values() for r in d["escenarios"]})

    def color(self, fase):
        return PALETA[self.fases.index(fase) % len(PALETA)]

    def _guardar(self, fig, nombre):
        ruta = self.carpeta / f"{nombre}.png"
        fig.savefig(ruta, dpi=160, bbox_inches="tight")
        plt.close(fig)
        return ruta

    def _cabecera(self, fig, titulo, subtitulo):
        fig.text(0.01, 1.0, titulo, fontsize=12.5, fontweight="bold", color=TINTA, ha="left", va="bottom")
        if subtitulo:
            fig.text(0.01, 0.985, subtitulo, fontsize=9.5, color=TINTA2, ha="left", va="top")

    def _leyenda(self, fig, extra=None):
        if len(self.fases) < 2 and not extra:
            return
        manejadores = [Line2D([0], [0], color=self.color(f), lw=2, marker="o", ms=6, mec=SUPERFICIE, mew=1.5, label=f)
                       for f in self.fases] if len(self.fases) >= 2 else []
        manejadores += extra or []
        fig.legend(handles=manejadores, loc="upper right", bbox_to_anchor=(0.995, 1.04),
                   ncol=len(manejadores), fontsize=9, handlelength=1.8, columnspacing=1.2, labelcolor=TINTA2)

    def lineas(self, nombre, titulo, subtitulo, ylabel, clave, clave_secundaria=None, ymax=None):
        """Una gráfica por backend (mismo eje Y), una línea por fase."""
        n = len(self.backends)
        fig, ejes = plt.subplots(1, n, figsize=(4.4 * n + 0.8, 3.5), sharey=True, squeeze=False)
        hay_datos = False
        for ax, backend in zip(ejes[0], self.backends):
            for fase in self.fases:
                d = self.e.get((fase, backend))
                if not d:
                    continue
                filas = sorted(d["escenarios"], key=lambda r: r["usuarios"])
                xs = [r["usuarios"] for r in filas]
                if clave_secundaria:
                    ys2 = [valor(r, clave_secundaria) for r in filas]
                    ax.plot(xs, [float("nan") if y is None else y for y in ys2], color=self.color(fase),
                            lw=1.2, alpha=0.45, marker="o", ms=4, solid_capstyle="round")
                ys = [valor(r, clave) for r in filas]
                hay_datos |= any(y is not None for y in ys)
                ax.plot(xs, [float("nan") if y is None else y for y in ys], color=self.color(fase), lw=2,
                        marker="o", ms=7, mec=SUPERFICIE, mew=2, solid_capstyle="round", zorder=3)
            ax.set_title(backend, loc="left", fontsize=10.5, color=TINTA, fontweight="bold")
            ax.set_xticks(self.usuarios)
            ax.set_xlabel("usuarios simultáneos")
            ax.margins(x=0.08)
        # Después de dibujar TODOS los paneles, para que el eje compartido abarque todos los datos
        ejes[0][0].set_ylim(bottom=0, top=ymax)
        ejes[0][0].set_ylabel(ylabel)
        if not hay_datos:
            plt.close(fig)
            return None
        extra = None
        if clave_secundaria:
            extra = [Line2D([0], [0], color=TENUE, lw=2, label="p95"),
                     Line2D([0], [0], color=TENUE, lw=1.2, alpha=0.6, label="mediana")]
        self._cabecera(fig, titulo, subtitulo)
        self._leyenda(fig, extra)
        fig.tight_layout(rect=(0, 0, 1, 0.9))
        return self._guardar(fig, nombre)

    def barras_errores(self):
        n = len(self.backends)
        fig, ejes = plt.subplots(1, n, figsize=(4.4 * n + 0.8, 3.5), sharey=True, squeeze=False)
        k = len(self.fases)
        ancho = min(0.8 / max(k, 1), 0.3)
        hay = False
        for ax, backend in zip(ejes[0], self.backends):
            for i, fase in enumerate(self.fases):
                d = self.e.get((fase, backend))
                if not d:
                    continue
                for j, u in enumerate(self.usuarios):
                    r = escenario(d, u)
                    if r is None:
                        continue
                    v = r["tasa_error_pct"] or 0
                    hay |= v > 0
                    x = j + (i - (k - 1) / 2) * ancho
                    ax.bar(x, v, width=ancho, color=self.color(fase), edgecolor=SUPERFICIE, linewidth=1.5, zorder=3)
                    if v > 0:
                        ax.text(x, v + 1.5, f"{v:.0f}%", ha="center", va="bottom", fontsize=8, color=TINTA2)
            ax.set_xticks(range(len(self.usuarios)), [str(u) for u in self.usuarios])
            ax.set_title(backend, loc="left", fontsize=10.5, color=TINTA, fontweight="bold")
            ax.set_xlabel("usuarios simultáneos")
            ax.set_ylim(0, 105)
        ejes[0][0].set_ylabel("% de peticiones con error")
        self._cabecera(fig, "Tasa de errores", "timeouts, HTTP 5xx, conexión o respuesta vacía"
                       + ("" if hay else " — no hubo ningún error"))
        if len(self.fases) >= 2:
            fig.legend(handles=[Patch(color=self.color(f), label=f) for f in self.fases], loc="upper right",
                       bbox_to_anchor=(0.995, 1.04), ncol=len(self.fases), fontsize=9, labelcolor=TINTA2,
                       handlelength=1.2)
        fig.tight_layout(rect=(0, 0, 1, 0.9))
        return self._guardar(fig, "errores")

    def ejecucion(self, fase, backend):
        """Latencia de cada petición y CPU/RAM a lo largo del tiempo para una ejecución."""
        d = self.e[(fase, backend)]
        color = self.color(fase)
        total = M.resumir_recursos(d["recursos"], float("-inf"), float("inf"))
        principal = M.recurso_principal(total)
        fuente = principal.get("fuente")
        muestras = [m for m in d["recursos"] if m["fuente"] == fuente]
        gpu = [m for m in d["recursos"] if m.get("gpu_pct") is not None]

        fig, (a1, a2, a3) = plt.subplots(3, 1, figsize=(9.5, 6.6), sharex=True,
                                         gridspec_kw={"height_ratios": [1.4, 1, 1]})
        for i, r in enumerate(sorted(d["escenarios"], key=lambda x: x["ventana"][0])):
            v0, v1 = r["ventana"]
            for ax in (a1, a2, a3):
                ax.axvspan(v0, v1, color=BANDA, zorder=0, lw=0)
            a1.text((v0 + v1) / 2, 1.02, f"{r['usuarios']} usuarios", transform=a1.get_xaxis_transform(),
                    ha="center", va="bottom", fontsize=8.5, color=TINTA2)

        ok = [p for p in d["peticiones"] if p["estado"] == "ok"]
        err = [p for p in d["peticiones"] if p["estado"] != "ok"]
        a1.scatter([p["t_inicio"] for p in ok], [p["latencia"] for p in ok], s=26, color=color,
                   edgecolors=SUPERFICIE, linewidths=1, zorder=3, label="completada")
        if err:
            a1.scatter([p["t_inicio"] for p in err], [p["latencia"] for p in err], s=30, marker="x",
                       color=CRITICO, linewidths=1.6, zorder=3, label="error")
        a1.set_ylabel("latencia (s)")
        a1.set_ylim(bottom=0)
        leyenda = [Line2D([0], [0], lw=0, marker="o", ms=6, color=color, mec=SUPERFICIE, label="petición completada")]
        if err:
            leyenda.append(Line2D([0], [0], lw=0, marker="x", ms=6, mew=1.6, color=CRITICO, label="error"))

        if muestras:
            a2.plot([m["t"] for m in muestras], [m.get("cpu_pct") for m in muestras], color=color, lw=2)
            leyenda.append(Line2D([0], [0], color=color, lw=2, label="CPU / RAM"))
        if gpu:
            a2.plot([m["t"] for m in gpu], [m["gpu_pct"] for m in gpu], color=TINTA2, lw=1.5)
            leyenda.append(Line2D([0], [0], color=TINTA2, lw=1.5, label="GPU"))
        fig.legend(handles=leyenda, loc="upper right", bbox_to_anchor=(0.995, 1.0), ncol=len(leyenda),
                   fontsize=8.5, labelcolor=TINTA2)
        a2.set_ylabel("uso (%)")
        a2.set_ylim(0, 105)

        if muestras:
            a3.plot([m["t"] for m in muestras], [m.get("ram_gb") for m in muestras], color=color, lw=2)
            limite = max((m.get("ram_total_gb") or 0) for m in muestras)
            if limite:
                a3.axhline(limite, color=TENUE, lw=1)
                a3.text(a3.get_xlim()[0], limite, f" RAM disponible {limite:.1f} GB", va="bottom",
                        ha="left", fontsize=8, color=TINTA2)
                a3.set_ylim(0, limite * 1.12)
        a3.set_ylabel("RAM (GB)")
        a3.set_xlabel("tiempo desde el inicio de la prueba (s)")

        origen = f"medido en: {fuente}" if fuente else "sin datos de recursos"
        self._cabecera(fig, f"{fase} · {backend}: cada petición y uso de recursos", origen)
        fig.tight_layout(rect=(0, 0, 1, 0.93))
        return self._guardar(fig, f"ejecucion_{nombre_archivo(fase)}_{nombre_archivo(backend)}")


def nombre_archivo(texto):
    return re.sub(r"[^A-Za-z0-9_-]+", "-", texto).strip("-")


# =============================================================================
#  Análisis: cuellos de botella
# =============================================================================
def motivos_fallo(r) -> list[str]:
    motivos = []
    if r["ok"] == 0:
        motivos.append("ninguna petición terminó")
    if (r["tasa_error_pct"] or 0) > UMBRAL_ERRORES:
        tipos = ", ".join(f"{t} ×{n}" for t, n in r["errores_por_tipo"].items())
        motivos.append(f"{r['tasa_error_pct']:.0f}% de errores ({tipos})")
    if r["ttft_p95_s"] is not None and r["ttft_p95_s"] > UMBRAL_TTFT_P95:
        motivos.append(f"TTFT p95 de {r['ttft_p95_s']:.1f} s (> {UMBRAL_TTFT_P95:.0f} s)")
    return motivos


def causas(r) -> list[str]:
    c = []
    tipos = r["errores_por_tipo"]
    rec = rp(r)
    if any(t.startswith("http_503") for t in tipos):
        c.append("Ollama rechaza peticiones con HTTP 503: la cola está llena (OLLAMA_MAX_QUEUE).")
    if tipos.get("http_502"):
        c.append("La API no consigue hablar con Ollama (HTTP 502): backend caído, reiniciándose o BACKEND_URL incorrecta.")
    if tipos.get("respuesta_vacia"):
        c.append("Hay respuestas sin texto: el límite de tokens se agota razonando (subir num_predict o think=false).")
    if tipos.get("conexion") or tipos.get("red"):
        c.append("Hay errores de red o conexión: revisa conectividad, firewall o reglas del NSG.")
    if r.get("espera_pct") is not None and r["espera_pct"] >= UMBRAL_COLA:
        c.append(f"El {r['espera_pct']:.0f}% del tiempo de cada petición es espera en cola: llegan más "
                 f"peticiones de las que Ollama atiende a la vez (OLLAMA_NUM_PARALLEL).")
    if rec.get("cpu_media_pct") is not None and rec["cpu_media_pct"] >= UMBRAL_CPU:
        c.append(f"CPU al {rec['cpu_media_pct']:.0f}% de media: el cálculo del modelo está saturado.")
    if rec.get("gpu_media_pct") is not None and rec["gpu_media_pct"] >= UMBRAL_GPU:
        c.append(f"GPU al {rec['gpu_media_pct']:.0f}% de media: la GPU está saturada.")
    if rec.get("ram_max_gb") and rec.get("ram_total_gb") and rec["ram_max_gb"] / rec["ram_total_gb"] >= UMBRAL_RAM:
        c.append(f"RAM al {100 * rec['ram_max_gb'] / rec['ram_total_gb']:.0f}% "
                 f"({rec['ram_max_gb']:.1f} de {rec['ram_total_gb']:.1f} GB).")
    if tipos.get("timeout") and not c:
        c.append("Las peticiones superan el timeout, pero no se ve un recurso saturado: "
                 "revisa la latencia de red y el tiempo de carga del modelo.")
    if not c:
        c.append("No se detecta ningún recurso saturado en este escenario.")
    return c


def analizar(d) -> dict:
    esc = sorted(d["escenarios"], key=lambda r: r["usuarios"])
    res = {"fallo": None, "motivos": [], "saturacion": None, "notas": []}
    for r in esc:
        motivos = motivos_fallo(r)
        if motivos:
            res["fallo"], res["motivos"] = r, motivos
            break
    res["referencia"] = res["fallo"] or esc[-1]
    res["causas"] = causas(res["referencia"])
    for a, b in zip(esc, esc[1:]):
        if a["tok_s_total"] and b["tok_s_total"] is not None and b["tok_s_total"] < a["tok_s_total"] * UMBRAL_ESCALADO:
            res["saturacion"] = (a, b)
            break
    razon = max((r.get("razonamiento_pct") or 0) for r in esc)
    if razon >= 20:
        res["notas"].append(f"El {razon:.0f}% del texto generado es razonamiento interno (thinking): "
                            "probar MODEL_THINK=false.")
    trunc = max((r.get("truncadas_pct") or 0) for r in esc)
    if trunc >= 30:
        res["notas"].append(f"Hasta el {trunc:.0f}% de las respuestas se cortan por el límite de tokens "
                            "(num_predict): más rápido, pero revisa que sigan siendo útiles.")
    return res


def frase_veredicto(backend, fase, a) -> str:
    if a["fallo"]:
        r = a["fallo"]
        texto = f"**{backend}** ({fase}) falla primero con **{r['usuarios']} usuarios**: {'; '.join(a['motivos'])}."
    else:
        u = a["referencia"]["usuarios"]
        texto = (f"**{backend}** ({fase}) aguanta hasta **{u} usuarios** dentro de los umbrales "
                 f"(TTFT p95 ≤ {UMBRAL_TTFT_P95:.0f} s y errores ≤ {UMBRAL_ERRORES:.0f}%).")
    return texto


# =============================================================================
#  Configuración de cada ejecución
# =============================================================================
def configuracion(d) -> dict:
    meta = d["meta"]
    info = meta.get("backend_info") or {}
    cache = info.get("cache") or {}
    parametros = info.get("parametros") or {}
    opciones = {**(parametros.get("options") or {}), **(meta["config"].get("opciones") or {})}
    think = meta["config"].get("think")
    if think is None:
        think = parametros.get("think")
    servidor = {}
    hardware = []
    for fuente, h in (meta.get("hardware") or {}).items():
        servidor.update(h.get("config_ollama") or {})
        partes = []
        if h.get("cpus"):
            partes.append(f"{h['cpus']} CPU")
        if h.get("ram_total_gb"):
            partes.append(f"{h['ram_total_gb']:.0f} GB RAM")
        if h.get("gpus"):
            partes.append(", ".join(h["gpus"]))
        if partes:
            hardware.append(f"{fuente}: {' · '.join(partes)}")
    servidor.pop("MODEL_NAME", None)
    return {
        "Ollama": info.get("backend_url") or meta.get("url"),
        "Modelo": meta.get("modelo"),
        "Cuantización": (info.get("backend") or {}).get("cuantizacion") or "—",
        "Caché en la API": ("sí" if cache.get("activa") else "no") if cache else "—",
        "Opciones del modelo": ", ".join(f"{k}={v}" for k, v in opciones.items()) or "por defecto",
        "Razonamiento (think)": "por defecto" if think is None else str(think).lower(),
        "Servidor Ollama": ", ".join(f"{k}={v}" for k, v in sorted(servidor.items())) or "valores por defecto / no medido",
        "Hardware medido": "; ".join(hardware) or "—",
    }


# =============================================================================
#  Construcción del informe
# =============================================================================
class Informe:
    def __init__(self):
        self.bloques = []

    def h(self, nivel, texto):
        self.bloques.append(("h", nivel, texto))

    def p(self, texto):
        self.bloques.append(("p", texto))

    def lista(self, items):
        if items:
            self.bloques.append(("ul", items))

    def tabla(self, t: Tabla):
        self.bloques.append(("tabla", t))

    def imagen(self, ruta: Path | None, alt: str):
        if ruta:
            self.bloques.append(("img", ruta, alt))

    def aviso(self, texto):
        self.bloques.append(("aviso", texto))

    # --- Markdown --------------------------------------------------------------
    def markdown(self, carpeta: Path) -> str:
        salida = []
        for b in self.bloques:
            if b[0] == "h":
                salida.append(f"{'#' * b[1]} {b[2]}\n")
            elif b[0] == "p":
                salida.append(b[1] + "\n")
            elif b[0] == "aviso":
                salida.append(f"> ⚠️ {b[1]}\n")
            elif b[0] == "ul":
                salida.append("\n".join(f"- {i}" for i in b[1]) + "\n")
            elif b[0] == "img":
                salida.append(f"![{b[2]}]({b[1].relative_to(carpeta).as_posix()})\n")
            elif b[0] == "tabla":
                t = b[1]

                def numerica(i):
                    return all(re.match(r"^[\d—.]", f[i][0]) for f in t.filas) if t.filas else False
                salida.append("| " + " | ".join(t.cabecera) + " |")
                salida.append("|" + "|".join("---:" if numerica(i) else "---" for i in range(len(t.cabecera))) + "|")
                for f in t.filas:
                    salida.append("| " + " | ".join(c[0].replace("|", "\\|") for c in f) + " |")
                salida.append(f"\n_{t.nota}_\n" if t.nota else "")
        return "\n".join(salida)

    # --- HTML ------------------------------------------------------------------
    @staticmethod
    def _en_linea(texto):
        t = html.escape(texto)
        t = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)
        return re.sub(r"`(.+?)`", r"<code>\1</code>", t)

    def html(self, titulo) -> str:
        partes = []
        for b in self.bloques:
            if b[0] == "h":
                partes.append(f"<h{b[1]}>{self._en_linea(b[2])}</h{b[1]}>")
            elif b[0] == "p":
                partes.append(f"<p>{self._en_linea(b[1])}</p>")
            elif b[0] == "aviso":
                partes.append(f'<div class="aviso"><strong>⚠</strong> {self._en_linea(b[1])}</div>')
            elif b[0] == "ul":
                partes.append("<ul>" + "".join(f"<li>{self._en_linea(i)}</li>" for i in b[1]) + "</ul>")
            elif b[0] == "img":
                datos = base64.b64encode(b[1].read_bytes()).decode()
                partes.append(f'<figure><img src="data:image/png;base64,{datos}" alt="{html.escape(b[2])}"></figure>')
            elif b[0] == "tabla":
                t = b[1]
                izq = [not (t.filas and all(re.match(r"^[\d—.]", f[i][0]) for f in t.filas))
                       for i in range(len(t.cabecera))]
                filas = "".join(
                    "<tr>" + "".join(f'<td class="{c[1]}{" izq" if izq[i] else ""}">{html.escape(c[0])}</td>'
                                     for i, c in enumerate(f)) + "</tr>"
                    for f in t.filas
                )
                cab = "".join(f'<th class="{"izq" if izq[i] else ""}">{html.escape(c)}</th>'
                              for i, c in enumerate(t.cabecera))
                nota = f'<p class="nota">{self._en_linea(t.nota)}</p>' if t.nota else ""
                partes.append(f'<div class="tabla"><table><thead><tr>{cab}</tr></thead><tbody>{filas}</tbody></table></div>{nota}')
        return PLANTILLA_HTML.replace("{{titulo}}", html.escape(titulo)).replace("{{cuerpo}}", "\n".join(partes))


PLANTILLA_HTML = """<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{titulo}}</title>
<style>
  :root { color-scheme: light; --sup:#fcfcfb; --pagina:#f9f9f7; --tinta:#0b0b0b; --tinta2:#52514e; --tenue:#898781;
          --linea:#e1e0d9; --bueno:#006300; --malo:#d03b3b; --aviso:#fff4d6; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--pagina); color:var(--tinta); font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif; }
  main { max-width:1080px; margin:0 auto; padding:32px 16px 64px; }
  h1 { font-size:28px; margin:0 0 4px; } h2 { font-size:21px; margin:40px 0 10px; padding-top:8px; border-top:1px solid var(--linea); }
  h3 { font-size:16px; margin:24px 0 8px; } p, li { color:var(--tinta2); } strong { color:var(--tinta); }
  code { background:#efeee9; padding:1px 5px; border-radius:4px; font-size:13px; }
  .aviso { background:var(--aviso); border:1px solid #f0d58a; border-radius:8px; padding:12px 14px; margin:16px 0; }
  .tabla { overflow-x:auto; margin:10px 0; background:var(--sup); border:1px solid var(--linea); border-radius:8px; }
  table { border-collapse:collapse; width:100%; font-size:13.5px; font-variant-numeric:tabular-nums; }
  th, td { padding:7px 10px; border-bottom:1px solid var(--linea); text-align:right; white-space:nowrap; }
  th { color:var(--tinta2); font-weight:600; background:#f4f3ef; }
  th.izq, td.izq { text-align:left; }
  tr:last-child td { border-bottom:0; }
  td.mejor { color:var(--bueno); font-weight:600; } td.peor { color:var(--malo); font-weight:600; }
  .nota { font-size:13px; color:var(--tenue); margin-top:4px; }
  figure { margin:14px 0 22px; background:var(--sup); border:1px solid var(--linea); border-radius:8px; padding:10px; }
  figure img { width:100%; height:auto; display:block; }
  @media print { body { background:#fff; } h2 { break-before:auto; } figure, .tabla { break-inside:avoid; } }
</style></head>
<body><main>
{{cuerpo}}
</main></body></html>
"""


def tabla_comparativa(ejecuciones, fase, backends, usuarios) -> Tabla:
    claves = ["p50", "p95", "ttft95", "tok_pet", "tok_total", "err", "cpu", "ram"]
    cab = ["Usuarios", "Backend", "Completadas"] + [
        f"{METRICAS[k][0]} ({METRICAS[k][1]})" if METRICAS[k][1] else METRICAS[k][0] for k in claves]
    filas = []
    for u in usuarios:
        mejores = {}
        datos_fila = []
        for b in backends:
            d = ejecuciones.get((fase, b))
            r = escenario(d, u) if d else None
            if r:
                datos_fila.append((b, r))
        if len(datos_fila) > 1:  # marcar el mejor de cada columna
            for k in claves:
                vals = [(valor(r, k), b) for b, r in datos_fila if valor(r, k) is not None]
                if len(vals) > 1 and len({round(v, 3) for v, _ in vals}) > 1 and k not in ("cpu", "ram"):
                    elegido = min(vals) if METRICAS[k][3] == "menor" else max(vals)
                    mejores[k] = elegido[1]
        for b, r in datos_fila:
            fila = [str(u), b, f"{r['ok']}/{r['peticiones']}"]
            for k in claves:
                fila.append((fmt(valor(r, k), METRICAS[k][4]), "mejor" if mejores.get(k) == b else ""))
            filas.append(fila)
    return Tabla(cab, filas, "En verde, el mejor backend en cada escenario. Latencias y tokens/s: solo de las "
                             "peticiones completadas (mira también la columna de errores). CPU y RAM: del "
                             "contenedor de Ollama si se midió; si no, de la máquina completa.")


def comparar_backends(u, a, b) -> str:
    """Frase local vs remoto. Primero cuenta cuántas peticiones terminan: comparar solo la latencia
    de las que sobreviven engaña (si casi todas fallan, las pocas que acaban parecen rápidas)."""
    (na, ra), (nb, rb) = a, b
    exito_a, exito_b = 100 - (ra["tasa_error_pct"] or 0), 100 - (rb["tasa_error_pct"] or 0)
    if abs(exito_a - exito_b) > UMBRAL_ERRORES:
        (nm, rm, em), (np_, rpe, ep) = ((na, ra, exito_a), (nb, rb, exito_b)) if exito_a > exito_b else \
            ((nb, rb, exito_b), (na, ra, exito_a))
        texto = (f"Con **{u} usuarios**, **{nm}** completa el {em:.0f}% de las peticiones y {np_} solo el {ep:.0f}%")
        if rm["tok_s_total"] and rpe["tok_s_total"]:
            texto += f"; {nm} genera {rm['tok_s_total'] / rpe['tok_s_total']:.1f}× los tokens/s de {np_}"
        return texto + "."
    if not ra["latencia_p95_s"] or not rb["latencia_p95_s"]:
        return f"Con **{u} usuarios** no hay latencias para comparar."
    (nr, rr), (nl, rl) = (a, b) if ra["latencia_p95_s"] <= rb["latencia_p95_s"] else (b, a)
    factor = rl["latencia_p95_s"] / rr["latencia_p95_s"]
    if factor < 1.1:
        texto = (f"Con **{u} usuarios** los dos rinden parecido (p95 {rr['latencia_p95_s']:.1f} s y "
                 f"{rl['latencia_p95_s']:.1f} s)")
    else:
        texto = (f"Con **{u} usuarios**, **{nr}** tiene una latencia p95 {factor:.1f}× menor que {nl} "
                 f"({rr['latencia_p95_s']:.1f} s frente a {rl['latencia_p95_s']:.1f} s)")
    if rr["tok_s_total"] and rl["tok_s_total"]:
        ratio = rr["tok_s_total"] / rl["tok_s_total"]
        texto += (f" y genera {ratio:.1f}× más tokens/s" if ratio >= 1.1 else
                  f", aunque genera menos tokens/s en total ({rr['tok_s_total']:.0f} frente a {rl['tok_s_total']:.0f})"
                  if ratio <= 0.9 else "")
    return texto + "."


def tabla_antes_despues(ejecuciones, base, fase, backend, usuarios) -> Tabla | None:
    a, d = ejecuciones.get((base, backend)), ejecuciones.get((fase, backend))
    if not a or not d:
        return None
    claves = ["p50", "p95", "ttft95", "tok_total", "err", "cache", "cpu", "ram"]
    cab = ["Usuarios"] + [f"{METRICAS[k][0]} ({METRICAS[k][1]})" if METRICAS[k][1] else METRICAS[k][0] for k in claves]
    filas = []
    for u in usuarios:
        ra, rd = escenario(a, u), escenario(d, u)
        if ra and rd:
            filas.append([str(u)] + [celda_delta(valor(ra, k), valor(rd, k), k) for k in claves])
    return Tabla(cab, filas, f"{base} → {fase}. ▲/▼ = sube/baja; en verde si mejora, en rojo si empeora. "
                             "Los porcentajes comparan en puntos (pt).")


def tabla_desglose(ejecuciones, fases, backends) -> Tabla:
    cab = ["Fase", "Backend", "Usuarios", "Espera (s)", "Prompt (s)", "Generación (s)", "Tokens resp.",
           "Cortadas (%)", "Razonam. (%)", "Repetidas (%)", "Caché (%)"]
    filas = []
    for f in fases:
        for b in backends:
            d = ejecuciones.get((f, b))
            if not d:
                continue
            for r in sorted(d["escenarios"], key=lambda x: x["usuarios"]):
                filas.append([f, b, str(r["usuarios"]), fmt(r["espera_media_s"]), fmt(r["prefill_media_s"], 2),
                              fmt(r["generacion_media_s"]), fmt(r["tokens_salida_media"], 0),
                              fmt(r["truncadas_pct"], 0), fmt(r["razonamiento_pct"], 0),
                              fmt(r["repetidos_pct"], 0), fmt(r["cache_pct"], 0)])
    return Tabla(cab, filas, "Espera = latencia − tiempo de prompt − tiempo de generación (cola, carga del modelo y red). "
                             "Medias de las peticiones que pasaron por el modelo.")


def resumen_csv(ejecuciones, ruta: Path):
    campos = ["fase", "backend", "usuarios", "peticiones", "ok", "errores", "tasa_error_pct", "latencia_media_s",
              "latencia_p50_s", "latencia_p95_s", "latencia_max_s", "ttft_p50_s", "ttft_p95_s", "tok_s_por_peticion",
              "tok_s_total", "peticiones_por_min", "tokens_salida_media", "cache_pct", "repetidos_pct",
              "espera_media_s", "prefill_media_s", "generacion_media_s", "espera_pct", "truncadas_pct",
              "razonamiento_pct", "fuente_recursos", "cpu_media_pct", "cpu_max_pct", "ram_media_gb", "ram_max_gb",
              "ram_total_gb", "gpu_media_pct", "gpu_max_pct"]
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos, extrasaction="ignore")
        w.writeheader()
        for (fase, backend), d in ejecuciones.items():
            for r in d["escenarios"]:
                principal = rp(r)
                w.writerow({**r, "fase": fase, "backend": backend, "fuente_recursos": principal.get("fuente"),
                            **{k: v for k, v in principal.items() if k != "fuente"}})


def conclusiones_md(informe: Informe, ruta: Path):
    """Añade conclusiones.md (escrito por vosotros) con un intérprete Markdown mínimo."""
    parrafo = []
    lista = []

    def volcar():
        if parrafo:
            informe.p(" ".join(parrafo))
            parrafo.clear()
        if lista:
            informe.lista(list(lista))
            lista.clear()

    for linea in ruta.read_text(encoding="utf-8").splitlines():
        s = linea.strip()
        if not s:
            volcar()
        elif s.startswith("#"):
            volcar()
            nivel = len(s) - len(s.lstrip("#"))
            informe.h(min(nivel + 2, 4), s.lstrip("#").strip())
        elif s.startswith(("- ", "* ")):
            if parrafo:
                volcar()
            lista.append(s[2:])
        else:
            if lista:
                volcar()
            parrafo.append(s)
    volcar()


def main():
    ap = argparse.ArgumentParser(description="Genera el informe comparativo de las pruebas de carga")
    ap.add_argument("--resultados", default=str(CARPETA / "resultados"))
    ap.add_argument("--salida", default=str(CARPETA / "informe"))
    ap.add_argument("--fases", help="fases a incluir, en orden (p. ej. antes,despues)")
    ap.add_argument("--base", help="fase de referencia para comparar (por defecto, la primera)")
    ap.add_argument("--titulo", default="Informe de pruebas de carga · Chat con Gemma 4")
    args = ap.parse_args()

    ejecuciones = cargar(Path(args.resultados))
    if not ejecuciones:
        raise SystemExit(f"No hay resultados en {args.resultados}. Ejecuta antes carga.py.")
    fases = ordenar_fases(ejecuciones, args.fases.split(",") if args.fases else None)
    ejecuciones = {k: v for k, v in ejecuciones.items() if k[0] in fases}
    backends = ordenar_backends(ejecuciones)
    base = args.base or fases[0]
    usuarios = sorted({r["usuarios"] for d in ejecuciones.values() for r in d["escenarios"]})

    salida = Path(args.salida)
    graficas = Graficas(ejecuciones, fases, backends, salida / "graficas")
    inf = Informe()

    # --- Portada ---------------------------------------------------------------
    inf.h(1, args.titulo)
    inf.p(f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')} · fases: {', '.join(fases)} · "
          f"backends: {', '.join(backends)} · escenarios: {', '.join(str(u) for u in usuarios)} usuarios simultáneos")
    if any(d["meta"].get("simulado") for d in ejecuciones.values()):
        inf.aviso("**DATOS SIMULADOS.** Al menos una ejecución se hizo contra el Ollama simulado "
                  "(simulador/ollama_simulado.py). Sirve para ver cómo queda el informe, no para entregarlo.")
    incompletas = [f"{f} · {b}" for (f, b), d in ejecuciones.items() if not d["meta"].get("completo")]
    if incompletas:
        inf.aviso(f"Ejecuciones interrumpidas (faltan escenarios): {', '.join(incompletas)}.")
    faltan = [f"{f} · {b}" for f in fases for b in backends if (f, b) not in ejecuciones]
    if faltan:
        inf.aviso(f"Faltan ejecuciones para comparar: {', '.join(faltan)}.")

    # --- 1. Configuración -------------------------------------------------------
    inf.h(2, "1. Cómo se ha probado")
    cfg = next(iter(ejecuciones.values()))["meta"]["config"]
    inf.lista([
        f"**Escenarios:** {', '.join(str(u) for u in cfg['usuarios'])} usuarios a la vez; cada uno hace "
        f"{cfg['peticiones_por_usuario']} preguntas seguidas con hasta {cfg['pensar_max_s']:g} s de pausa entre ellas.",
        f"**Timeout:** {cfg['timeout_s']:.0f} s por petición (si se supera, cuenta como error).",
        f"**Preguntas:** {cfg['n_prompts']} distintas (prompts.txt), elegidas con semilla fija {cfg['semilla']} "
        f"para que todas las fases y backends reciban exactamente la misma carga"
        + (f"; las más típicas se repiten más (zipf={cfg['zipf']})." if cfg.get("zipf") else "."),
        "**Script:** `carga.py` (asyncio + aiohttp) con streaming, midiendo el primer token y las métricas que "
        "devuelve Ollama (`eval_count`, `eval_duration`...). CPU/RAM cada pocos segundos en segundo plano.",
    ])
    claves_cfg = list(configuracion(next(iter(ejecuciones.values()))).keys())
    filas = []
    for f in fases:
        for b in backends:
            d = ejecuciones.get((f, b))
            if d:
                c = configuracion(d)
                filas.append([f, b] + [c[k] for k in claves_cfg] + [d["meta"]["inicio"].replace("T", " ")])
    inf.tabla(Tabla(["Fase", "Backend"] + claves_cfg + ["Fecha"], filas))

    # --- 2. Local vs remoto -----------------------------------------------------
    inf.h(2, "2. Comparativa local vs remoto")
    if len(backends) < 2:
        inf.p("Solo hay un backend con resultados; ejecuta carga.py también contra el otro para compararlos.")
    for f in fases:
        inf.h(3, f"Fase «{f}»")
        inf.tabla(tabla_comparativa(ejecuciones, f, backends, usuarios))
        if len(backends) >= 2:
            notas = []
            for u in usuarios:
                filas_u = [(b, escenario(ejecuciones[(f, b)], u)) for b in backends[:2] if (f, b) in ejecuciones]
                filas_u = [(b, r) for b, r in filas_u if r]
                if len(filas_u) == 2:
                    notas.append(comparar_backends(u, *filas_u))
            inf.lista(notas)

    # --- 3. Gráficas --------------------------------------------------------------
    inf.h(2, "3. Gráficas de rendimiento")
    inf.p("Cada panel es un backend (mismo eje vertical para poder compararlos) y cada color, una fase.")
    inf.imagen(graficas.lineas("latencia", "Latencia por petición",
                               "tiempo hasta tener la respuesta completa (solo peticiones completadas)",
                               "segundos", "p95", "p50"), "Latencia p95 y mediana por usuarios")
    inf.imagen(graficas.lineas("ttft", "Tiempo hasta el primer token (p95)",
                               "lo que espera el usuario hasta ver la primera palabra", "segundos", "ttft95"),
               "TTFT p95 por usuarios")
    inf.imagen(graficas.lineas("tokens_totales", "Tokens por segundo generados en total",
                               "tokens de respuestas completadas por segundo: si deja de subir al añadir usuarios, está saturado",
                               "tokens/s", "tok_total"), "Tokens por segundo totales")
    inf.imagen(graficas.lineas("tokens_peticion", "Velocidad que ve cada usuario",
                               "tokens/s de cada respuesta (baja al repartirse el cálculo entre más peticiones)",
                               "tokens/s", "tok_pet"), "Tokens por segundo por petición")
    inf.imagen(graficas.barras_errores(), "Tasa de errores")
    inf.imagen(graficas.lineas("espera", "Tiempo en cola", "% de la latencia que la petición pasa esperando turno",
                               "% de la latencia", "espera", ymax=105), "Porcentaje de espera en cola")
    inf.imagen(graficas.lineas("cpu", "Uso de CPU (media)", "% del total de la máquina o del contenedor",
                               "% CPU", "cpu", ymax=105), "Uso de CPU")
    inf.imagen(graficas.lineas("ram", "Memoria RAM (máximo)", "pico de RAM durante cada escenario",
                               "GB", "ram"), "Uso de RAM")
    if any(valor(r, "gpu") is not None for d in ejecuciones.values() for r in d["escenarios"]):
        inf.imagen(graficas.lineas("gpu", "Uso de GPU (media)", "", "% GPU", "gpu", ymax=105), "Uso de GPU")

    # --- 4. Cuellos de botella ----------------------------------------------------
    inf.h(2, "4. Cuellos de botella")
    inf.p(f"Criterio de «fallo»: TTFT p95 > {UMBRAL_TTFT_P95:.0f} s o más de un {UMBRAL_ERRORES:.0f}% de errores. "
          f"Se analiza la fase «{base}».")
    for b in backends:
        d = ejecuciones.get((base, b))
        if not d:
            continue
        a = analizar(d)
        inf.h(3, f"¿Dónde falla primero {b}?")
        inf.p(frase_veredicto(b, base, a))
        items = [f"Causa probable: {c}" for c in a["causas"]]
        if a["saturacion"]:
            x, y = a["saturacion"]
            items.append(f"La capacidad se estanca: con {x['usuarios']} usuarios genera {x['tok_s_total']:.1f} tok/s "
                         f"y con {y['usuarios']}, {y['tok_s_total']:.1f} tok/s. Más usuarios solo alargan la cola.")
        items += a["notas"]
        inf.lista(items)

    # --- 5. Antes vs después ----------------------------------------------------
    otras = [f for f in fases if f != base]
    inf.h(2, "5. Optimizaciones: antes vs después")
    if not otras:
        inf.p("Solo hay una fase. Aplica las optimizaciones (carpeta optimizaciones/) y vuelve a ejecutar "
              "carga.py con otra --fase para completar esta sección.")
    for f in otras:
        for b in backends:
            if (base, b) not in ejecuciones or (f, b) not in ejecuciones:
                continue
            inf.h(3, f"{b}: «{base}» → «{f}»")
            ca, cd = configuracion(ejecuciones[(base, b)]), configuracion(ejecuciones[(f, b)])
            cambios = [f"**{k}:** {ca[k]} → {cd[k]}" for k in ca
                       if ca[k] != cd[k] and k not in ("Hardware medido", "Ollama")]
            inf.p("Qué cambia entre las dos ejecuciones:" if cambios else
                  "No se detectan cambios de configuración entre las dos ejecuciones (¿se aplicaron las optimizaciones?).")
            inf.lista(cambios)
            t = tabla_antes_despues(ejecuciones, base, f, b, usuarios)
            if t:
                inf.tabla(t)
            ad = analizar(ejecuciones[(f, b)])
            inf.p("Tras el cambio: " + frase_veredicto(b, f, ad))

    # --- 6. Recursos durante cada ejecución ------------------------------------
    inf.h(2, "6. Evolución durante cada prueba")
    inf.p("Arriba, cada punto es una petición (cuándo empezó y cuánto tardó; las cruces son errores). "
          "Debajo, CPU y RAM del backend en ese momento. Las bandas grises marcan cada escenario.")
    for f in fases:
        for b in backends:
            if (f, b) in ejecuciones:
                inf.imagen(graficas.ejecucion(f, b), f"Evolución de {f} en {b}")

    # --- 7. Desglose ------------------------------------------------------------
    inf.h(2, "7. Desglose por escenario")
    inf.tabla(tabla_desglose(ejecuciones, fases, backends))

    # --- 8. Conclusiones ----------------------------------------------------------
    inf.h(2, "8. Conclusiones")
    ruta_conclusiones = CARPETA / "conclusiones.md"
    if ruta_conclusiones.exists():
        conclusiones_md(inf, ruta_conclusiones)
    else:
        inf.p("Escribe vuestras conclusiones en `pruebas-carga/conclusiones.md` y vuelve a ejecutar informe.py: "
              "se insertarán aquí.")

    # --- Anexo --------------------------------------------------------------------
    inf.h(2, "Anexo: qué significa cada métrica")
    inf.lista([
        "**Latencia p50 / p95:** tiempo total de la petición. p50 = la mitad tarda menos; p95 = el 95% tarda menos "
        "(lo que sufren los usuarios con peor suerte).",
        "**TTFT:** tiempo hasta el primer token. Con streaming es lo que el usuario percibe como «tarda en contestar».",
        "**tok/s por petición:** velocidad de generación de cada respuesta (eval_count / eval_duration de Ollama).",
        "**tok/s totales:** tokens de todas las respuestas completadas del escenario dividido por su duración. "
        "Es la capacidad útil del backend (lo generado para peticiones que acabaron en timeout no cuenta).",
        "**Espera en cola:** parte de la latencia que no es ni procesar el prompt ni generar: esperar turno, "
        "cargar el modelo y red.",
        "**Errores:** timeout (no terminó a tiempo), http_5xx (Ollama/API rechazó), conexion/red, "
        "respuesta_vacia (no devolvió texto).",
        "**Caché:** % de respuestas servidas por la caché de la API (hit) o compartidas con una petición idéntica "
        "simultánea (agrupada).",
    ])
    inf.p("Archivos de resultados usados: " + ", ".join(f"`{d['_archivo']}`" for d in ejecuciones.values()))

    # --- Escribir ---------------------------------------------------------------
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "informe.md").write_text(inf.markdown(salida), encoding="utf-8")
    (salida / "informe.html").write_text(inf.html(args.titulo), encoding="utf-8")
    resumen_csv(ejecuciones, salida / "resumen.csv")
    print(f"Informe generado en {salida}/")
    print("  informe.html  (ábrelo en el navegador; Ctrl+P para PDF)")
    print("  informe.md    (para el repositorio)")
    print(f"  graficas/     ({len(list((salida / 'graficas').glob('*.png')))} imágenes)")
    print("  resumen.csv")


if __name__ == "__main__":
    main()
