"""Punto de entrada unico: ejecuta los dos retos del dia en orden.

    python ejecutar_todo.py                 # texto + vision
    python ejecutar_todo.py --solo vision   # solo una parte
    python ejecutar_todo.py --modelo models/gemini-2.5-flash
"""

from __future__ import annotations

import argparse
import runpy
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

SCRIPTS = {
    "texto": BASE / "analisis_textos.py",
    "vision": BASE / "analisis_imagenes.py",
}


def ejecutar(parte: str, modelo: str | None) -> None:
    args = [str(SCRIPTS[parte])]
    if modelo:
        args += ["--modelo", modelo]
    print(f"\n{'=' * 70}\n  {parte.upper()}\n{'=' * 70}")
    sys.argv = args
    runpy.run_path(str(SCRIPTS[parte]), run_name="__main__")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ejecuta los dos retos del dia 2")
    parser.add_argument("--solo", choices=["texto", "vision"], help="Ejecuta solo una parte")
    parser.add_argument("--modelo", help="Modelo de Gemini para las dos partes")
    args = parser.parse_args()

    partes = [args.solo] if args.solo else ["texto", "vision"]
    for parte in partes:
        ejecutar(parte, args.modelo)

    print(f"\n{'=' * 70}\n  Fin. Resultados en: {BASE / 'resultados'}\n{'=' * 70}")


if __name__ == "__main__":
    main()
