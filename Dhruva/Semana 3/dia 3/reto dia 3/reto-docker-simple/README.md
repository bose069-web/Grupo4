# Reto Docker: chat con Gemma 4 (versión sencilla)

Dos contenedores:

- **ollama**: sirve el modelo Gemma 4 E4B.
- **api**: API en Python (Flask) que le hace preguntas a Ollama. Puede usar el Ollama local o uno remoto cambiando `BACKEND_URL` en el fichero `.env`.

```
reto-docker-simple/
├── docker-compose.yml   # los 2 contenedores, la red y el volumen
├── .env                 # BACKEND_URL (local o remoto) y modelo
└── api/
    ├── Dockerfile       # cómo se construye la imagen de la API
    ├── app.py           # la API
    ├── chat.py          # el chat por terminal del día anterior
    └── requirements.txt
```

## 1. Comprobar que Docker funciona

```bash
docker --version
docker run hello-world
```

Si sale *"Hello from Docker!"*, está bien instalado.

> El modelo necesita unos 10 GB de RAM y 10 GB de disco. Si tu PC va justo, pon `MODELO=gemma4:e2b` en `.env`.

## 2. Arrancar

```bash
docker compose up -d --build
```

La primera vez se descarga el modelo (unos 9,6 GB). Para ver cómo va:

```bash
docker compose logs -f ollama
```

Cuando aparezca `success`, ya está (sal con `Ctrl+C`).

## 3. Probar

En el navegador:

- <http://localhost:8000> → muestra a qué backend está conectada la API.
- <http://localhost:8000/chat?mensaje=Hola, ¿quién eres?> → respuesta del modelo.

Chat por terminal:

```bash
docker compose run --rm api python chat.py
```

## 4. Cambiar a un Ollama remoto

1. Abre `.env`, pon `#` delante de la línea local y quítaselo a la remota que quieras usar.
2. Aplica el cambio (Docker recrea solo la API):
   ```bash
   docker compose up -d
   ```
3. Comprueba en <http://localhost:8000> que `backend` ha cambiado.

¿Cómo probarlo sin Azure? Con el PC de un compañero que también tenga este proyecto arrancado: su Ollama está publicado en el puerto **11435**, así que pon `BACKEND_URL=http://IP_DEL_COMPAÑERO:11435`. Su IP la ve con `ipconfig` (Windows) o `ip a` (Linux).

Si no hay otro PC, puedes simularlo con tu propio Ollama pero entrando "desde fuera", por el puerto de tu PC:
`BACKEND_URL=http://host.docker.internal:11435`

Para volver a local, deja otra vez activa la línea `BACKEND_URL=http://ollama:11434` y repite `docker compose up -d`.

## 5. Qué hace cada cosa del docker-compose

| Concepto | En este proyecto |
|---|---|
| **Imagen** | `ollama/ollama` (ya hecha, de Docker Hub) y la de la API, que construimos con `api/Dockerfile` |
| **Contenedor** | `ollama` y `api` son las imágenes en ejecución |
| **Red** | `red_chat`: dentro de ella la API encuentra a Ollama por su nombre (`http://ollama:11434`) |
| **Volumen** | `modelos`: guarda el modelo descargado. Aunque borres el contenedor, no hay que volver a descargarlo |
| **Variable de entorno** | `BACKEND_URL`: la API se conecta a donde diga, sin cambiar el código |

## 6. Parar

```bash
docker compose down      # para y borra los contenedores (el modelo se queda guardado)
docker compose down -v   # también borra el volumen con el modelo
```

## Problemas típicos

- **`port is already allocated`**: otro programa usa el 8000 o el 11435. Cambia el primer número en `ports` (por ejemplo `"8001:8000"`).
- **La respuesta da error justo al arrancar**: el modelo aún se está descargando, mira `docker compose logs -f ollama`.
- **`model requires more system memory`**: dale más RAM a Docker Desktop o usa `gemma4:e2b`.
