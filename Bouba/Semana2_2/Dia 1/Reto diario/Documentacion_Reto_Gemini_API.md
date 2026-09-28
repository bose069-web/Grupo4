# Reto Gemini API

## Objetivo

Utilizar la API de Google Gemini desde Python para:

- Enviar prompts de texto.
- Analizar sentimiento.
- Extraer entidades.
- Explorar capacidades multimodales mediante imágenes.

---

## Instalación

Instalar las librerías necesarias:

```bash
pip install google-genai
pip install pillow
```

---

## Obtención de la API Key

1. Acceder a Google AI Studio.
2. Iniciar sesión con una cuenta Google.
3. Ir a la sección API Keys.
4. Crear una nueva API Key.
5. Copiar la clave generada.
6. Configurarla en los scripts Python mediante:

```python
client = genai.Client(
    api_key="API KEY"
)
```

---

## Parte 1: Análisis de Sentimiento

Se enviaron 10 textos:

- 5 en español.
- 5 en inglés.

Para cada texto se obtuvo:

- Sentimiento (Positivo, Negativo o Neutro).
- Entidades detectadas.
- Explicación breve.

Resultado generado:

resultados_sentimiento.txt

---

## Parte 2: Capacidades Multimodales

Se envió una imagen al modelo Gemini.

El modelo generó:

- Descripción detallada.
- Objetos detectados.
- Información contextual de la imagen.

Resultado generado:

resultado_imagen.txt

---

## Modelo utilizado

models/gemini-3.5-flash-lite

---

## Resultados obtenidos

La API respondió correctamente para:

✅ Generación de texto

✅ Análisis de sentimiento

✅ Extracción de entidades

✅ Análisis de imágenes

Los resultados quedaron almacenados en archivos de texto para su revisión.

---

## Estructura del proyecto

Dia 1/

├── Script_sentimientos.py

├── resultados_sentimiento.txt

├── script_imagen.py

├── resultado_imagen.txt

├── imagen.jpg

└── README.md

---

## Conclusiones

Google Gemini permite integrar capacidades avanzadas de IA mediante una API sencilla de utilizar desde Python.

Durante las pruebas se comprobó el correcto funcionamiento de:

- Procesamiento de lenguaje natural.
- Clasificación de sentimientos.
- Extracción de entidades.
- Comprensión multimodal de imágenes.

La herramienta ofrece una integración rápida y resultados precisos para tareas de IA generativa.