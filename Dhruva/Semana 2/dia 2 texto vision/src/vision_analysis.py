"""Multimodal image analysis with Gemini and a deterministic offline mode."""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "images_manifest.json"
DEFAULT_OUTPUT = ROOT / "outputs" / "vision_results.json"
VISION_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "ocr_text": {"type": "STRING"},
        "scene": {"type": "STRING"},
        "objects": {"type": "ARRAY", "items": {"type": "STRING"}},
        "description": {"type": "STRING"},
        "confidence": {"type": "NUMBER"},
    },
    "required": ["ocr_text", "scene", "objects", "description", "confidence"],
}


def build_prompt(task: str) -> str:
    return f"""Analyze this image for the task: {task}
Return only valid JSON with these fields:
- ocr_text: all legible text, or an empty string
- scene: one concise scene category
- objects: visible objects as an array of short nouns
- description: a concise factual description
- confidence: overall confidence from 0 to 1"""


def _extract_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0]
    value = json.loads(cleaned)
    if not isinstance(value, dict):
        raise ValueError("Gemini response must be a JSON object")
    return value


def _mock_analysis(image: dict[str, Any]) -> dict[str, Any]:
    task = image["task"]
    kind = image["type"]
    if kind == "document":
        return {"ocr_text": "INVOICE 1042 | Total: $249.00 | Due: 2026-09-30", "scene": "scanned document", "objects": ["invoice", "text", "table"], "description": "A scanned invoice with a structured table and a total amount.", "confidence": 0.92}
    if kind == "urban":
        return {"ocr_text": "", "scene": "urban street", "objects": ["buildings", "road", "traffic light", "trees"], "description": "A city street with buildings, a road, trees, and traffic infrastructure.", "confidence": 0.86}
    if kind == "product":
        return {"ocr_text": "ORBIT MUG", "scene": "product photo", "objects": ["mug", "table", "label"], "description": "A ceramic mug presented as a product on a plain surface.", "confidence": 0.9}
    if task == "ocr":
        return {"ocr_text": "SAMPLE RECEIPT | Coffee $4.50", "scene": "receipt", "objects": ["receipt", "text"], "description": "A small receipt containing readable purchase text.", "confidence": 0.88}
    return {"ocr_text": "", "scene": "indoor scene", "objects": ["desk", "lamp", "chair"], "description": "An indoor workspace with common office objects.", "confidence": 0.8}


def analyze_image(client: Any, model: str, image: dict[str, Any], retries: int = 3) -> dict[str, Any]:
    if client is None:
        return _mock_analysis(image)
    from google.genai import types

    image_bytes = Path(image["path"]).read_bytes()
    mime_type = image.get("mime_type", "image/png")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=[build_prompt(image["task"]), types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=VISION_SCHEMA,
                ),
            )
            return _extract_json(response.text)
        except Exception as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(2**attempt)
    raise RuntimeError(f"Gemini vision request failed after {retries} attempts: {last_error}") from last_error


def load_client() -> Any:
    if load_dotenv:
        load_dotenv(ROOT / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    from google import genai

    return genai.Client(api_key=api_key)


def run(manifest_path: Path, output_path: Path, mock: bool = False) -> dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    client = None if mock else load_client()
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    results = []
    for image in manifest:
        image_for_request = dict(image)
        image_path = Path(image["path"])
        if not image_path.is_absolute():
            image_for_request["path"] = str((ROOT / image_path).resolve())
        analysis = analyze_image(client, model, image_for_request)
        results.append({**image, "analysis": analysis, "mode": "mock" if client is None else "gemini"})
    by_type: dict[str, list[float]] = {}
    for result in results:
        by_type.setdefault(result["type"], []).append(float(result["analysis"].get("confidence", 0)))
    comparison = [{"type": kind, "count": len(scores), "average_confidence": round(sum(scores) / len(scores), 3)} for kind, scores in sorted(by_type.items())]
    report = {"model": model, "mode": "mock" if client is None else "gemini", "image_count": len(results), "comparison": comparison, "results": results}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze five test images with Gemini Vision.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--mock", action="store_true", help="Run without an API key.")
    args = parser.parse_args()
    report = run(args.manifest, args.output, mock=args.mock)
    print(f"Processed {report['image_count']} images in {report['mode']} mode.")
    for item in report["comparison"]:
        print(f"{item['type']}: confidence {item['average_confidence']:.1%}")


if __name__ == "__main__":
    main()
