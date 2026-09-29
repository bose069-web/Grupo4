"""API Flask para transcribir audios con Gemini."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from flask import Flask, jsonify, request, send_from_directory

from transcribir_audio import transcribir


BASE_DIR = Path(__file__).resolve().parent
EXTENSIONES_PERMITIDAS = {".wav", ".mp3", ".m4a", ".ogg", ".flac", ".webm"}
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")


@app.get("/")
def inicio():
    return send_from_directory(BASE_DIR, "index.html")


@app.post("/transcribir")
def endpoint_transcribir():
    audio = request.files.get("audio")
    if audio is None or not audio.filename:
        return jsonify(error="Adjunta un archivo en el campo 'audio'."), 400

    extension = Path(audio.filename).suffix.lower()
    if extension not in EXTENSIONES_PERMITIDAS:
        permitidas = ", ".join(sorted(EXTENSIONES_PERMITIDAS))
        return jsonify(error=f"Formato no permitido. Usa: {permitidas}"), 415

    try:
        with NamedTemporaryFile(suffix=extension, delete=False) as temporal:
            audio.save(temporal)
            ruta_temporal = temporal.name
        texto = transcribir(ruta_temporal)
        return jsonify(transcripcion=texto)
    except RuntimeError as error:
        return jsonify(error=str(error)), 500
    except Exception:
        app.logger.exception("Error al transcribir el audio")
        return jsonify(error="Gemini no pudo procesar el audio."), 502
    finally:
        if "ruta_temporal" in locals():
            Path(ruta_temporal).unlink(missing_ok=True)


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)