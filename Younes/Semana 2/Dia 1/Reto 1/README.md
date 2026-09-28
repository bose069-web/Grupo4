# Proyecto Gemini: texto, imágenes y análisis de sentimiento

Este proyecto permite conversar con Gemini desde la terminal. Se pueden enviar mensajes de texto y analizar imágenes indicando la ruta del archivo. También incluye diez ejemplos bilingües para probar clasificación de sentimiento y extracción de entidades.

## Requisitos

- Python 3.10 o posterior.
- Una clave de Gemini API creada en [Google AI Studio](https://aistudio.google.com/apikey).
- Conexión a Internet.

Instala el SDK oficial de Google:

```powershell
python -m pip install -U google-genai
```

## Obtener y configurar la clave API

1. Abre [Google AI Studio - API keys](https://aistudio.google.com/apikey) e inicia sesión.
2. Crea una clave en un proyecto de Google Cloud o selecciona un proyecto disponible.
3. No compartas la clave ni la incluyas en capturas, mensajes o repositorios públicos.
4. En `gemini.py`, reemplaza el valor de ejemplo de `GEMINI_API_KEY` por tu clave y guarda el archivo.

**Seguridad:** este proyecto guarda la clave en el código porque así está configurado actualmente. Es cómodo para una práctica local, pero no es seguro para compartir o publicar. La documentación oficial recomienda usar una variable de entorno o un gestor de secretos. Si la clave se ha compartido o publicado, revócala en AI Studio y crea otra. No subas `gemini.py` con una clave activa a GitHub.

## Modelos, precios y cuota gratuita

El script usa por defecto `gemini-3.5-flash-lite`, que acepta texto e imágenes. Los precios oficiales el **28 de septiembre de 2026** son:

| Modelo | Nivel gratuito | Nivel de pago estándar |
| --- | --- | --- |
| `gemini-3.5-flash-lite` (modelo del proyecto) | Entrada: 0 USD; salida: 0 USD, sujeto a cuota y disponibilidad gratuita | Entrada: 0,30 USD por millón de tokens; salida: 2,50 USD por millón de tokens |
| `gemini-3.8-flash` (alternativa) | Entrada y salida sin coste en el nivel gratuito, sujeto a cuota y disponibilidad | Hasta el 31-12-2026: entrada 0,75 USD y salida 3,75 USD por millón de tokens. Desde el 01-01-2027: entrada 1,50 USD y salida 7,50 USD por millón de tokens |

En `gemini-3.5-flash-lite`, el precio de entrada de pago se aplica a texto, imagen, vídeo y audio; la salida se cobra por tokens generados. Por tanto, el coste de una petición no es fijo: depende del contenido enviado, la respuesta y el historial de la conversación. Los importes están en USD y pueden cambiar; revisa la [tabla oficial de precios](https://ai.google.dev/gemini-api/docs/pricing) antes de usar el proyecto con facturación.

El nivel gratuito no significa uso ilimitado. Los límites de peticiones por minuto (RPM), tokens por minuto (TPM) y peticiones por día (RPD) son por proyecto, dependen del modelo y del nivel de uso, y pueden cambiar. Google muestra los límites activos de cada proyecto en [AI Studio - Rate limits](https://aistudio.google.com/rate-limit); la [documentación de límites](https://ai.google.dev/gemini-api/docs/rate-limits) explica cómo funcionan. El nivel gratuito también puede permitir que Google use el contenido para mejorar sus productos; no envíes información privada.

Para probar el modelo alternativo, establece `GEMINI_MODEL` antes de iniciar el script:

```powershell
$env:GEMINI_MODEL = "gemini-3.8-flash"
python .\gemini.py
```

## Ejecutar el chat

Desde PowerShell, en la carpeta del proyecto:

```powershell
python .\gemini.py
```

Escribe un mensaje y pulsa Enter. Para analizar una imagen, introduce la ruta del archivo cuando aparezca el prompt. Usa comillas si la ruta contiene espacios:

```text
C:\Users\TuUsuario\Pictures\producto.jpg
"C:\Users\Tu Usuario\Pictures\foto de viaje.png"
```

El programa detecta archivos de imagen por su extensión, los envía junto con una instrucción de análisis y muestra la respuesta. Después puedes seguir escribiendo o enviar otra ruta; el chat conserva el contexto hasta que escribas `salir` o pulses `Ctrl+C`. La ruta debe existir y ser accesible desde la carpeta del proyecto.

## Prueba multimodal: descripción de una imagen

1. Inicia el script y proporciona una ruta a una imagen que puedas compartir.
2. Espera la respuesta de Gemini.
3. Comprueba si describe los elementos visibles, el contexto y los detalles relevantes sin inventar información que no aparezca en la imagen.
4. Puedes continuar preguntando sobre esa misma imagen o proporcionar otra ruta.

    **Respuesta de Gemini:**

Basándome en la imagen que has vuelto a compartir, aquí tienes un análisis completo y útil:

* **Descripción visual:** La imagen muestra a **dos adorables cachorros de Golden Retriever** sentados lado a lado en un prado de césped verde. El suelo está salpicado de pequeñas flores o pétalos de color anaranjado. Ambos perritos tienen la boca abierta, la lengua fuera y una expresión muy feliz y enérgica.

## Prompts de sentimiento y entidades

Envía cada prompt por separado en el chat. Cada uno solicita una clasificación como positivo, negativo o neutro, además de identificar personas, organizaciones y lugares.

### Español

1. Analiza el sentimiento del texto y clasifícalo como positivo, negativo o neutro. Extrae las entidades mencionadas (personas, organizaciones y lugares). Texto: «Me encantó la atención de Lucía en el Hotel Mirador de Sevilla; volveré pronto.»

	**Respuesta de Gemini:**

* **Sentimiento:** Positivo ("Me encantó", "volveré pronto").
* **Entidades mencionadas:**
  * **Personas:** Lucía
  * **Organizaciones:** Hotel Mirador (empresa/alojamiento)
  * **Lugares:** Sevilla

2. Analiza el sentimiento del texto y clasifícalo como positivo, negativo o neutro. Extrae las entidades mencionadas (personas, organizaciones y lugares). Texto: «La aplicación de NubeMóvil es rápida y fácil de usar. La recomiendo.»

	**Respuesta de Gemini:**

* **Sentimiento:** Positivo ("rápida y fácil de usar", "La recomiendo").
* **Entidades mencionadas:**
  * **Personas:** Ninguna.
  * **Organizaciones:** NubeMóvil (empresa/proveedor de la aplicación).
  * **Lugares:** Ninguno.

3. Analiza el sentimiento del texto y clasifícalo como positivo, negativo o neutro. Extrae las entidades mencionadas (personas, organizaciones y lugares). Texto: «El tren de Renfe llegó una hora tarde a la estación de Valencia y nadie explicó el motivo.»

	**Respuesta de Gemini:**

* **Sentimiento:** Negativo ("llegó una hora tarde", "nadie explicó el motivo").
* **Entidades mencionadas:**
  * **Personas:** Ninguna.
  * **Organizaciones:** Renfe (empresa de transporte).
  * **Lugares:** Valencia (ciudad / estación).

4. Analiza el sentimiento del texto y clasifícalo como positivo, negativo o neutro. Extrae las entidades mencionadas (personas, organizaciones y lugares). Texto: «El pedido de Mercado Libre llegó roto y el servicio de atención no resolvió el problema.»

	**Respuesta de Gemini:**

* **Sentimiento:** Negativo ("llegó roto", "no resolvió el problema").
* **Entidades mencionadas:**
  * **Personas:** Ninguna.
  * **Organizaciones:** Mercado Libre (empresa / plataforma de comercio electrónico).
  * **Lugares:** Ninguno.

5. Analiza el sentimiento del texto y clasifícalo como positivo, negativo o neutro. Extrae las entidades mencionadas (personas, organizaciones y lugares). Texto: «Marta viajará a Bogotá el próximo viernes para asistir a una conferencia.»

	**Respuesta de Gemini:**

* **Sentimiento:** Neutro (es una afirmación o declaración de hechos sin carga emocional evidente).
* **Entidades mencionadas:**
  * **Personas:** Marta
  * **Organizaciones:** Ninguna.
  * **Lugares:** Bogotá.

### English

6. Analyze the sentiment of the text and classify it as positive, negative, or neutral. Extract the entities mentioned (people, organizations, and places). Text: “The team at GreenLeaf Café in London made my visit wonderful. I’ll definitely come back.”

	**Gemini's response:**

* **Sentiment:** Positive ("wonderful", "I'll definitely come back").
* **Entities mentioned:**
  * **People:** None.
  * **Organizations:** GreenLeaf Café (business/establishment).
  * **Places:** London.

7. Analyze the sentiment of the text and classify it as positive, negative, or neutral. Extract the entities mentioned (people, organizations, and places). Text: “I’m very happy with the support I received from Daniel at BrightTech.”

	**Gemini's response:**

* **Sentiment:** Positive ("very happy").
* **Entities mentioned:**
  * **People:** Daniel
  * **Organizations:** BrightTech (company/organization)
  * **Places:** None.

8. Analyze the sentiment of the text and classify it as positive, negative, or neutral. Extract the entities mentioned (people, organizations, and places). Text: “My flight with Northstar Airlines was delayed for six hours, and the staff were unhelpful.”

	**Gemini's response:**

* **Sentiment:** Negative ("delayed for six hours", "unhelpful").
* **Entities mentioned:**
  * **People:** None.
  * **Organizations:** Northstar Airlines.
  * **Places:** None.

9. Analyze the sentiment of the text and classify it as positive, negative, or neutral. Extract the entities mentioned (people, organizations, and places). Text: “The new update from PixelWorks keeps crashing, and customer support has not replied.”

	**Gemini's response:**

* **Sentiment:** Negative ("keeps crashing", "has not replied").
* **Entities mentioned:**
  * **People:** None.
  * **Organizations:** PixelWorks.
  * **Places:** None.

10. Analyze the sentiment of the text and classify it as positive, negative, or neutral. Extract the entities mentioned (people, organizations, and places). Text: “Emma will visit Toronto next month to attend a meeting at the University of Toronto.”

	**Gemini's response:**

* **Sentiment:** Neutral (it is a statement of facts without any evident emotional charge).
* **Entities mentioned:**
  * **People:** Emma
  * **Organizations:** University of Toronto
  * **Places:** Toronto

## Resultados y verificación

- El script permite mantener una conversación de varios turnos con texto y rutas de imágenes.
- Los diez prompts cubren entradas en español e inglés y piden tanto sentimiento como entidades.
- La prueba con imágenes debe hacerse con una clave válida y una imagen local; la respuesta puede variar entre ejecuciones.

## Documentación oficial

- [Modelos disponibles](https://ai.google.dev/gemini-api/docs/models)
- [Crear y proteger claves API](https://ai.google.dev/gemini-api/docs/api-key)
- [Límites de velocidad](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Precios y nivel gratuito](https://ai.google.dev/gemini-api/docs/pricing)
