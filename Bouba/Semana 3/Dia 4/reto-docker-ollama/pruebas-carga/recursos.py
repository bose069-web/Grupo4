"""
Muestreo de uso de recursos (CPU, RAM, GPU) mientras corre la prueba de carga.

Fuentes disponibles (se combinan con --recursos):
  docker:<servicio>   contenedor(es) de un servicio de docker compose (docker stats)
  host                el equipo donde corre el script (requiere psutil)
  gpu                 GPU NVIDIA del equipo (nvidia-smi)
  http://IP:9101      agente_metricas.py ejecutándose en la máquina remota

Cada muestra es un diccionario:
  {"t": segundos desde el inicio, "fuente": "...", "nivel": "contenedor|sistema|gpu",
   "cpu_pct": % del total de la máquina (0-100), "ram_gb": ..., "ram_total_gb": ...,
   "gpu_pct": ..., "gpu_mem_gb": ...}
"""

import asyncio
import json
import re
import shutil
import time

import aiohttp

GB = 1024 ** 3
_UNIDADES = {
    "b": 1, "kb": 1e3, "mb": 1e6, "gb": 1e9, "tb": 1e12,
    "kib": 1024, "mib": 1024 ** 2, "gib": 1024 ** 3, "tib": 1024 ** 4,
}


def a_bytes(texto: str) -> float:
    """'5.12GiB' -> bytes. Admite las unidades que imprime docker stats."""
    m = re.fullmatch(r"\s*([\d.]+)\s*([a-zA-Z]*)\s*", texto)
    if not m:
        return 0.0
    numero, unidad = float(m.group(1)), (m.group(2) or "b").lower()
    return numero * _UNIDADES.get(unidad, 1)


def parsear_docker_stats(linea: str) -> dict:
    """Una línea de `docker stats --format '{{json .}}'` -> números."""
    d = json.loads(linea)
    usado, _, limite = d.get("MemUsage", "0B / 0B").partition("/")
    return {
        "nombre": d.get("Name", ""),
        "cpu_pct_nucleo": float(d.get("CPUPerc", "0%").rstrip("%") or 0),  # 100% = 1 núcleo
        "ram_bytes": a_bytes(usado),
        "ram_limite_bytes": a_bytes(limite),
    }


async def _ejecutar(*args: str, timeout: float = 15) -> str:
    proc = await asyncio.create_subprocess_exec(
        *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        salida, error = await asyncio.wait_for(proc.communicate(), timeout)
    except asyncio.TimeoutError:
        proc.kill()
        raise RuntimeError(f"'{' '.join(args)}' tardó más de {timeout}s")
    if proc.returncode != 0:
        raise RuntimeError(error.decode(errors="replace").strip() or f"'{args[0]}' falló")
    return salida.decode(errors="replace")


# --- Muestreadores -------------------------------------------------------------
class Muestreador:
    nombre = "?"

    async def preparar(self) -> dict:
        """Comprueba que la fuente funciona y devuelve información del hardware."""
        raise NotImplementedError

    async def muestra(self) -> list[dict]:
        raise NotImplementedError

    async def cerrar(self):
        pass


class DockerMuestreador(Muestreador):
    """CPU y RAM de los contenedores de un servicio de compose (suma si hay réplicas)."""

    def __init__(self, servicio: str):
        self.servicio = servicio
        self.nombre = f"docker:{servicio}"
        self.contenedores: list[str] = []
        self.nucleos = 1

    async def preparar(self) -> dict:
        if not shutil.which("docker"):
            raise RuntimeError("no se encuentra el comando docker")
        salida = await _ejecutar(
            "docker", "ps", "--filter", f"label=com.docker.compose.service={self.servicio}",
            "--format", "{{.Names}}",
        )
        self.contenedores = salida.split()
        if not self.contenedores:  # quizá es el nombre exacto de un contenedor
            nombres = (await _ejecutar("docker", "ps", "--format", "{{.Names}}")).split()
            self.contenedores = [n for n in nombres if n == self.servicio]
        if not self.contenedores:
            raise RuntimeError(f"no hay ningún contenedor en marcha del servicio '{self.servicio}'")
        info = (await _ejecutar("docker", "info", "--format", "{{.NCPU}} {{.MemTotal}}")).split()
        self.nucleos = int(info[0]) if info else 1
        ram_total = int(info[1]) / GB if len(info) > 1 else None
        # Configuración del servidor Ollama (OLLAMA_NUM_PARALLEL, etc.) para el informe
        config = {}
        try:
            entorno = json.loads(await _ejecutar("docker", "inspect", "--format", "{{json .Config.Env}}",
                                                 self.contenedores[0]))
            for variable in entorno or []:
                clave, _, valor = variable.partition("=")
                if (clave.startswith("OLLAMA_") or clave == "MODEL_NAME") and valor and clave != "OLLAMA_HOST":
                    config[clave] = valor
        except Exception:  # noqa: BLE001
            pass
        return {"cpus": self.nucleos, "ram_total_gb": ram_total, "contenedores": self.contenedores,
                "config_ollama": config}

    async def muestra(self) -> list[dict]:
        salida = await _ejecutar(
            "docker", "stats", "--no-stream", "--format", "{{json .}}", *self.contenedores
        )
        filas = [parsear_docker_stats(l) for l in salida.splitlines() if l.strip()]
        if not filas:
            return []
        limite = max(f["ram_limite_bytes"] for f in filas)
        return [{
            "fuente": self.nombre, "nivel": "contenedor",
            "cpu_pct": sum(f["cpu_pct_nucleo"] for f in filas) / self.nucleos,
            "ram_gb": sum(f["ram_bytes"] for f in filas) / GB,
            "ram_total_gb": limite / GB if limite else None,
        }]


class HostMuestreador(Muestreador):
    """El equipo que lanza la prueba (en Windows/Mac con Docker Desktop incluye la VM de Docker)."""

    nombre = "host"

    async def preparar(self) -> dict:
        try:
            import psutil  # noqa: PLC0415
        except ImportError:
            raise RuntimeError("falta psutil (pip install psutil)")
        self.psutil = psutil
        psutil.cpu_percent(None)  # la primera llamada solo inicializa
        return {"cpus": psutil.cpu_count(), "ram_total_gb": psutil.virtual_memory().total / GB}

    async def muestra(self) -> list[dict]:
        mem = self.psutil.virtual_memory()
        return [{
            "fuente": self.nombre, "nivel": "sistema",
            "cpu_pct": self.psutil.cpu_percent(None),
            "ram_gb": (mem.total - mem.available) / GB,
            "ram_total_gb": mem.total / GB,
        }]


class GpuMuestreador(Muestreador):
    """GPU(s) NVIDIA del equipo local."""

    nombre = "gpu"
    CONSULTA = "utilization.gpu,memory.used,memory.total,name"

    async def _leer(self) -> list[list[str]]:
        salida = await _ejecutar(
            "nvidia-smi", f"--query-gpu={self.CONSULTA}", "--format=csv,noheader,nounits"
        )
        return [[c.strip() for c in l.split(",")] for l in salida.splitlines() if l.strip()]

    async def preparar(self) -> dict:
        if not shutil.which("nvidia-smi"):
            raise RuntimeError("no hay nvidia-smi (sin GPU NVIDIA)")
        filas = await self._leer()
        return {"gpus": [f[3] for f in filas], "gpu_mem_total_gb": sum(float(f[2]) for f in filas) / 1024}

    async def muestra(self) -> list[dict]:
        filas = await self._leer()
        return [{
            "fuente": self.nombre, "nivel": "gpu",
            "gpu_pct": sum(float(f[0]) for f in filas) / len(filas),
            "gpu_mem_gb": sum(float(f[1]) for f in filas) / 1024,
        }]


class HttpMuestreador(Muestreador):
    """Lee agente_metricas.py en la máquina remota."""

    def __init__(self, url: str):
        self.url = url
        self.nombre = f"agente:{url.split('//')[-1].split('/')[0]}"
        self.session: aiohttp.ClientSession | None = None

    async def _leer(self) -> dict:
        async with self.session.get(self.url) as r:
            r.raise_for_status()
            return await r.json(content_type=None)

    async def preparar(self) -> dict:
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=8))
        d = await self._leer()
        sistema = d.get("sistema", {})
        return {
            "host": d.get("host"), "cpus": sistema.get("cpus"),
            "ram_total_gb": sistema.get("ram_total_gb"),
            "gpus": [g.get("nombre") for g in d.get("gpu", [])],
            "contenedores": d.get("contenedor", {}).get("nombres"),
        }

    async def muestra(self) -> list[dict]:
        d = await self._leer()
        s = d.get("sistema", {})
        registro = {
            "fuente": self.nombre, "nivel": "sistema",
            "cpu_pct": s.get("cpu_pct"), "ram_gb": s.get("ram_gb"), "ram_total_gb": s.get("ram_total_gb"),
        }
        gpus = d.get("gpu") or []
        if gpus:
            registro["gpu_pct"] = sum(g["util_pct"] for g in gpus) / len(gpus)
            registro["gpu_mem_gb"] = sum(g["mem_gb"] for g in gpus)
        registros = [registro]
        c = d.get("contenedor")
        if c:
            registros.append({
                "fuente": self.nombre + ":contenedor", "nivel": "contenedor",
                "cpu_pct": c.get("cpu_pct"), "ram_gb": c.get("ram_gb"), "ram_total_gb": c.get("ram_total_gb"),
            })
        return registros

    async def cerrar(self):
        if self.session:
            await self.session.close()


def crear(especificacion: str) -> Muestreador:
    e = especificacion.strip()
    if e.startswith("docker:"):
        return DockerMuestreador(e.split(":", 1)[1])
    if e == "host":
        return HostMuestreador()
    if e == "gpu":
        return GpuMuestreador()
    if e.startswith(("http://", "https://")):
        return HttpMuestreador(e)
    raise ValueError(f"Fuente de recursos desconocida: '{e}' (usa docker:<servicio>, host, gpu o http://IP:9101)")


# --- Bucle de muestreo -------------------------------------------------------
class Monitor:
    """Toma muestras de todas las fuentes cada `intervalo` segundos, en segundo plano."""

    def __init__(self, muestreadores: list[Muestreador], intervalo: float, t0: float):
        self.muestreadores = muestreadores
        self.intervalo = intervalo
        self.t0 = t0
        self.muestras: list[dict] = []
        self.errores: dict[str, str] = {}
        self._tareas: list[asyncio.Task] = []

    async def _bucle(self, m: Muestreador):
        fallos_seguidos = 0
        while True:
            inicio = time.perf_counter()
            try:
                for registro in await m.muestra():
                    registro["t"] = round(inicio - self.t0, 2)
                    self.muestras.append(registro)
                fallos_seguidos = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                fallos_seguidos += 1
                self.errores[m.nombre] = str(exc)
                if fallos_seguidos == 5:
                    print(f"  [recursos] {m.nombre} falla repetidamente: {exc}")
            await asyncio.sleep(max(0.0, self.intervalo - (time.perf_counter() - inicio)))

    def iniciar(self):
        self._tareas = [asyncio.create_task(self._bucle(m)) for m in self.muestreadores]

    async def parar(self):
        for t in self._tareas:
            t.cancel()
        await asyncio.gather(*self._tareas, return_exceptions=True)
        for m in self.muestreadores:
            await m.cerrar()
