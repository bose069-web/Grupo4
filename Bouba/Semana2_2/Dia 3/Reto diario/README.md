# Transcripción de voz con Gemini (ASIX)

Prototipo del día: Speech-to-Text con la API de Gemini, interfaz web y endpoint Flask. Perfil ASIX.

## Cómo se ha planteado la práctica

El enunciado pedía la **opción B (Python)**: enviar ficheros de audio (`.wav`, `.mp3` y formatos compatibles) a Gemini y pedir la transcripción, más un **endpoint API** que reciba el audio, lo envíe a Gemini y devuelva el texto, documentando la arquitectura de red.

La solución se ha separado en tres capas:

1. **Cliente Python** (`transcribir_audio.py`): sube un archivo a Gemini, pide la transcripción en español y devuelve solo el texto. Sirve para pruebas por lotes desde la terminal.
2. **API Flask** (`app.py`): expone `POST /transcribir`, valida el formato, guarda un temporal, llama a Gemini y responde en JSON. La API key permanece en el servidor (`.env`).
3. **Interfaz** (`index.html`): el usuario elige un archivo o graba con el micrófono (`MediaRecorder`) y el navegador envía el audio al backend. La transcripción final la hace Gemini, no el navegador.

Los tres guiones de prueba en español están en `guiones_audios.txt` (corto, medio y largo). Las transcripciones de referencia de esas pruebas se guardaron en `audio1.txt`, `audio2.txt` y `audio3.txt`.

La comparativa Web Speech API frente a Gemini se documenta aquí y también aparece en la interfaz y en `comparativa_y_arquitectura.md`. En este prototipo Gemini es el motor de transcripción; el navegador se usa para capturar o adjuntar el audio.

## Cómo está ordenado el proyecto

```text
Dia 2/
├── README.md                      # Este documento
├── app.py                         # Servidor Flask: UI + POST /transcribir
├── transcribir_audio.py           # Cliente Gemini (CLI y función usada por Flask)
├── Script_Audio.py                # Atajo que lanza transcribir_audio.py
├── index.html                     # Interfaz: archivo, grabación, resultado, comparativa
├── comparativa_y_arquitectura.md  # Comparativa detallada y diagrama de red
├── guiones_audios.txt             # Guiones de los 3 audios de prueba (español)
├── audio1.txt                     # Transcripción de la prueba 1
├── audio2.txt                     # Transcripción de la prueba 2
├── audio3.txt                     # Transcripción de la prueba 3
└── .env                           # GEMINI_API_KEY (no compartir)
```

| Archivo | Rol |
| --- | --- |
| `transcribir_audio.py` | Núcleo: `files.upload` + `generate_content` con Gemini |
| `app.py` | Red local: escucha en `127.0.0.1:5000`, sirve `index.html` y el endpoint |
| `index.html` | Prototipo de interfaz con integración de transcripción |
| `comparativa_y_arquitectura.md` | Entrega escrita de ventajas/desventajas y flujo de red |
| `guiones_audios.txt` | Texto esperado de las 3 grabaciones |
| `audio1.txt` … `audio3.txt` | Resultado de transcripción de cada prueba |

Formatos aceptados por el endpoint: `.wav`, `.mp3`, `.m4a`, `.ogg`, `.flac`, `.webm`.

## Cómo ejecutarlo

Dependencias: `flask`, `python-dotenv`, `google-genai`.

1. Define `GEMINI_API_KEY` en `.env` (opcionalmente `GEMINI_MODEL`).
2. Arranca el servidor:

```powershell
python app.py
```

3. Abre `http://127.0.0.1:5000`, sube un audio o graba y pulsa transcribir.

Desde terminal, sin interfaz:

```powershell
python transcribir_audio.py ruta\al\audio.mp3 -o salida.txt
```

Contra el endpoint:

```powershell
curl.exe -X POST http://127.0.0.1:5000/transcribir -F "audio=@audio.mp3"
```

Respuesta correcta:

```json
{
  "transcripcion": "..."
}
```

Errores: falta el archivo (`400`), formato no permitido (`415`), fallo de Gemini (`502`).

## Arquitectura de red

```text
Navegador o curl
    → POST /transcribir  (multipart/form-data, campo audio)
        → Flask (127.0.0.1:5000)
            → valida extensión, guarda temporal
            → API Gemini (clave solo en el servidor)
            → JSON { "transcripcion": "..." }
            → elimina el temporal
    ← texto en el navegador
```

La clave no se incluye en `index.html` ni se envía al cliente.

## Comparativa: Web Speech API vs Gemini

| Característica | Web Speech API | Gemini (este prototipo) |
| --- | --- | --- |
| Tiempo de respuesta | Tiempo real: el texto aparece mientras se habla | Por lotes: se envía el audio completo y luego llega el texto |
| Precisión | Media; suele fallar con ruido, acentos o nombres propios | Alta; usa el contexto del audio entero |
| Dónde corre | Solo en el navegador (y no en todos igual) | Backend Python + API de Gemini |
| Archivos `.wav` / `.mp3` | No está pensada para ficheros largos ya grabados | Diseñada para enviar ficheros y transcribirlos |
| Conexión | Depende del navegador y de su servicio de reconocimiento | Internet desde el servidor hacia Gemini |
| API key | No se expone en el frontend | Debe quedarse en `.env` en el servidor |
| Ventaja principal | Dictado inmediato, sin backend | Mejor precisión y procesamiento por lotes |
| Inconveniente principal | Compatibilidad y calidad variables | Latencia, cuota de API y hace falta servidor |

**Conclusión.** Web Speech API encaja en subtítulos o dictado en vivo dentro del navegador. Gemini encaja cuando hay grabaciones (wav/mp3), se quiere conservar el texto y se prioriza la precisión. Esta práctica usa Gemini para la transcripción y el navegador para elegir o grabar el audio, con Flask como puente de red (perfil ASIX).

## Entregable

Prototipo funcional de interfaz con transcripción de voz: página web + `POST /transcribir` + cliente Gemini, más esta comparativa y la documentación de arquitectura.
