# Reto 1 - Análisis de texto e imágenes con Gemini

Este proyecto ya está preparado para ejecutarse con tu clave de Gemini. Solo necesitas instalar dependencias, poner la clave, y ejecutar los dos scripts de análisis.

## Estructura

- `reto1.py`: analiza los textos y guarda los resultados en `outputs/text_results.json`.
- `analisis_imagenes.py`: analiza las imágenes y guarda los resultados en `outputs/image_results.json`.
- `data/`: conjunto de ejemplos y referencias para texto e imágenes.
- `images/`: imágenes de prueba del reto.
- `analisis_resultados.ipynb`: notebook para comparar resultados con referencias.
- `config.py`: aquí se guarda tu clave local de Gemini.
- `config.example.py`: plantilla para crear `config.py`.

## 1) Preparar entorno

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## 2) Poner la clave de Gemini

Abre el archivo `config.py` y rellena tu clave real. Si prefieres, puedes exportarla como variable de entorno antes de ejecutar.

```python
import os

GEMINI_API_KEY = "TU_CLAVE_DE_GEMINI_AQUI"
# o bien:
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
```

También puedes hacerlo de esta forma:

```powershell
$env:GEMINI_API_KEY = "TU_CLAVE_DE_GEMINI"
```

> No compartas la clave ni la subas a repositorios públicos.

## 3) Ejecutar análisis

Desde la carpeta del proyecto:

```powershell
python reto1.py
python analisis_imagenes.py
```

Cada script crea su JSON en `outputs/`.

## 4) Evaluar resultados

Abre `analisis_resultados.ipynb` y ejecuta todas las celdas para comparar las predicciones con las referencias del dataset.

## Notas

- El proyecto necesita una API key válida de Gemini para producir resultados reales.
- Si la clave falla o no está definida, los scripts lo indicarán claramente.
- Los JSON de `outputs/` se crean al ejecutar los scripts; no deben dejarse resultados antiguos o ficticios.