"""Transcribe un archivo de audio usando la API de Gemini."""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
from google import genai

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def transcribir(ruta_audio: str, modelo: str | None = None) -> str:
    """Sube un audio a Gemini y devuelve su transcripcion en espanol."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Define la variable de entorno GEMINI_API_KEY antes de ejecutar el script.")

    cliente = genai.Client(api_key=api_key)
    archivo = cliente.files.upload(file=ruta_audio)
    respuesta = cliente.models.generate_content(
        model=modelo or os.getenv("GEMINI_MODEL", "models/gemini-3.5-flash-lite"),
        contents=[
            "Transcribe este audio en espanol. Devuelve solo la transcripcion, sin comentarios.",
            archivo,
        ],
    )
    return respuesta.text.strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe un audio con Gemini")
    parser.add_argument("audio", help="Ruta del archivo .wav, .mp3, .m4a u otro formato compatible")
    parser.add_argument("-o", "--salida", help="Archivo de texto donde guardar la transcripcion")
    args = parser.parse_args()

    texto = transcribir(args.audio)
    print(texto)
    if args.salida:
        Path(args.salida).write_text(texto + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()