# Reto del Día: Hugging Face, Gemma 4 y modelos open-source

## 1. Cuenta en Hugging Face (acción manual)

1. Registrarse en https://huggingface.co/join y verificar el correo.
2. Crear un token de acceso (Settings > Access Tokens, tipo *Read*) para descargar modelos y usar Inference Providers.
3. Explorar el Hub: https://huggingface.co/models (filtros: *Tasks*, *Libraries*, *Licenses*, *Languages*). Colección de Gemma 4: https://huggingface.co/collections/google/gemma-4

## 2. Familia Gemma 4 (fuente: model card `google/gemma-4-31B-it`)

Licencia: Apache 2.0. Contexto: 128K (E2B/E4B) y 256K (12B/26B-A4B/31B). Más de 140 idiomas en preentrenamiento, 35+ con soporte directo. Vocabulario 262K.

| Modelo | Parámetros efectivos / activos | Parámetros totales | VRAM BF16 (est.) | VRAM Q4 (est.) | Modalidades (entrada) | Arquitectura |
|---|---|---|---|---|---|---|
| E2B | 2.3B efectivos | 5.1B (con embeddings) | ~10 GB | ~3-4 GB | Texto, imagen, audio | Densa + PLE |
| E4B | 4.5B efectivos | 8B (con embeddings) | ~16 GB | ~5-6 GB | Texto, imagen, audio | Densa + PLE |
| 12B | 11.95B | 11.95B | ~24 GB | ~7-8 GB | Texto, imagen, audio (sin encoders) | Densa "Unified" |
| 26B-A4B | 3.8B activos | 25.2B (128 expertos, 8 activos + 1 compartido) | ~50 GB | ~15-16 GB | Texto, imagen | MoE |
| 31B | 30.7B | 30.7B | ~62 GB | ~18-20 GB | Texto, imagen | Densa |

Notas:
- VRAM estimada: parámetros totales x 2 bytes (BF16) o x ~0.5-0.6 bytes (Q4), sin KV cache. El contexto largo añade memoria extra. En el MoE se cargan todos los expertos aunque solo 3.8B estén activos (más rápido, no más ligero).
- Audio: máximo 30 s. Vídeo: máximo 60 s a 1 fps.

### Benchmarks (modelos instruct; columnas: 31B | 26B-A4B | 12B | E4B | E2B | Gemma 3 27B)

| Benchmark | 31B | 26B-A4B | 12B | E4B | E2B | Gemma 3 27B |
|---|---|---|---|---|---|---|
| MMLU Pro | 85.2% | 82.6% | 77.2% | 69.4% | 60.0% | 67.6% |
| GPQA Diamond | 84.3% | 82.3% | 78.8% | 58.6% | 43.4% | 42.4% |
| AIME 2026 (sin tools) | 89.2% | 88.3% | 77.5% | 42.5% | 37.5% | 20.8% |
| LiveCodeBench v6 | 80.0% | 77.1% | 72.0% | 52.0% | 44.0% | 29.1% |
| Codeforces ELO | 2150 | 1718 | 1659 | 940 | 633 | 110 |
| MMMLU (multilingüe) | 88.4% | 86.3% | 83.4% | 76.6% | 67.4% | 70.7% |
| MMMU Pro (visión) | 76.9% | 73.8% | 69.1% | 52.6% | 44.2% | 49.7% |
| MRCR v2 8-needle 128k | 66.4% | 44.1% | 43.4% | 25.4% | 19.1% | 13.5% |

Conclusión: el 26B-A4B ofrece ~97% de la calidad del 31B activando solo 3.8B parámetros; el 12B es el mejor equilibrio para GPU de consumo con audio; E2B/E4B son para dispositivos edge.

## 3. Comparativa de modelos open-source

Valores de otros modelos basados en conocimiento general (verificar en cada model card antes de entregar).

| Modelo | Parámetros | VRAM FP16 / Q4 (est.) | Licencia | Idiomas | Contexto | Casos de uso |
|---|---|---|---|---|---|---|
| Gemma 4 E4B | 4.5B ef. (8B tot.) | ~16 GB / ~5 GB | Apache 2.0 | 140+ (35+ soportados) | 128K | On-device, asistentes multimodales (audio/imagen), ASR |
| Gemma 4 12B | 11.95B | ~24 GB / ~8 GB | Apache 2.0 | 140+ | 256K | Razonamiento, código, multimodal en GPU de consumo |
| Gemma 4 26B-A4B | 25.2B (3.8B activos) | ~50 GB / ~16 GB | Apache 2.0 | 140+ | 256K | Inferencia rápida con alta calidad, agentes |
| Gemma 4 31B | 30.7B | ~62 GB / ~19 GB | Apache 2.0 | 140+ | 256K | Máxima calidad, razonamiento, código |
| Llama 3.1 8B Instruct | 8B | ~16 GB / ~5 GB | Llama 3.1 Community License (uso comercial con condiciones) | 8 (EN, ES, FR, DE, IT, PT, HI, TH) | 128K | Chat, RAG, resumen, function calling |
| Llama 3.3 70B Instruct | 70B | ~140 GB / ~40 GB | Llama 3.3 Community License | 8 | 128K | Asistentes de alta calidad, código, razonamiento |
| Phi-3-mini-4k/128k Instruct | 3.8B | ~8 GB / ~2.5 GB | MIT | Principalmente inglés | 4K / 128K | Edge, móviles, razonamiento ligero |
| Mistral 7B Instruct v0.3 | 7.3B | ~15 GB / ~4.5 GB | Apache 2.0 | Principalmente inglés, algo de europeos | 32K | Chat, function calling, base para fine-tuning |
| Mixtral 8x7B Instruct | 46.7B (12.9B activos) | ~93 GB / ~26 GB | Apache 2.0 | EN, FR, DE, ES, IT | 32K | Chat multilingüe europeo, código |

## 4. Conexión a la VM de Azure de Inetum (PENDIENTE)

Pendiente de recibir la API. Cuando esté disponible se necesitará:
- URL base del endpoint (probablemente compatible con OpenAI: `/v1/models`, `/v1/chat/completions`).
- API key / método de autenticación.
- Si hay restricciones de red (VPN, IP permitida).

Plan:
1. `GET /v1/models` para listar los modelos desplegados.
2. Elegir 2+ modelos y enviar el mismo prompt (mismos parámetros: temperature, max_tokens).
3. Registrar respuesta, latencia y tokens/s; evaluar calidad (corrección, coherencia, idioma, seguimiento de instrucciones).
4. Guardar la clave en variable de entorno (`AZURE_VM_API_KEY`), nunca en el código.

## 5. Ejecución del mismo prompt en 2 modelos (PENDIENTE)

Prompts propuestos (cubren distintas capacidades):
1. Razonamiento: "Un tren sale a 80 km/h y otro a 100 km/h en sentido contrario desde puntos separados 450 km. ¿Cuándo se cruzan? Explica paso a paso."
2. Código: "Escribe una función en Python que valide un IBAN español y añade tests."
3. Resumen en español: texto de ~300 palabras a resumir en 3 viñetas.

Rúbrica (1-5): corrección, claridad, seguimiento de instrucciones, calidad del español, latencia.
