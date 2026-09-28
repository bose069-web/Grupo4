# from google import genai

# # Tu API Key
# client = genai.Client(
#     api_key="AQ.Ab8RN6Ih8IQU4ntgKsMy7JyDUK62qlnfmvfcGVioeXaU84MOjQ"
# )

# prompt = """
# Analiza los siguientes textos.

# 1. Estoy muy contento con el resultado del proyecto.
# 2. La experiencia ha sido terrible y decepcionante.
# 3. Hoy es lunes y tengo una reunión a las 10.
# 4. El equipo hizo un trabajo excelente.
# 5. No me gustó el servicio recibido.

# 6. I am very happy with this product.
# 7. The experience was awful and frustrating.
# 8. Today is a normal working day.
# 9. The team delivered outstanding results.
# 10. I am disappointed with the support.

# Para cada texto indica:

# - Sentimiento (Positivo, Negativo o Neutro)
# - Entidades detectadas
# - Breve explicación

# Organiza la respuesta en una tabla.
# """

# try:
#     response = client.models.generate_content(
#         model="models/gemini-3.8-flash",
#         contents=prompt
#     )

#     print(response.text)

# except Exception as e:
#     print("ERROR:")
#     print(type(e))
#     print(e)














# import time
# from google import genai

# client = genai.Client(
#     api_key="AQ.Ab8RN6Ih8IQU4ntgKsMy7JyDUK62qlnfmvfcGVioeXaU84MOjQ"
# )

# prompt = """
# Analiza los siguientes textos y clasifica su sentimiento.
# """

# max_intentos = 5

# for intento in range(max_intentos):
#     try:
#         response = client.models.generate_content(
#             model="models/gemini-3.8-flash",
#             contents=prompt
#         )

#         print(response.text)
#         break

#     except Exception as e:
#         print(f"Intento {intento + 1} fallido")

#         if intento < max_intentos - 1:
#             print("Reintentando...")
#             time.sleep(10)
#         else:
#             print("Error final:")
#             print(e)















from google import genai

client = genai.Client(
    api_key="AQ.Ab8RN6Ih8IQU4ntgKsMy7JyDUK62qlnfmvfcGVioeXaU84MOjQ"
)

prompt = """
Analiza los siguientes textos y devuelve una tabla con:

- Texto
- Sentimiento (Positivo, Negativo o Neutro)
- Entidades detectadas
- Explicación breve

1. Estoy muy contento con el resultado del proyecto.
2. La experiencia ha sido terrible y decepcionante.
3. Hoy es lunes y tengo una reunión a las 10.
4. El equipo hizo un trabajo excelente.
5. No me gustó el servicio recibido.
6. I am very happy with this product.
7. The experience was awful and frustrating.
8. Today is a normal working day.
9. The team delivered outstanding results.
10. I am disappointed with the support.
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
    r"C:\Users\boubacar.seck.ext\Documents\gemini_proyecto\Reto diario\resultados_sentimiento.txt",
    "w",
    encoding="utf-8"
) as f:
    f.write(response.text)