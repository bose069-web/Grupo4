# Reto diario

Gateway HTTP para Ollama. El mismo servicio API se conecta a un Ollama local de Docker o a un servidor Ollama remoto mediante `BACKEND_URL`.

## Requisitos

- Docker Engine y Docker Compose v2.
- Para el modo local, conexión a Internet la primera vez para descargar el modelo configurado.

## Despliegue local

Desde esta carpeta:

```sh
docker compose --profile local up -d --build
```

Compose inicia la API en `http://localhost:8000` y el servicio local de Ollama. El modelo predeterminado es `gemma3:1b`; se descarga automáticamente y queda guardado en un volumen Docker.

Comprueba el estado:

```sh
docker compose ps
curl http://localhost:8000/health/backend
```

Prueba una conversación:

```sh
curl -X POST http://localhost:8000/api/chat \
  -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"Hola"}]}'
```

## Despliegue remoto

Configura una URL de Ollama accesible desde el contenedor de la API. Por ejemplo, si Ollama escucha en el puerto `11434` de otro equipo:

```sh
BACKEND_MODE=remoto BACKEND_URL=http://192.168.1.50:11434 docker compose up -d --build api
```

En Linux, para usar Ollama instalado en el host Docker, se puede usar `http://host.docker.internal:11434` (el Compose añade el alias de host). Sustituye la dirección por la del servidor real. El servidor remoto debe tener descargado el modelo indicado por `MODEL_NAME`.

No se inicia el servicio local de Ollama en este modo. `BACKEND_URL` determina el destino y `BACKEND_MODE` solo etiqueta el modo en `/api/info`.

## Configuración

| Variable | Predeterminado | Descripción |
| --- | --- | --- |
| `BACKEND_MODE` | `local` | Etiqueta `local` o `remoto`. |
| `BACKEND_URL` | `http://ollama:11434` | URL base del servidor Ollama. |
| `MODEL_NAME` | `gemma3:1b` | Modelo usado por la API y descargado en modo local. |
| `BACKEND_API_KEY` | vacío | Token Bearer opcional para el backend. |
| `REQUEST_TIMEOUT` | `300` | Tiempo máximo de espera del modelo, en segundos. |
| `API_PORT` | `8000` | Puerto publicado de la API. |

Para cambiar el modelo local, por ejemplo:

```sh
MODEL_NAME=gemma3:1b docker compose --profile local up -d --build
```

## Endpoints

- `GET /health`: estado de la API.
- `GET /health/backend`: comprueba conexión y modelos disponibles en Ollama.
- `GET /api/info`: muestra URL, modo y modelo configurados.
- `POST /api/chat`: recibe `{"messages":[{"role":"user","content":"..."}]}` y devuelve la respuesta del modelo.

## Parada

```sh
docker compose --profile local down
```

El volumen `ollama_models` se conserva. Para borrar también los modelos descargados:

```sh
docker compose --profile local down -v
```
