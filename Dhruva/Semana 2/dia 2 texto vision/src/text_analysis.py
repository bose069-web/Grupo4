"""Structured text analysis with Gemini, plus a deterministic offline mode."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional for the offline mode
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "text_samples.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "text_results.json"

TEXT_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "language": {"type": "STRING"},
        "language_confidence": {"type": "NUMBER"},
        "entities": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "text": {"type": "STRING"},
                    "label": {"type": "STRING"},
                },
                "required": ["text", "label"],
            },
        },
        "sentiment": {"type": "STRING", "enum": ["positive", "negative", "mixed", "neutral"]},
        "sentiment_score": {"type": "NUMBER"},
        "summary": {"type": "STRING"},
    },
    "required": ["language", "language_confidence", "entities", "sentiment", "sentiment_score", "summary"],
}


def build_prompt(text: str) -> str:
    return f"""Analyze the following text. Return only valid JSON matching the requested schema.
Tasks:
1. Detect the primary language using an ISO 639-1 code.
2. Extract named entities and label each as PERSON, ORGANIZATION, LOCATION, DATE, or OTHER.
3. Classify sentiment as positive, negative, mixed, or neutral and give a score from -1 to 1.
4. Write a faithful summary in the same language as the input, maximum 30 words.
Text:
{text}"""


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Gemini response must be a JSON object")
    return value


def _mock_analysis(text: str) -> dict[str, Any]:
    lower = text.lower()
    language = "es" if any(word in lower for word in (" la ", " el ", " una ", " para ", " que ")) else "en"
    if any(word in lower for word in ("le ", " est ", " après")):
        language = "fr"
    if any(word in lower for word in (" der ", " bitte ", " und ")):
        language = "de"
    if any(word in lower for word in (" o ", " uma ", " saúde")):
        language = "pt"
    positive = ("excellent", "beautiful", "quickly", "practical", "excellent", "excelente", "práctica")
    negative = ("bloquea", "damaged", "fragile", "fragil", "frecuencia")
    positive_hits = sum(word in lower for word in positive)
    negative_hits = sum(word in lower for word in negative)
    if positive_hits and negative_hits:
        sentiment, score = "mixed", 0.0
    elif positive_hits:
        sentiment, score = "positive", 0.75
    elif negative_hits:
        sentiment, score = "negative", -0.75
    else:
        sentiment, score = "neutral", 0.0
    entities: list[dict[str, str]] = []
    for match in re.findall(r"\b[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑ-]*(?:\s+[A-ZÁÉÍÓÚÑ][\wÁÉÍÓÚÑ-]*)*", text):
        if match.lower() not in {"The", "Hi", "Please", "Guten", "La", "Le", "O"}:
            entities.append({"text": match, "label": "PROPER_NOUN"})
    return {
        "language": language,
        "language_confidence": 0.65,
        "entities": entities,
        "sentiment": sentiment,
        "sentiment_score": score,
        "summary": text[:120].rstrip(" .") + ("..." if len(text) > 120 else ""),
    }


def analyze_text(client: Any, model: str, text: str, retries: int = 3) -> dict[str, Any]:
    if client is None:
        return _mock_analysis(text)
    from google.genai import types

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=build_prompt(text),
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=TEXT_SCHEMA,
                ),
            )
            return _extract_json(response.text)
        except Exception as error:  # API/network errors should be retried briefly.
            last_error = error
            if attempt < retries - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Gemini text request failed after {retries} attempts: {last_error}") from last_error


def load_client() -> Any:
    if load_dotenv:
        load_dotenv(ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai

    return genai.Client(api_key=api_key)


def run(input_path: Path, output_path: Path, mock: bool = False) -> dict[str, Any]:
    samples = json.loads(input_path.read_text(encoding="utf-8"))
    client = None if mock else load_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    results = []
    for sample in samples:
        analysis = analyze_text(client, model, sample["text"])
        results.append({**sample, "analysis": analysis, "mode": "mock" if client is None else "gemini"})
    language_accuracy = sum(
        result["analysis"].get("language") == result["language_hint"] for result in results
    ) / len(results)
    report = {
        "model": model,
        "mode": "mock" if client is None else "gemini",
        "sample_count": len(results),
        "language_accuracy_against_hint": round(language_accuracy, 3),
        "average_language_confidence": round(
            sum(float(result["analysis"].get("language_confidence", 0)) for result in results) / len(results), 3
        ),
        "results": results,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze 10 text samples with Gemini.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mock", action="store_true", help="Run without an API key.")
    args = parser.parse_args()
    report = run(args.input, args.output, mock=args.mock)
    print(f"Processed {report['sample_count']} texts in {report['mode']} mode.")
    print(f"Language accuracy against hints: {report['language_accuracy_against_hint']:.1%}")


if __name__ == "__main__":
    main()
