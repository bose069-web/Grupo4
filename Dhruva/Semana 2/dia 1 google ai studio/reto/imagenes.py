from google import genai
from PIL import Image
 
client = genai.Client(
    api_key="AQ.Ab8RN6IJ16DKQ4DALK5gAmB2bTnoQbntl0Nt2ST4lIk28JawDQ"
)
 
try:
    imagen = Image.open("C:\\Users\\dhruva.pankajkumar.e\\Documents\\gemeni proyecto\\sem2\\d1\\reto\\imagen.jpg")
 
    response = client.models.generate_content(
        model="models/gemini-3.5-flash-lite",
        contents=[
            "Describe detalladamente esta imagen.",
            imagen
        ]
    )
 
    print(response.text)
 
 
    print("C:\\Users\\dhruva.pankajkumar.e\\Documents\\gemeni proyecto\\sem2\\d1\\reto\\Resultado guardado en resultado_imagen.txt")
 
except Exception as e:
    print("ERROR:")
    print(e)

with open(
    r"C:\Users\dhruva.pankajkumar.e\Documents\gemeni proyecto\sem2\d1\reto\resultado_imagen.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write(response.text)