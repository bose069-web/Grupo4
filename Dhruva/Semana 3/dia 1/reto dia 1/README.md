# Reto del día: Hugging Face, Gemma 4 y VM de Azure

**Fecha de preparación:** 16 de octubre de 2026  
**Estado:** investigación documental completada; validación de Azure pendiente de credenciales.

## Qué está completado y qué queda pendiente

| Actividad | Estado | Evidencia |
|---|---|---|
| Explorar el Hub de Hugging Face | Completado documentalmente | Enlaces oficiales del informe |
| Comparar Gemma 4 E2B, E4B, 12B, 26B-A4B y 31B | Completado | `informe.md`, sección 2 |
| Tabla de al menos cinco modelos open-source | Completado | `informe.md`, sección 3 |
| Consultar los modelos desplegados en la VM de Inetum | Pendiente de endpoint/token | `azure_compare.py` |
| Ejecutar el mismo prompt en dos modelos de la VM | Pendiente de endpoint/token | `azure_compare.py` genera `resultados-azure.json` |
| Crear una cuenta de Hugging Face | Acción personal que debe hacer el alumno | https://huggingface.co/join |

No se incluyen credenciales en ningún archivo. Cuando se disponga de los datos de Inetum, usar:

```bash
export AZURE_API_BASE="https://HOST_O_ENDPOINT"
export AZURE_API_KEY="token-secreto"
python3 azure_compare.py --models modelo-a modelo-b
```

Si la API no es compatible con OpenAI, ajustar `--models-path`, `--chat-path` y
`--auth-header` según la documentación de Inetum.

