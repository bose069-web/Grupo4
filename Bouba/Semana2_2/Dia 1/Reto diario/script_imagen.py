from google import genai
from PIL import Image

client = genai.Client(
    api_key="AQ.Ab8RN6Ih8IQU4ntgKsMy7JyDUK62qlnfmvfcGVioeXaU84MOjQ"
)

try:
    imagen = Image.open("imagen.jpg")

    response = client.models.generate_content(
        model="models/gemini-3.5-flash-lite",
        contents=[
            "Describe detalladamente esta imagen.",
            imagen
        ]
    )

    print(response.text)

    with open("resultado_imagen.txt", "w", encoding="utf-8") as f:
        f.write(response.text)

    print("\nResultado guardado en resultado_imagen.txt")

except Exception as e:
    print("ERROR:")
    print(e)