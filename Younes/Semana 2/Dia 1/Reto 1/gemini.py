import mimetypes
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types

GEMINI_API_KEY = "PEGA_AQUI_TU_CLAVE_NUEVA"


def main() -> int:
	if not GEMINI_API_KEY or GEMINI_API_KEY == "PEGA_AQUI_TU_CLAVE_NUEVA":
		print(
			"Edita GEMINI_API_KEY en el código y pega una clave nueva.",
			file=sys.stderr,
		)
		return 1

	client = genai.Client(api_key=GEMINI_API_KEY)
	model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
	chat = client.chats.create(model=model)
	print('Chat con Gemini listo. Escribe "salir" para terminar.')

	while True:
		try:
			message = input("\nTú (texto o ruta de imagen): ").strip()
		except (EOFError, KeyboardInterrupt):
			print("\nHasta luego.")
			break

		if not message:
			continue
		if message.lower() in {"salir", "exit", "/quit"}:
			print("Hasta luego.")
			break

		image_name = message
		if len(image_name) >= 2 and image_name[0] == image_name[-1] and image_name[0] in {'"', "'"}:
			image_name = image_name[1:-1]
		image_path = Path(image_name)
		mime_type, _ = mimetypes.guess_type(image_path.name)

		if mime_type and mime_type.startswith("image/"):
			if not image_path.is_file():
				print(f"No se encontró la imagen: {image_path}", file=sys.stderr)
				continue
			contents: str | list[str | types.Part] = [
				"Analiza esta imagen y responde de forma útil.",
				types.Part.from_bytes(
					data=image_path.read_bytes(), mime_type=mime_type
				),
			]
		else:
			contents = message

		try:
			response = chat.send_message(contents)
			print(f"Gemini: {response.text or 'No devolvió texto.'}")
		except Exception as error:
			print(f"No se pudo obtener respuesta: {error}", file=sys.stderr)
	return 0


if __name__ == "__main__":
	raise SystemExit(main())
