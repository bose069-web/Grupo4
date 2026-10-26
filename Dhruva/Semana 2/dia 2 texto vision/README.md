# Día 6: Gemini multimodal

Entrega completa para el reto de análisis de texto y visión con Gemini. El proyecto usa `google-genai` y solicita respuestas estructuradas en JSON para que los resultados se puedan guardar y comparar.

## Estructura

- `src/text_analysis.py`: idioma, entidades, sentimiento y resumen para 10 textos.
- `src/vision_analysis.py`: OCR, descripción, escena y objetos para 5 imágenes.
- `data/`: muestras y manifiesto de imágenes.
- `assets/test_images/`: imágenes de prueba generadas localmente con Pillow.
- `notebooks/day6_gemini_analysis.ipynb`: informe ejecutable.
- `outputs/`: informes JSON generados por los scripts.
- `tests/test_day6.py`: pruebas de contratos y conteos.

## Instalación y API real

```powershell
python -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edita .env y agrega GEMINI_API_KEY
python -m src.text_analysis
python -m src.vision_analysis
```

El modelo por defecto es `gemini-2.5-flash`; se puede cambiar con `GEMINI_MODEL`. No se incluye ninguna clave en el repositorio.

## Ejecución sin clave

El modo simulado permite comprobar toda la tubería y el notebook sin red:

```powershell
python scripts/create_test_images.py
python -m src.text_analysis --mock
python -m src.vision_analysis --mock
python -m unittest discover -s tests -v
```

## Criterio de comparación

El informe de texto compara el idioma detectado contra `language_hint` y calcula exactitud y confianza media. Para visión, cada muestra conserva la confianza devuelta y se calcula la confianza media por tipo de imagen. En una ejecución real, estas métricas deben interpretarse como evaluación inicial: la precisión definitiva requiere anotaciones humanas independientes para entidades, OCR, escenas y objetos.


