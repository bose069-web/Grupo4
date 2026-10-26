# Conceptos de Docker: imágenes, contenedores, volúmenes y redes

Guía para explicar al resto del equipo (perfil ASIX). Cada concepto se enlaza con lo que hemos montado en este repositorio.

---

## 0. ¿Qué problema resuelve Docker?

"En mi máquina funciona": la app depende de una versión de Python, de unas librerías, de variables de entorno… Docker empaqueta la aplicación **junto con todo lo que necesita** para que se ejecute igual en el portátil de cualquiera, en el servidor del instituto o en Azure.

| | Máquina virtual | Contenedor |
|---|---|---|
| Qué virtualiza | Hardware completo | Solo el proceso (usa el kernel del host) |
| Sistema operativo | Uno completo por VM | Comparte el kernel del host |
| Arranque | Minutos | Segundos |
| Tamaño | GB | MB (normalmente) |
| Aislamiento | Muy fuerte | Fuerte (namespaces + cgroups del kernel Linux) |

En Windows y macOS, Docker Desktop crea por debajo una pequeña VM Linux (WSL2 en Windows) donde corren los contenedores.

---

## 1. Imagen

**Una plantilla de solo lectura** con el sistema de ficheros y la configuración necesarios para ejecutar una aplicación.

- Analogía: la imagen es la **ISO de instalación** (o una *clase* en programación); el contenedor es el **equipo ya instalado y encendido** (el *objeto*).
- Está formada por **capas**: cada instrucción del `Dockerfile` crea una. Si una capa no cambia, Docker la reutiliza (caché).
- Se descargan de un registro (Docker Hub, GitHub Container Registry, Azure Container Registry…) o se construyen con `docker build`.

### El Dockerfile

| Instrucción | Qué hace | Ejemplo en el repo |
|---|---|---|
| `FROM` | Imagen base de la que partimos | `FROM python:3.12-slim` |
| `WORKDIR` | Directorio de trabajo dentro de la imagen | `WORKDIR /app` |
| `COPY` | Copia ficheros del proyecto a la imagen | `COPY app.py chat.py ./` |
| `RUN` | Ejecuta un comando **al construir** la imagen | `RUN pip install -r requirements.txt` |
| `ENV` | Variable de entorno por defecto | `ENV PYTHONUNBUFFERED=1` |
| `ARG` | Variable solo para el build | `ARG PRELOAD_IN_IMAGE=false` |
| `EXPOSE` | Documenta el puerto (no lo publica) | `EXPOSE 8000` |
| `USER` | Usuario con el que corre el proceso | `USER appuser` |
| `HEALTHCHECK` | Cómo sabe Docker si el servicio está sano | `CMD python -c "...urlopen('/health')"` |
| `CMD` / `ENTRYPOINT` | Qué se ejecuta **al arrancar** el contenedor | `CMD ["uvicorn", "app:app", ...]` |

**Truco de la caché** (ver `api/Dockerfile`): se copia primero `requirements.txt` y se instalan las dependencias, y *después* el código. Así, si solo cambias `app.py`, Docker reutiliza la capa del `pip install` y el build tarda segundos.

```bash
docker images                     # imágenes locales
docker pull ollama/ollama         # descargar una imagen
docker build -t reto/chat-api ./api
docker history reto/chat-api      # ver las capas
```

---

## 2. Contenedor

**Una imagen en ejecución**: un proceso aislado con su propio sistema de ficheros, red, procesos y límites de recursos. Encima de las capas de la imagen se añade una capa **de escritura** propia.

- Se pueden lanzar muchos contenedores de la misma imagen.
- **Son efímeros**: si borras el contenedor, lo que escribió en su capa se pierde (para eso están los volúmenes).
- En el repo, `api` y `chat` usan **la misma imagen** con **distinto comando**: uno arranca la API y el otro el chat por terminal.

```bash
docker run hello-world            # crea + arranca un contenedor
docker ps / docker ps -a          # en ejecución / todos
docker logs -f <contenedor>       # ver la salida
docker exec -it <contenedor> sh   # entrar en un contenedor en marcha
docker stop / start / rm <contenedor>
```

Ciclo de vida: `created → running → (paused) → exited → removed`.

---

## 3. Volúmenes

La forma de que los datos **sobrevivan** al contenedor.

| Tipo | Dónde viven los datos | Uso típico |
|---|---|---|
| **Volumen con nombre** | Gestionado por Docker | Bases de datos, modelos descargados |
| **Bind mount** | Una carpeta concreta de tu PC | Desarrollo (editar código y verlo dentro) |
| **tmpfs** | Solo en RAM | Datos temporales o sensibles |

En el repo: `ollama_models:/root/.ollama`. Gemma 4 E4B pesa ~9,6 GB; sin volumen, cada vez que se recreara el contenedor habría que volver a descargarlo.

```bash
docker volume ls
docker volume inspect reto_ollama_models
docker compose down        # el volumen se conserva
docker compose down -v     # el volumen se borra
```

Detalle curioso: si un volumen con nombre **vacío** se monta en una ruta donde la imagen ya tiene ficheros, Docker copia esos ficheros al volumen. Por eso `PRELOAD_IN_IMAGE=true` funciona: el modelo que va dentro de la imagen pasa al volumen la primera vez.

---

## 4. Redes

Docker crea redes virtuales para que los contenedores se comuniquen.

| Driver | Qué hace |
|---|---|
| `bridge` | Red privada en el host (la habitual). Las que crea Compose son de este tipo |
| `host` | El contenedor usa directamente la red del host (sin aislamiento) |
| `none` | Sin red |
| `bridge` + `internal: true` | Red sin salida a internet |

Ideas clave:

- **DNS interno**: en una red definida por el usuario, los contenedores se resuelven **por nombre de servicio** (servidor DNS `127.0.0.11`). Por eso la API usa `http://ollama:11434` y no una IP.
- **Exponer ≠ publicar**: `EXPOSE` solo documenta. `ports: "8000:8000"` sí abre el puerto en tu PC (`puerto_host:puerto_contenedor`).
- **`localhost` dentro de un contenedor es el propio contenedor**, no tu PC. Para llegar a tu PC: `host.docker.internal`.
- **Segmentación**: igual que con VLANs, separamos niveles.

En el repo:

```
Navegador ──:8080──► frontend ──(red frontend)──► api ──(red backend)──► ollama          (modo local)
                                                   └──► host:11435 ──► ollama-remoto       (modo remoto, red "remoto")
```

`frontend` y `ollama` no comparten red: el frontend **no puede** llegar a Ollama. Demostración:

```bash
docker compose exec frontend wget -qO- -T 3 http://ollama:11434   # bad address 'ollama'
docker network inspect reto_backend                                # quién está en cada red
```

El `ollama-remoto` está en una red propia (`reto_remoto`) que la API no comparte. La única forma de llegar a él es **publicar un puerto en el host** (`11435:11434`) y que la API salga por `host.docker.internal:11435`. Es el mismo camino que seguiría hacia otro PC de clase o una VM en la nube: así simulamos un backend remoto sin tener Azure.

¿Por qué la red backend no es `internal: true`? Porque Ollama necesita internet para descargar el modelo y la API necesita salir hacia el backend remoto. Sería una buena mejora para producción: red interna + modelo ya incluido en la imagen.

---

## 5. Docker Compose

Describe **todo el stack** en un fichero YAML y lo levanta con un comando.

| Clave | Para qué |
|---|---|
| `services` | Cada contenedor (build/imagen, puertos, variables, redes, volúmenes) |
| `networks` / `volumes` | Recursos compartidos |
| `depends_on` + `condition: service_healthy` | Orden de arranque: la API espera a que Ollama tenga el modelo |
| `healthcheck` | Comando que dice si el servicio está sano |
| `profiles` | Servicios que solo arrancan si activas el perfil (`local`, `remoto-simulado`, `cli`) |
| `${VARIABLE:-defecto}` | Sustitución de variables desde la shell o `.env` |

```bash
docker compose up -d --build     # construir y levantar en segundo plano
docker compose ps                # estado
docker compose logs -f <servicio>
docker compose config            # ver el YAML final ya con las variables sustituidas
docker compose down
```

---

## 6. Variables de entorno: la misma imagen en local y en remoto

La API **no tiene la URL de Ollama escrita en el código**: la lee de `BACKEND_URL`. Así una sola imagen sirve para todos los entornos; solo cambia la configuración.

```
.env          → BACKEND_URL=http://ollama:11434                 (local)
.env.remoto   → BACKEND_URL=http://host.docker.internal:11435   (remoto simulado)
                BACKEND_URL=http://192.168.x.x:11435            (PC de un compañero)
                BACKEND_URL=http://IP_VM:11434                  (Azure, cuando esté disponible)
```

Prioridad: **shell > `.env` > valor por defecto del compose**.

---

## 7. Guion para la explicación (15 minutos)

1. **(2 min)** `docker run hello-world` y explicar qué ha pasado: pull de la imagen → crear contenedor → ejecutar → salir.
2. **(3 min)** Abrir `api/Dockerfile` y recorrer las instrucciones. Hacer `docker build` dos veces y enseñar que la segunda usa la caché.
3. **(3 min)** `docker compose up -d` y `docker compose ps`. Enseñar los tres servicios y su estado *healthy*.
4. **(3 min)** Redes: el `wget` que falla desde el frontend y `docker network inspect`.
5. **(2 min)** Volúmenes: `docker compose down` + `up` → el modelo no se vuelve a descargar.
6. **(2 min)** `docker compose --env-file .env.remoto up -d` y ver cómo la web pasa de "Ollama local" a "Ollama remoto" sin reconstruir nada. Mejor aún si el remoto es el PC de un compañero.

---

## 8. Preguntas de repaso

1. **¿Qué diferencia hay entre una imagen y un contenedor?**
   La imagen es la plantilla de solo lectura; el contenedor es una instancia en ejecución de esa imagen con una capa de escritura propia.
2. **Si borro el contenedor de Ollama, ¿pierdo el modelo?**
   No, porque está en el volumen `reto_ollama_models`. Solo se pierde con `docker compose down -v` o `docker volume rm`.
3. **¿Por qué la API puede usar `http://ollama:11434` y el frontend no?**
   Porque el DNS interno resuelve nombres de servicio solo dentro de cada red, y el frontend no está en la red `backend`.
4. **¿Qué diferencia hay entre `EXPOSE 8000` y `ports: "8000:8000"`?**
   `EXPOSE` solo documenta el puerto; `ports` lo publica en el host para acceder desde fuera.
5. **¿Por qué no poner `BACKEND_URL=http://localhost:11434` en el contenedor de la API?**
   Porque dentro del contenedor `localhost` es el propio contenedor de la API, donde no hay ningún Ollama.
6. **¿Qué hace `condition: service_healthy` en `depends_on`?**
   Hace que la API no arranque hasta que el healthcheck de Ollama sea correcto (servidor activo y modelo descargado), no solo hasta que el contenedor exista.
