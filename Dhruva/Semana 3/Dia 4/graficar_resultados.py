#!/usr/bin/env python3
"""Generate comparison charts from one or more load-test JSON files."""

import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("resultados/graficas"))
    args = parser.parse_args()
    rows = []
    for path in args.inputs:
        document = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(document.get("summary", []))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for metric, title, filename, ylabel in (
        ("latency_ms_p95", "Latencia p95 por concurrencia", "latencia-p95.png", "ms"),
        ("tokens_per_second_avg", "Tokens por segundo", "tokens-por-segundo.png", "tokens/s"),
        ("error_rate_percent", "Tasa de errores", "errores.png", "%"),
    ):
        plt.figure(figsize=(8, 4.5))
        for backend in sorted({row["backend"] for row in rows}):
            selected = sorted((row for row in rows if row["backend"] == backend),
                              key=lambda row: row["concurrency"])
            plt.plot([row["concurrency"] for row in selected],
                     [row[metric] or 0 for row in selected], marker="o", label=backend)
        plt.xlabel("Usuarios simultáneos")
        plt.ylabel(ylabel)
        plt.title(title)
        plt.grid(alpha=0.25)
        plt.legend()
        plt.tight_layout()
        plt.savefig(args.output_dir / filename, dpi=150)
        plt.close()
    print(f"Gráficas guardadas en {args.output_dir}")


if __name__ == "__main__":
    main()
