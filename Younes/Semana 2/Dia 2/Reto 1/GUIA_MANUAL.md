# Guía rápida del reto

Este documento resume cómo dejar el proyecto listo para ejecutarse localmente.

## Requisitos

- Python 3.10+
- Dependencias del archivo `requirements.txt`
- Una clave válida de Gemini

## Configuración

1. Crear entorno virtual:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

2. Rellenar `config.py` con la clave real:

```python
import os

GEMINI_API_KEY = "TU_CLAVE_DE_GEMINI"
```

o exportarla antes de ejecutar:

```powershell
$env:GEMINI_API_KEY = "TU_CLAVE_DE_GEMINI"
```

## Ejecución

```powershell
python reto1.py
python analisis_imagenes.py
```

Los resultados se guardan en `outputs/`.

## Evaluación

Abre el notebook `analisis_resultados.ipynb` y ejecútalo una vez que existan los archivos JSON de salida.

## Importante

No compartas la clave ni la copies a archivos públicos o al repositorio.