"""Analiza textos con Gemini y guarda resultados estructurados en JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from config import GEMINI_API_KEY


PROJECT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = PROJECT_DIR / "data" / "textos.json"
DEFAULT_OUTPUT = PROJECT_DIR / "outputs" / "text_results.json"
DEFAULT_MODEL = "gemini-3.5-flash-lite"

TEXT_RESPONSE_SCHEMA = {
	"type": "OBJECT",
	"properties": {
		"language": {"type": "STRING"},
		"entities": {
			"type": "ARRAY",
			"items": {
				"type": "OBJECT",
				"properties": {
					"name": {"type": "STRING"},
					"type": {"type": "STRING"},
				},
				"required": ["name", "type"],
			},
		},
		"sentiment": {"type": "STRING", "enum": ["positive", "neutral", "negative"]},
		"summary": {"type": "STRING"},
	},
	"required": ["language", "entities", "sentiment", "summary"],
}


def load_texts(input_path: Path) -> list[dict[str, Any]]:
	"""Carga ejemplos desde un JSON que contiene una lista de objetos."""
	with input_path.open(encoding="utf-8") as input_file:
		texts = json.load(input_file)
	if not isinstance(texts, list):
		raise ValueError("El archivo de entrada debe contener una lista JSON.")
	for index, item in enumerate(texts, start=1):
		if not isinstance(item, dict) or not item.get("text"):
			raise ValueError(f"El ejemplo {index} debe ser un objeto con el campo 'text'.")
	return texts


def analyze_text(text: str, client: Any, model: str = DEFAULT_MODEL) -> dict[str, Any]:
	"""Pide a Gemini idioma, entidades, sentimiento y resumen en JSON."""
	from google.genai import types

	prompt = f"""Analiza el texto siguiente. No inventes información.
Devuelve el idioma en español, las entidades nombradas con su tipo,
el sentimiento (positive, neutral o negative) y un resumen breve.
Respeta exactamente el esquema JSON indicado.

TEXTO:
{text}"""
	response = client.models.generate_content(
		model=model,
		contents=prompt,
		config=types.GenerateContentConfig(
			response_mime_type="application/json",
			response_schema=TEXT_RESPONSE_SCHEMA,
			temperature=0,
		),
	)
	if not response.text:
		raise ValueError("Gemini devolvió una respuesta vacía.")
	result = json.loads(response.text)
	if result["sentiment"] not in {"positive", "neutral", "negative"}:
		raise ValueError("Gemini devolvió un sentimiento no reconocido.")
	return result


def run_analysis(input_path: Path, output_path: Path, model: str) -> list[dict[str, Any]]:
	"""Procesa todos los textos y guarda cada resultado junto con su referencia."""
	if not GEMINI_API_KEY or GEMINI_API_KEY == "PEGA_TU_API_KEY_AQUI":
		raise RuntimeError("Completa GEMINI_API_KEY en config.py antes de ejecutar.")

	from google import genai

	client = genai.Client(api_key=GEMINI_API_KEY)
	results = []
	for item in load_texts(input_path):
		record = {key: value for key, value in item.items() if key != "text"}
		record["text"] = item["text"]
		try:
			record["prediction"] = analyze_text(item["text"], client, model)
			record["error"] = None
		except Exception as error:  # Conserva los demás ejemplos si uno falla.
			record["prediction"] = None
			record["error"] = str(error)
		results.append(record)

	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
	return results


def main() -> None:
	parser = argparse.ArgumentParser(description=__doc__)
	parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="JSON con los textos")
	parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Ruta del JSON de resultados")
	parser.add_argument("--model", default=DEFAULT_MODEL, help="Modelo Gemini a utilizar")
	args = parser.parse_args()

	results = run_analysis(args.input, args.output, args.model)
	completed = sum(result["prediction"] is not None for result in results)
	print(f"Análisis terminado: {completed}/{len(results)} textos. Resultados: {args.output}")


if __name__ == "__main__":
	main()
