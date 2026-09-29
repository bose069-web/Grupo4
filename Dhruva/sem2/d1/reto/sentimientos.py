from google import genai
 
client = genai.Client(
    api_key="AQ.Ab8RN6IJ16DKQ4DALK5gAmB2bTnoQbntl0Nt2ST4lIk28JawDQ"
)
 
prompt = """
Analiza los siguientes textos y devuelve una tabla con:
 
- Texto
- Sentimiento (Positivo, Negativo o Neutro)
- Entidades detectadas
- Explicación breve
 
# Español
"Me encanta Madrid y estoy muy contento con el viaje.",
"El servicio de esta empresa ha sido horrible.",
"Microsoft presentó un nuevo producto en Madrid.",
"Estoy muy satisfecho con mi nuevo ordenador Lenovo.",
"El retraso del vuelo de Iberia ha sido frustrante.",
 
# Inglés
"I love visiting London during the summer.",
"The customer service at Amazon was terrible.",
"Microsoft announced a new product in Seattle.",
"My new Lenovo laptop works perfectly.",
"The flight delay at Heathrow was disappointing."
"""
 
try:
    response = client.models.generate_content(
        model="models/gemini-3.5-flash-lite",
        contents=prompt
    )
 
    print(response.text)
   
 
except Exception as e:
    print("ERROR:")
    print(e)
 
with open(
    r"C:\Users\dhruva.pankajkumar.e\Documents\gemeni proyecto\sem2\d1\reto\sentiminetos.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write(response.text)
 