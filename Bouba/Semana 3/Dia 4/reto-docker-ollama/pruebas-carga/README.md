# Pruebas de carga y optimización

Script de estrés con **asyncio + aiohttp** que lanza 5, 10 y 20 usuarios simultáneos contra el chat. Mide latencia, tiempo hasta el primer token, tokens/s, errores y uso de CPU/RAM/GPU, y genera un **informe comparativo con gráficas**: local vs remoto, y antes vs después de optimizar.

| Fichero | Para qué |
|---|---|
| `carga.py` | Script de pruebas de estrés (lo que se ejecuta) |
| `recursos.py` | Muestreo de CPU/RAM/GPU: `docker stats`, el propio PC, `nvidia-smi` o el agente remoto |
| `metricas.py` | Cálculo de percentiles, tokens/s, % en cola… (lo usan los otros dos scripts) |
| `informe.py` | Genera `informe/informe.html`, `informe.md`, `graficas/*.png` y `resumen.csv` |
| `agente_metricas.py` | Se copia a la **máquina remota** para medir su CPU/RAM/GPU |
| `prompts.txt` | Las preguntas que hacen los usuarios simulados |
| `conclusiones.plantilla.md` | Guion para vuestras conclusiones (se copia a `conclusiones.md`) |
| `simulador/ollama_simulado.py` | Ollama falso para probar el script en 2 minutos, **sin modelo** |
| `../optimizaciones/*.env` | Las optimizaciones, activables con `--env-file` |

---

## 0. Preparación (una vez)

Desde la raíz del repositorio, reconstruye la API (incluye la caché y las métricas nuevas):

```bash
docker compose up -d --build
```

Entorno de Python para los scripts:

```bash
cd pruebas-carga
python -m venv .venv
# Windows:            .venv\Scripts\activate
# Linux/macOS/WSL:    source .venv/bin/activate
pip install -r requirements.txt
```

> **¿Cuánto tarda?** Cada ejecución tiene 3 escenarios. Cada usuario hace 2 preguntas con un límite de 120 s cada una, así que una ejecución dura como máximo unos 15 minutos. Son 4 ejecuciones: local y remoto, antes y después.

### (Opcional) Probar que todo funciona sin el modelo

```bash
python simulador/ollama_simulado.py --acelerar 10
# en otra terminal:
python carga.py --tipo ollama --url http://localhost:11500 --modelo gemma4:e4b --backend local --fase prueba \
       --usuarios 2,4 --timeout 15 --recursos http://localhost:11500/metricas --salida resultados-prueba
python informe.py --resultados resultados-prueba --salida informe-prueba
```

El informe saldrá marcado como **DATOS SIMULADOS**. Borra `resultados-prueba/` e `informe-prueba/` después.

---

## 1. Fase «antes» (sin optimizaciones)

### Backend local

Comandos desde la raíz del repositorio:

```bash
docker compose up -d                                    # stack local, configuración por defecto
cd pruebas-carga
python carga.py --backend local --fase antes
```

El script detecta solo el contenedor `ollama` y mide su CPU/RAM con `docker stats`. Si tienes GPU NVIDIA, también la mide.

### Backend remoto

Elige la opción que tengáis disponible:

**A) PC de un compañero (recomendada mientras no haya Azure).** Usa hardware distinto y una red real.

En el PC del compañero (con este mismo repositorio):

```bash
docker compose --env-file .env.remoto up -d ollama-remoto       # Ollama publicado en el puerto 11435
python pruebas-carga/agente_metricas.py --docker ollama-remoto  # sus métricas, en el puerto 9101
```

Si usa Windows, tiene que permitir los puertos 11435 y 9101 en el firewall.

En tu PC: en `.env.remoto` deja `COMPOSE_PROFILES=` vacío y pon `BACKEND_URL=http://IP_DEL_COMPAÑERO:11435`. Después:

```bash
docker compose stop ollama
docker compose --env-file .env.remoto up -d
cd pruebas-carga
python carga.py --backend remoto --fase antes --recursos http://IP_DEL_COMPAÑERO:9101
```

**B) VM de Azure (cuando haya acceso).** Usa el modelo grande. Igual que la opción A, con estos cambios:
- `BACKEND_URL=http://IP_VM:11434`.
- En la VM se ejecuta `python3 agente_metricas.py`. No necesita instalar nada en Linux.
- Abre en el NSG los puertos 11434 y 9101 **solo para tu IP**, o usa túneles SSH.

**C) Remoto simulado en tu mismo PC.** Solo sirve para practicar el procedimiento, porque comparte CPU y RAM con el local:

```bash
docker compose stop ollama
docker compose --env-file .env.remoto up -d
cd pruebas-carga
python carga.py --backend remoto --fase antes          # mide el contenedor ollama-remoto
```

---

## 2. Optimizaciones

Están en la carpeta `optimizaciones/` como ficheros `.env` que se suman a la configuración base. No hay que tocar código.

| Fichero | Qué hace | Dónde actúa |
|---|---|---|
| `1-cache.env` | Caché de respuestas frecuentes (TTL 10 min) y **agrupación de peticiones idénticas simultáneas**: si 8 usuarios preguntan lo mismo a la vez, Ollama solo genera una respuesta | API (local y remoto) |
| `2-parametros.env` | `num_predict=256` (máx. tokens), `temperature=0.3`, `think=false`. En el servidor: `OLLAMA_NUM_PARALLEL=4`, contexto 2048, flash attention y caché KV en 8 bits | API + servidor Ollama |
| `3-cuantizacion.env` | Modelo local más cuantizado: `gemma4:e4b-it-qat` (4 bits QAT, 6,1 GB) | Ollama local |

> **Escalado horizontal (réplicas):** no lo usamos. En un solo PC, dos réplicas de Ollama comparten la misma CPU y duplican la RAM (unos 10 GB cada una), así que no aumentan la capacidad. Tendría sentido con varias máquinas o con una VM con más recursos.

### Fase «después»: local

Desde la raíz del repositorio:

```bash
docker compose --env-file .env --env-file optimizaciones/1-cache.env --env-file optimizaciones/2-parametros.env --env-file optimizaciones/3-cuantizacion.env up -d
cd pruebas-carga
python carga.py --backend local --fase despues
```

La primera vez, Ollama descarga el modelo cuantizado (6,1 GB) antes de arrancar. Si en tu PC estaba en marcha `ollama-remoto`, páralo antes para que no ocupe RAM: `docker compose stop ollama-remoto`.

### Fase «después»: remoto

En tu PC (la caché y los parámetros de petición están en tu API):

```bash
docker compose --env-file .env.remoto --env-file optimizaciones/1-cache.env --env-file optimizaciones/2-parametros.env up -d
cd pruebas-carga
python carga.py --backend remoto --fase despues --recursos http://IP_REMOTA:9101
```

La parte de servidor de `2-parametros.env` (las variables `OLLAMA_*`) tiene que aplicarse **en la máquina remota**:
- **PC del compañero:** `docker compose --env-file .env.remoto --env-file optimizaciones/2-parametros.env up -d ollama-remoto`.
- **VM de Azure:** ejecuta `sudo systemctl edit ollama`, añade una línea `Environment="OLLAMA_NUM_PARALLEL=4"` por cada variable y después `sudo systemctl restart ollama`.

### (Opcional) Medir cada optimización por separado

Para saber cuánto aporta cada una, haz ejecuciones intermedias con otra etiqueta de fase:

```bash
docker compose --env-file .env --env-file optimizaciones/1-cache.env up -d
python carga.py --backend local --fase opt1-cache
```

El informe ordena las fases: `antes`, después las intermedias por fecha y `despues` al final.

---

## 3. Informe

```bash
python informe.py
```

- Abre `informe/informe.html` en el navegador. Con **Ctrl+P → Guardar como PDF** obtienes el PDF.
- `informe/informe.md` + `informe/graficas/` sirven para verlo directamente en GitHub.
- Copia `conclusiones.plantilla.md` a `conclusiones.md`, rellénalo con vuestro análisis y vuelve a ejecutar `informe.py`: se añade al final.

Si repites una prueba, el informe usa automáticamente **la última ejecución** de cada fase y backend. Las anteriores se quedan en `resultados/`.

### Qué incluye

1. Configuración de cada ejecución: modelo, cuantización, caché, parámetros, variables `OLLAMA_*` y hardware.
2. **Tabla local vs remoto** para cada escenario.
3. Gráficas: latencia p50/p95, TTFT, tokens/s totales y por petición, errores, % en cola, CPU, RAM y GPU.
4. **Cuellos de botella detectados automáticamente**: con cuántos usuarios falla primero cada backend y la causa probable (cola, CPU, RAM, GPU o red).
5. **Tabla antes vs después** con la mejora en % y qué configuración cambió.
6. Evolución de cada prueba en el tiempo: cada petición y la CPU/RAM en ese momento.

---

## 4. Cómo leer los resultados

| Si ves… | Significa… | Optimización que ayuda |
|---|---|---|
| Mucho % de **espera en cola** y CPU baja | Ollama atiende de una en una | `OLLAMA_NUM_PARALLEL` |
| **CPU ~100 %** y los tokens/s totales no suben con más usuarios | El modelo satura la CPU | Cuantizar, `num_predict` o más hardware (remoto) |
| **RAM** cerca del límite | Modelo + contexto no caben | Cuantizar, menos contexto, KV `q8_0` |
| Errores **timeout** | Responde, pero tarde | Todo lo anterior. Subir `--timeout` solo esconde el problema |
| Errores **http_503** | La cola de Ollama está llena | `OLLAMA_MAX_QUEUE`, o menos carga |
| Errores **conexion** | Red, firewall o NSG | Revisar la conectividad |
| **TTFT alto** en el remoto incluso con 5 usuarios | Latencia de red o carga del modelo | Calentar el modelo, `OLLAMA_KEEP_ALIVE` |
| Mucho % de **razonamiento** | El modelo «piensa» antes de responder | `MODEL_THINK=false` |

**¿Por qué se repiten preguntas?** El script usa una semilla fija (todas las fases reciben exactamente la misma carga) y reparte las preguntas con frecuencias desiguales (`--zipf 1`): unas pocas se repiten mucho, como en un chat real. Por eso la caché acierta. El informe muestra el % de preguntas repetidas para que quede claro. Con `--zipf 0` todas son igual de probables.

---

## 5. Opciones de `carga.py`

```
--backend local|remoto|...        etiqueta (obligatoria)
--fase antes|despues|...          etiqueta (obligatoria)
--url http://localhost:8000       API del stack (o un Ollama con --tipo ollama --modelo X)
--usuarios 5,10,20                escenarios
--peticiones-por-usuario 2
--timeout 120                     segundos por petición
--recursos docker:ollama          también: host, gpu, http://IP:9101 (repetible)
--zipf 1.0                        0 = preguntas al azar
--opciones '{"num_predict":256}'  opciones de Ollama en la propia petición
```

`python carga.py --help` muestra todas las opciones.

**Con la versión sencilla del proyecto (Flask, sin caché ni streaming en la API)**, usa el script directamente contra Ollama:
`python carga.py --tipo ollama --url http://localhost:11435 --modelo gemma4:e4b --backend local --fase antes`.
Los parámetros del modelo se pasan con `--opciones '{"num_predict":256,"temperature":0.3}' --think false`.

## Problemas frecuentes

- **`No se puede contactar con http://localhost:8000`**: el stack no está levantado (`docker compose ps`).
- **`docker:ollama no disponible`**: el contenedor no está en marcha o Ollama está instalado fuera de Docker. Usa `--recursos host`.
- **Casi todo da timeout ya con 5 usuarios**: es un resultado válido (el cuello de botella) y es lo que hay que optimizar. Si quieres ver más escenarios con éxito, prueba `--peticiones-por-usuario 1`.
- **El remoto tiene mucho TTFT en la primera petición**: el modelo se estaba cargando. El script hace una petición de calentamiento, pero si la VM descarga el modelo por inactividad (`OLLAMA_KEEP_ALIVE`), vuelve a cargarlo.
