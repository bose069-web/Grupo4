"""Procesa imágenes con Gemini y guarda resultados estructurados en JSON."""

from __future__ import annotations

import argparse
import json
import mimetypes
from pathlib import Path
from typing import Any

from config import GEMINI_API_KEY


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_DIR / "data" / "imagenes.json"
DEFAULT_OUTPUT = PROJECT_DIR / "outputs" / "image_results.json"
DEFAULT_MODEL = "gemini-2.5-flash"

IMAGE_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "ocr_text": {"type": "STRING"},
        "scene_description": {"type": "STRING"},
        "scene_category": {
            "type": "STRING",
            "enum": ["document", "urban", "product", "nature", "chart", "other"],
        },
        "objects": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["ocr_text", "scene_description", "scene_category", "objects"],
}


def load_manifest(input_path: Path) -> list[dict[str, Any]]:
    """Carga y valida el manifiesto de imágenes."""
    with input_path.open(encoding="utf-8") as input_file:
        images = json.load(input_file)
    if not isinstance(images, list):
        raise ValueError("El manifiesto debe contener una lista JSON.")
    for index, item in enumerate(images, start=1):
        if not isinstance(item, dict) or not item.get("image_path"):
            raise ValueError(f"La imagen {index} debe incluir 'image_path'.")
    return images


def analyze_image(image_path: Path, client: Any, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """Pide OCR, descripción, categoría y objetos visibles para una imagen."""
    from google.genai import types

    mime_type, _ = mimetypes.guess_type(image_path.name)
    if not mime_type or not mime_type.startswith("image/"):
        raise ValueError(f"No se pudo determinar el formato de imagen: {image_path.name}")

    image_part = types.Part.from_bytes(data=image_path.read_bytes(), mime_type=mime_type)
    prompt = """Analiza la imagen sin inferir detalles que no sean visibles.
Transcribe todo el texto legible literalmente en ocr_text (usa una cadena vacía
si no hay texto). Describe brevemente la escena, elige una categoría entre
document, urban, product, nature, chart u other, e indica los objetos visibles.
Devuelve únicamente los campos definidos por el esquema JSON."""
    response = client.models.generate_content(
        model=model,
        contents=[prompt, image_part],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=IMAGE_RESPONSE_SCHEMA,
            temperature=0,
        ),
    )
    if not response.text:
        raise ValueError("Gemini devolvió una respuesta vacía.")
    return json.loads(response.text)


def run_analysis(input_path: Path, output_path: Path, model: str) -> list[dict[str, Any]]:
    """Procesa el manifiesto completo y registra fallos por imagen."""
    if not GEMINI_API_KEY or GEMINI_API_KEY == "PEGA_TU_API_KEY_AQUI":
        raise RuntimeError("Completa GEMINI_API_KEY en config.py antes de ejecutar.")

    from google import genai

    client = genai.Client(api_key=GEMINI_API_KEY)
    results = []
    for item in load_manifest(input_path):
        record = dict(item)
        image_path = (PROJECT_DIR / item["image_path"]).resolve()
        try:
            if not image_path.is_file():
                raise FileNotFoundError(f"No encuentro la imagen: {image_path}")
            record["prediction"] = analyze_image(image_path, client, model)
            record["error"] = None
        except Exception as error:
            record["prediction"] = None
            record["error"] = str(error)
        results.append(record)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Manifiesto JSON de imágenes")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Ruta del JSON de resultados")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo Gemini a utilizar")
    args = parser.parse_args()

    results = run_analysis(args.input, args.output, args.model)
    completed = sum(result["prediction"] is not None for result in results)
    print(f"Análisis terminado: {completed}/{len(results)} imágenes. Resultados: {args.output}")


if __name__ == "__main__":
    main()