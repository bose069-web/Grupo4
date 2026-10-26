# Informe de pruebas de carga: local vs. Azure

## Alcance y método

El script [`load_test.py`](./load_test.py) usa `asyncio` y `aiohttp` para lanzar
peticiones concurrentes. Cada escenario ejecuta 5, 10 y 20 usuarios simultáneos.
Registra latencia media, p50, p95, errores, tokens/s y CPU/RAM del proceso
cliente. Los tokens se toman de `eval_count` de Ollama o de `usage` en APIs
OpenAI-compatible; si el servidor no los devuelve, la métrica queda como `null`
en lugar de inventarse.

> La CPU/RAM local que mide el script es la del generador de carga. Para medir la
> VM de Azure hay que proporcionar métricas del host (Azure Monitor, `docker
> stats` o Prometheus) y añadirlas al CSV, porque el cliente no puede observar
> recursos privados del servidor.

## Instalación

```bash
python3 -m pip install -r requirements-load.txt
```

## Ejecución antes de optimizar

Con el proxy Flask local:

```bash
python3 load_test.py --backend local-before \
  --url http://127.0.0.1:8084/chat --protocol proxy \
  --output resultados/local-before.json
```

Con una VM Azure que exponga Ollama:

```bash
python3 load_test.py --backend azure-before \
  --url http://IP_DE_LA_VM:11434/api/chat --protocol ollama \
  --model MODELO_AZURE --output resultados/azure-before.json
```

Con una VM OpenAI-compatible:

```bash
python3 load_test.py --backend azure-before \
  --url https://HOST/v1/chat/completions --protocol openai \
  --model MODELO_AZURE --api-key "$AZURE_API_KEY" \
  --output resultados/azure-before.json
```

## Optimizaciones aplicadas

1. **Caché de respuestas frecuentes**: se habilita con
   `ENABLE_RESPONSE_CACHE=true`; usa TTL configurable y una clave basada en el
   mensaje normalizado.
2. **Parámetros de inferencia**: `TEMPERATURE=0.2` y `MAX_TOKENS=128` reducen
   variabilidad y trabajo innecesario para este benchmark. Son configurables y
   no se deben considerar óptimos para todos los casos de uso.

Activación:

```bash
ENABLE_RESPONSE_CACHE=true TEMPERATURE=0.2 MAX_TOKENS=128 \
  docker compose up -d --build
```

Repetición:

```bash
python3 load_test.py --backend local-after \
  --url http://127.0.0.1:8084/chat --protocol proxy \
  --output resultados/local-after.json
```

Para que el caché sea medible, las peticiones usan una lista fija de cuatro
prompts. El escenario debe repetirse al menos dos veces: la primera calienta la
memoria y la segunda mide los aciertos.

## Comparación y gráficas

```bash
python3 graficar_resultados.py resultados/*-before.json resultados/*-after.json
```

La carpeta `resultados/graficas` contiene:

* `latencia-p95.png`
* `tokens-por-segundo.png`
* `errores.png`

## Tabla comparativa

Ejecutar el comando anterior produce un CSV por ejecución. Consolidar sus filas
en esta tabla, sin rellenar valores no medidos:

| Escenario | Backend | Éxitos/total | Errores | Latencia p95 (ms) | Tokens/s | CPU generador (%) | RAM delta (MB) |
|---|---|---:|---:|---:|---:|---:|---:|
| 5 usuarios | Local | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| 5 usuarios | Azure | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| 10 usuarios | Local | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| 10 usuarios | Azure | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| 20 usuarios | Local | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |
| 20 usuarios | Azure | pendiente | pendiente | pendiente | pendiente | pendiente | pendiente |

## Análisis

El cuello de botella se identifica como el primer escenario donde aumenta
fuertemente p95, aparece una tasa de errores no nula o cae tokens/s. No se debe
declarar qué backend falla primero hasta ejecutar los seis escenarios con el
mismo prompt, límite de tokens y timeout. La comparación antes/después debe usar
las mismas cargas y una temperatura equivalente.

## Resultados locales medidos

La baseline se ejecutó con caché desactivada y `MAX_TOKENS=32` para mantener la
prueba dentro de los recursos disponibles. La ejecución optimizada activó caché,
usó `TEMPERATURE=0.2` y conservó `MAX_TOKENS=32`. Los prompts fueron los cuatro
prompts fijos del script; por tanto, desde el escenario de 10 usuarios ya había
respuestas reutilizables en caché.

| Escenario | Estado | Éxitos/total | Errores | Latencia p95 (ms) | Tokens/s |
|---|---|---:|---:|---:|---:|
| 5 usuarios | Local baseline | 5/5 | 0% | 35.121,80 | 2,15 |
| 5 usuarios | Local optimizado | 5/5 | 0% | 31.996,17 | 2,26 |
| 10 usuarios | Local baseline | 9/10 | 10% | 57.353,46 | 1,61 |
| 10 usuarios | Local optimizado | 10/10 | 0% | 10,70 | 4.146,74 |
| 20 usuarios | Local baseline | 7/20 | 65% | 56.277,14 | 1,14 |
| 20 usuarios | Local optimizado | 20/20 | 0% | 19,14 | 2.289,65 |

El primer punto de fallo local es **20 usuarios simultáneos**: la cola de
inferencias satura el modelo y aparecen 13 timeouts/errores. La mejora grande en
10 y 20 usuarios procede principalmente del caché de los prompts repetidos; no
debe extrapolarse a consultas nuevas. Las gráficas generadas están en
[`resultados/graficas`](./resultados/graficas).

## Estado de la ejecución Azure

No se ejecutaron resultados remotos porque el workspace no contiene una URL real
de la VM: solo hay placeholders (`IP_DE_LA_VM`) y no hay credencial configurada.
Ejecutar los comandos de la sección anterior con el endpoint real generará los
seis registros Azure necesarios. No es válido rellenar esa tabla con estimaciones.
