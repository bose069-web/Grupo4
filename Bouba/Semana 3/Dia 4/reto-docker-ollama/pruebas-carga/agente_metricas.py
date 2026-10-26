#!/usr/bin/env python3
"""
Agente de métricas para la MÁQUINA REMOTA (VM de Azure, PC de un compañero...).

Sirve por HTTP el uso de CPU, RAM y GPU de esa máquina para que el script de
carga (carga.py --recursos http://IP:9101) lo registre durante la prueba.

Uso en la máquina remota:
    python3 agente_metricas.py                       # puerto 9101
    python3 agente_metricas.py --docker ollama-remoto  # + CPU/RAM de ese servicio de compose

Requisitos: Python 3.8+. En Linux no necesita nada más. En Windows/Mac: pip install psutil
Seguridad: expone datos del sistema. Abre el puerto solo a tu IP (NSG en Azure,
firewall en Windows) o usa un túnel SSH:  ssh -N -L 9101:localhost:9101 usuario@IP
"""

from __future__ import annotations

import argparse
import json
import platform
import shutil
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

GB = 1024 ** 3

try:
    import psutil
except ImportError:
    psutil = None


# --- CPU y RAM del sistema ---------------------------------------------------
class Cpu:
    """% de CPU de todo el sistema desde la última lectura."""

    def __init__(self):
        self._lock = threading.Lock()
        self._anterior = self._tiempos()

    @staticmethod
    def _tiempos():
        if psutil:
            return None
        with open("/proc/stat") as f:
            valores = [int(x) for x in f.readline().split()[1:]]
        inactivo = valores[3] + (valores[4] if len(valores) > 4 else 0)  # idle + iowait
        return sum(valores), inactivo

    def porcentaje(self) -> float:
        if psutil:
            return psutil.cpu_percent(None)
        with self._lock:
            total, inactivo = self._tiempos()
            total0, inactivo0 = self._anterior
            self._anterior = (total, inactivo)
        dt = total - total0
        return 0.0 if dt <= 0 else 100.0 * (1 - (inactivo - inactivo0) / dt)


def ram() -> tuple[float, float]:
    """(usada, total) en GB."""
    if psutil:
        m = psutil.virtual_memory()
        return (m.total - m.available) / GB, m.total / GB
    datos = {}
    with open("/proc/meminfo") as f:
        for linea in f:
            clave, valor = linea.split(":", 1)
            datos[clave] = int(valor.split()[0]) * 1024
    total = datos["MemTotal"]
    return (total - datos.get("MemAvailable", datos.get("MemFree", 0))) / GB, total / GB


def nucleos() -> int:
    if psutil:
        return psutil.cpu_count()
    import os
    return os.cpu_count() or 1


# --- GPU NVIDIA ----------------------------------------------------------------
def gpus() -> list[dict]:
    if not shutil.which("nvidia-smi"):
        return []
    try:
        salida = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5, check=True,
        ).stdout
    except Exception:  # noqa: BLE001
        return []
    resultado = []
    for linea in salida.splitlines():
        if linea.strip():
            nombre, util, usada, total = [c.strip() for c in linea.split(",")]
            resultado.append({
                "nombre": nombre, "util_pct": float(util),
                "mem_gb": float(usada) / 1024, "mem_total_gb": float(total) / 1024,
            })
    return resultado


# --- Contenedor (opcional) ---------------------------------------------------
_UNIDADES = {"b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3}


def _a_bytes(texto: str) -> float:
    texto = texto.strip()
    i = len(texto)
    while i and not texto[i - 1].isdigit():
        i -= 1
    return float(texto[:i] or 0) * _UNIDADES.get(texto[i:].lower() or "b", 1)


def contenedor(servicio: str, cpus: int) -> dict | None:
    try:
        nombres = subprocess.run(
            ["docker", "ps", "--filter", f"label=com.docker.compose.service={servicio}", "--format", "{{.Names}}"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout.split() or [servicio]
        salida = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{json .}}", *nombres],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
    except Exception:  # noqa: BLE001
        return None
    cpu = ram_usada = limite = 0.0
    for linea in salida.splitlines():
        if linea.strip():
            d = json.loads(linea)
            cpu += float(d["CPUPerc"].rstrip("%") or 0)
            usada, _, lim = d["MemUsage"].partition("/")
            ram_usada += _a_bytes(usada)
            limite = max(limite, _a_bytes(lim))
    return {"nombres": nombres, "cpu_pct": cpu / cpus, "ram_gb": ram_usada / GB, "ram_total_gb": limite / GB}


# --- Servidor HTTP -------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Agente de métricas para pruebas de carga")
    parser.add_argument("--puerto", type=int, default=9101)
    parser.add_argument("--docker", metavar="SERVICIO", help="servicio de compose a medir además del sistema")
    args = parser.parse_args()

    cpu = Cpu()
    if psutil:
        psutil.cpu_percent(None)
    n = nucleos()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            usada, total = ram()
            datos = {
                "host": platform.node(),
                "ts": time.time(),
                "sistema": {"cpus": n, "cpu_pct": cpu.porcentaje(), "ram_gb": usada, "ram_total_gb": total},
                "gpu": gpus(),
            }
            if args.docker:
                datos["contenedor"] = contenedor(args.docker, n)
            cuerpo = json.dumps(datos).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)

    print(f"Agente de métricas en http://0.0.0.0:{args.puerto}  (Ctrl+C para parar)")
    if not psutil and platform.system() != "Linux":
        print("AVISO: sin psutil solo funciona en Linux. Instala: pip install psutil")
    ThreadingHTTPServer(("0.0.0.0", args.puerto), Handler).serve_forever()


if __name__ == "__main__":
    main()
