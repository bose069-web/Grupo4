# Informe: modelos abiertos y acceso a una VM de Azure

## 1. Objetivo y metodología

El objetivo es explorar Hugging Face, comparar la familia Gemma 4 y preparar una
comparación reproducible en la VM de Azure de Inetum. Las cifras de VRAM son
estimaciones de inferencia: dependen de la precisión, cuantización, longitud de
contexto, batch y runtime. No deben confundirse con requisitos de entrenamiento.

Para pesos, una aproximación útil es:

- BF16/FP16: `parámetros × 2 bytes`, más aproximadamente 10–25% de overhead.
- INT8: `parámetros × 1 byte`, más overhead.
- INT4: `parámetros × 0,5 bytes`, más overhead.

En MoE, los parámetros **activos** afectan al cómputo por token, pero normalmente
hay que alojar los pesos de **todos** los expertos; por eso la VRAM no se calcula
solo con los parámetros activos.

## 2. Familia Gemma 4 en Hugging Face

Fuente principal: [ficha técnica oficial de Gemma 4](https://ai.google.dev/gemma/docs/core/model_card_4)
y [colección Gemma 4 en Hugging Face](https://huggingface.co/collections/google/gemma-4).
Los modelos son open-weight y usan Apache 2.0 según la ficha oficial.

| Modelo | Parámetros efectivos / totales | VRAM orientativa (INT4 / BF16) | Modalidades de entrada | Contexto | Benchmarks oficiales |
|---|---:|---:|---|---:|---|
| Gemma 4 E2B | 2,3B efectivos; 5,1B con embeddings | 4–6 GB / 12–14 GB | Texto, imagen, audio; también procesa vídeo como frames | 128K | MMLU Pro 60,0%; AIME 37,5%; LiveCodeBench v6 44,0%; GPQA Diamond 43,4% |
| Gemma 4 E4B | 4,5B efectivos; 8B con embeddings | 6–8 GB / 18–21 GB | Texto, imagen, audio; también vídeo como frames | 128K | MMLU Pro 69,4%; AIME 42,5%; LiveCodeBench v6 52,0%; GPQA Diamond 58,6% |
| Gemma 4 12B Unified | 11,95B | 8–10 GB / 28–32 GB | Texto, imagen y audio; también vídeo como frames | 256K | MMLU Pro 77,2%; AIME 77,5%; LiveCodeBench v6 72,0%; GPQA Diamond 78,8% |
| Gemma 4 26B-A4B | 25,2B totales; 3,8B activos (MoE) | 16–20 GB / 56–64 GB | Texto e imagen; vídeo mediante frames | 256K | MMLU Pro 82,6%; AIME 88,3%; LiveCodeBench v6 77,1%; GPQA Diamond 82,3% |
| Gemma 4 31B | 30,7B | 18–24 GB / 68–76 GB | Texto e imagen; vídeo mediante frames | 256K | MMLU Pro 85,2%; AIME 89,2%; LiveCodeBench v6 80,0%; GPQA Diamond 84,3% |

### Interpretación

* La `E` de E2B/E4B significa **effective parameters**: las embeddings por
  capa hacen que el número efectivo sea menor que el número almacenado.
* En 26B-A4B, el cómputo por token se parece más a un modelo de unos 4B, pero
  los pesos de los expertos siguen requiriendo memoria. La cuantización o el
  offload puede cambiar mucho el resultado práctico.
* Los modelos pequeños son los candidatos naturales para portátil, edge o una
  GPU pequeña. 12B es un equilibrio razonable. 26B-A4B y 31B necesitan una GPU
  de servidor o cuantización agresiva.
* Las cifras de benchmark son las publicadas por Google; no son una prueba
  ejecutada en la futura VM de Inetum. Los resultados pueden cambiar con el
  prompt, el modo de razonamiento, la implementación y la versión del modelo.

## 3. Comparación de modelos open-source/open-weight

La expresión “open-source” se usa aquí de forma práctica para modelos con pesos
publicables y licencia de uso documentada. No todas las licencias son OSI:
Llama, por ejemplo, usa una licencia comunitaria propia.

| Modelo | Parámetros | VRAM orientativa (INT4 / BF16) | Licencia | Idiomas | Casos de uso |
|---|---:|---:|---|---|---|
| Gemma 4 E4B | 4,5B efectivos; 8B almacenados | 6–8 / 18–21 GB | Apache 2.0 | 140+; multilingüe | Chat, razonamiento, código, visión/audio en tamaños compatibles, agentes |
| Meta Llama 3.1 8B Instruct | 8B | 5–6 / 19–22 GB | Llama 3.1 Community License | Inglés, alemán, francés, italiano, portugués, hindi, español y tailandés | Asistentes, generación de texto/código, RAG y síntesis |
| Microsoft Phi-3 Mini 4K Instruct | 3,8B | 3–5 / 9–11 GB | MIT | Principalmente inglés | Edge, baja latencia, razonamiento matemático/lógico, dispositivos con memoria limitada |
| Mistral 7B Instruct v0.3 | 7,3B aprox. | 5–6 / 17–20 GB | Apache 2.0 | Principalmente inglés; capacidad multilingüe no equivalente a la de Llama 3.1 | Chat, generación, function calling, prototipos y despliegues locales |
| Qwen2.5 7B Instruct | 7,6B aprox. | 5–6 / 18–21 GB | Apache 2.0 | Multilingüe, incluido chino e inglés | Chat multilingüe, código, extracción estructurada y RAG |

Las cifras de esta tabla son reglas de dimensionamiento para batch 1 y contexto
moderado; KV-cache y visión pueden elevarlas. Las licencias, idiomas y casos de
uso deben comprobarse en la ficha de la versión exacta antes de un uso comercial.

Fuentes:

* [Llama 3.1 8B Instruct, ficha de Hugging Face](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)
* [Phi-3 Mini 4K Instruct, ficha de Hugging Face](https://huggingface.co/microsoft/Phi-3-mini-4k-instruct)
* [Mistral 7B Instruct v0.3, ficha de Hugging Face](https://huggingface.co/mistralai/Mistral-7B-Instruct-v0.3)
* [Qwen2.5 7B Instruct, ficha de Hugging Face](https://huggingface.co/Qwen/Qwen2.5-7B-Instruct)

## 4. Procedimiento de Azure pendiente

No es correcto inventar el inventario ni respuestas de una VM a la que todavía
no hay acceso. El script `azure_compare.py` hará lo siguiente:

1. Consultar `GET /v1/models` y guardar la lista real de modelos.
2. Seleccionar dos modelos indicados por el usuario.
3. Enviar exactamente el mismo prompt a ambos mediante
   `POST /v1/chat/completions`.
4. Registrar respuesta, latencia, código HTTP y errores en
   `resultados-azure.json`.

### Prompt controlado

> Explica en español, para una persona técnica no especialista, qué diferencia
> hay entre parámetros totales y parámetros activos en un modelo Mixture-of-Experts.
> Usa un ejemplo numérico sencillo, indica una ventaja y una limitación, y responde
> en un máximo de 180 palabras.

### Qué analizar después

Para cada respuesta se calificará de 0 a 2:

| Criterio | 0 | 1 | 2 |
|---|---|---|---|
| Exactitud técnica | Incorrecta | Parcial | Correcta |
| Cumplimiento del formato | No cumple | Cumple parcialmente | Cumple completamente |
| Claridad en español | Confusa | Comprensible | Clara y precisa |
| Ejemplo numérico | Ausente/incorrecto | Válido pero poco claro | Válido y pedagógico |
| Latencia | Registrar, no puntuar sin umbral | Registrar | Registrar |

No se debe declarar un “ganador” solo por longitud. Se compararán exactitud,
claridad, cumplimiento del límite y latencia, manteniendo temperatura y límite
de tokens iguales.

## 5. Limitaciones y próximos pasos

1. Crear la cuenta de Hugging Face personalmente en
   [huggingface.co/join](https://huggingface.co/join); no se deben compartir
   contraseñas ni tokens.
2. Pasar el endpoint de Inetum, el método de autenticación, el nombre del header
   y, si no es OpenAI-compatible, los paths documentados.
3. Ejecutar el script y anexar `model_inventory` y `responses` de
   `resultados-azure.json` a la entrega.
4. Sustituir las estimaciones de VRAM por mediciones de la VM si la API expone
   hardware o métricas de inferencia.

