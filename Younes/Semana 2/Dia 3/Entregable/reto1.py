import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from google import genai
from google.genai import types


GEMINI_API_KEY = ""
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
MAX_AUDIO_BYTES = 25 * 1024 * 1024


class LocalHTTPServer(ThreadingHTTPServer):
	allow_reuse_address = False


class TranscriptionHandler(BaseHTTPRequestHandler):
	def do_GET(self) -> None:
		if self.path != "/health":
			self.send_error(404)
			return
		self._send_json(200, {"status": "ok"})

	def do_POST(self) -> None:
		if self.path != "/transcribe":
			self.send_error(404)
			return

		if not GEMINI_API_KEY:
			self._send_json(400, {"error": "Pega tu clave en GEMINI_API_KEY al principio de reto1.py."})
			return

		try:
			content_length = int(self.headers.get("Content-Length", "0"))
		except ValueError:
			self._send_json(400, {"error": "No se pudo leer el tamaño del audio."})
			return

		if content_length <= 0 or content_length > MAX_AUDIO_BYTES:
			self._send_json(400, {"error": "El audio está vacío o supera el límite de 25 MB."})
			return

		audio_bytes = self.rfile.read(content_length)
		if len(audio_bytes) != content_length:
			self._send_json(400, {"error": "La recepción del audio quedó incompleta."})
			return

		try:
			client = genai.Client(api_key=GEMINI_API_KEY)
			response = client.models.generate_content(
				model=GEMINI_MODEL,
				contents=[
					"Transcribe literalmente en español el audio adjunto. "
					"Conserva las palabras tal como se dicen y añade puntuación. "
					"Devuelve únicamente la transcripción, sin comentarios.",
					types.Part.from_bytes(data=audio_bytes, mime_type="audio/wav"),
				],
			)
			transcription = (response.text or "").strip()
			if not transcription:
				self._send_json(502, {"error": "Gemini no devolvió una transcripción."})
				return
			self._send_json(200, {"transcription": transcription, "model": GEMINI_MODEL})
		except Exception as error:
			self._send_json(502, {"error": f"Gemini no pudo transcribir el audio: {error}"})

	def _send_json(self, status: int, payload: dict[str, str]) -> None:
		body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
		self.send_response(status)
		self.send_header("Content-Type", "application/json; charset=utf-8")
		self.send_header("Content-Length", str(len(body)))
		self.end_headers()
		self.wfile.write(body)

	def log_message(self, format_string: str, *args: object) -> None:
		print(f"{self.address_string()} - {format_string % args}")


def main() -> None:
	port = int(os.getenv("GEMINI_SERVER_PORT", "8000"))
	server = LocalHTTPServer(("127.0.0.1", port), TranscriptionHandler)
	print(f"API Gemini disponible en http://127.0.0.1:{port}. Pulsa Ctrl+C para cerrar.")
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		print("\nServidor cerrado.")
	finally:
		server.server_close()


if __name__ == "__main__":
	main()
