import json
import tempfile
import unittest
from pathlib import Path

from src.text_analysis import _extract_json, run as run_text
from src.vision_analysis import run as run_vision

ROOT = Path(__file__).resolve().parents[1]


class Day6PipelineTests(unittest.TestCase):
    def test_extract_json_accepts_markdown_fence(self):
        self.assertEqual(_extract_json("```json\n{\"ok\": true}\n```"), {"ok": True})

    def test_text_pipeline_processes_ten_samples(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_text(ROOT / "data" / "text_samples.json", Path(directory) / "text.json", mock=True)
        self.assertEqual(report["sample_count"], 10)
        self.assertEqual(len(report["results"]), 10)
        self.assertGreaterEqual(report["language_accuracy_against_hint"], 0.8)
        self.assertTrue(all("summary" in item["analysis"] for item in report["results"]))

    def test_vision_pipeline_processes_five_images(self):
        with tempfile.TemporaryDirectory() as directory:
            report = run_vision(ROOT / "data" / "images_manifest.json", Path(directory) / "vision.json", mock=True)
        self.assertEqual(report["image_count"], 5)
        self.assertEqual(sum(item["count"] for item in report["comparison"]), 5)
        self.assertTrue(all(0 <= item["analysis"]["confidence"] <= 1 for item in report["results"]))

    def test_manifests_are_valid_json(self):
        for file_name in ("text_samples.json", "images_manifest.json"):
            with (ROOT / "data" / file_name).open(encoding="utf-8") as file:
                self.assertIsInstance(json.load(file), list)


if __name__ == "__main__":
    unittest.main()
