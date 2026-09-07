
def get_completion(prompt, model="gpt-3.5-turbo"):
    messages = [{"role": "user", "content": prompt}]
    response = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=0,
    ) 
    return response.choices[0].message["content"]


Prompt 1 

text = f"""
A = 1
B = 2
"""
prompt = f"""
Suma A y B
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1: La suma de A y B es 3.

Respuesta IA 2:  3

Prompt 2

text = f"""
A = 1
B = 2
Contexto: A y B representan el número de manzanas que tienen dos amigos.
"""
prompt = f"""
Suma A y B y di cuántas manzanas tienen entre los dos
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1: La suma de A y B es 3. Por lo tanto, entre los dos amigos tienen 3 manzanas.

Respuesta IA 2: Entre los dos amigos tienen 3 manzanas.

Prompt 3 

text = f"""
A = 1
B = 2
C = 3
D = 4
E = 5
F = 6
G = 7
"""
prompt = f"""
Suma únicamente los valores cuyo resultado sea un número par.
No expliques el proceso, entrega solo el resultado final.
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1: 12

Respuesta IA 2: 12

Prompt 4

text = f"""
A = 1
B = 2
C = 3
D = 4
"""
prompt = f"""
Actúa como un profesor de matemáticas de primaria.
Explica de forma sencilla cómo sumar A, B, C y D, como si se lo explicaras a un niño de 8 años.
```{text}```
"""

response = get_completion(prompt)
print(response)

Respuesta IA 1:
Hola niños, hoy vamos a aprender a sumar los números A, B, C y D. 

Primero vamos a sumar A y B. A es igual a 1 y B es igual a 2. Si sumamos 1 + 2, obtenemos 3. 

Ahora vamos a sumar C y D. C es igual a 3 y D es igual a 4. Si sumamos 3 + 4, obtenemos 7. 

Por último, vamos a sumar los resultados de las dos sumas anteriores. Sumamos 3 (A + B) + 7 (C + D) y obtenemos 10. 

Entonces, la suma de A, B, C y D es igual a 10. ¡Muy bien hecho!
Respuesta IA 2:
Expected output would use simple language, analogies (like counting apples), and step-by-step explanation to reach 10.

Prompt 5 

text = f"""
A = 1
B = 2
C = 3
D = 4
E = 5
"""
prompt = f"""
Actúa como un profesor de matemáticas.
Un alumno confundió la suma de A, B, C, D y E y llegó a un resultado incorrecto.
Resuelve el ejercicio paso a paso, mostrando cada operación por separado.
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1:

text = f"""
A = 1
B = 2
C = 3
D = 4
E = 5
"""
prompt = f"""
Actúa como un profesor de matemáticas.
Un alumno confundió la suma de A, B, C, D y E y llegó a un resultado incorrecto.
Resuelve el ejercicio paso a paso, mostrando cada operación por separado.
```{text}```
"""
response = get_completion(prompt)
print(response)
​
Para resolver la suma de A, B, C, D y E, primero sumamos los valores de cada variable por separado:

A = 1
B = 2
C = 3
D = 4
E = 5

1 + 2 = 3
3 + 3 = 6
6 + 4 = 10
10 + 5 = 15

Por lo tanto, la suma correcta de A, B, C, D y E es 15. El alumno que llegó a un resultado incorrecto probablemente cometió un error en alguna de las operaciones de suma. Es importante revisar cada paso con cuidado para evitar confusiones.
Respuesta IA 2:
A + B = 1 + 2 = 3
3 + C = 3 + 3 = 6
6 + D = 6 + 4 = 10
10 + E = 10 + 5 = 15
Prompt 6 

text = f"""
A = 1
B = 2
C = 3
D = 4
"""
prompt = f"""
Actúa como un asistente de datos.
Para cada letra, genera una palabra que empiece por esa letra y tenga tantas letras como su valor.
Devuelve el resultado como una lista, un elemento por línea.
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1:
A: apple
B: banana
C: carrot
D: dance
Respuesta IA 2:
A (1 letter): "A"
B (2 letters): "Be"
C (3 letters): "Cat"
D (4 letters): "Door"
Prompt 7 

text = f"""
A = 1
B = 2
C = 3
D = 4
E = 5
"""
prompt = f"""
Actúa como un analista de datos.
Organiza la información en una tabla con columnas: Letra, Valor, Par o Impar.
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1:
| Letra | Valor | Par o Impar |
|-------|-------|-------------|
| A     | 1     | Impar       |
| B     | 2     | Par         |
| C     | 3     | Impar       |
| D     | 4     | Par         |
| E     | 5     | Impar       |
Respuesta IA 2:
| Letra | Valor | Par o Impar |
|-------|-------|-------------|
| A     | 1     | Impar       |
| B     | 2     | Par         |
| C     | 3     | Impar       |
| D     | 4     | Par         |
| E     | 5     | Impar       |
Prompt 8 

text = f"""
A = 1
B = 2
C = 3
D = 4
"""
prompt = f"""
Actúa como un generador de datos estructurados.
Convierte la siguiente información en un JSON con esta estructura exacta:
{{"letra": str, "valor": int, "es_par": bool}}
Devuelve solo el JSON, sin texto adicional.
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1:
{
  "letra": "A",
  "valor": 1,
  "es_par": false
}
{
  "letra": "B",
  "valor": 2,
  "es_par": true
}
{
  "letra": "C",
  "valor": 3,
  "es_par": false
}
{
  "letra": "D",
  "valor": 4,
  "es_par": true
}
Respuesta IA 2:

Prompt 9 

text = f"""
A = 1
B = 2
C = 3
"""
prompt = f"""
Actúa como un generador de datos estructurados.
Ejemplo de formato esperado:
{{"letra": "Z", "valor": 26, "es_par": true}}

Ahora convierte los siguientes datos al mismo formato, dentro de un array JSON:
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1:
[
    {"letra": "A", "valor": 1, "es_par": false},
    {"letra": "B", "valor": 2, "es_par": true},
    {"letra": "C", "valor": 3, "es_par": false}
]
Respuesta IA 2:
[
  {"letra": "A", "valor": 1, "es_par": false},
  {"letra": "B", "valor": 2, "es_par": true},
  {"letra": "C", "valor": 3, "es_par": false},
  {"letra": "D", "valor": 4, "es_par": true}
]
Prompt 10

text = f"""
A = 1
B = 2
C = 3
D = 4
"""
prompt = f"""
Actúa como un asistente educativo que ayuda a niños a aprender matemáticas.
Ejemplo de formato esperado:
{{"letra": "Z", "valor": 26, "explicacion": "26 es un número par"}}

Instrucciones:
- Convierte los siguientes datos al mismo formato, dentro de un array JSON.
- La explicación debe tener un tono amable y motivador, dirigido a un niño.
- Cada explicación debe tener máximo 15 palabras.
- No agregues texto fuera del JSON.
```{text}```
"""
response = get_completion(prompt)
print(response)

Respuesta IA 1:
[
    {"letra": "A", "valor": 1, "explicacion": "¡Bien hecho! 1 es el primer número."},
    {"letra": "B", "valor": 2, "explicacion": "¡Muy bien! 2 es un número par."},
    {"letra": "C", "valor": 3, "explicacion": "¡Excelente! 3 es impar y primo."},
    {"letra": "D", "valor": 4, "explicacion": "¡Sigue así! 4 es divisible por 2."}
]
Respuesta IA 2:
[
  {"letra": "A", "valor": 1, "explicacion": "¡El número 1 es especial y único!"},
  {"letra": "B", "valor": 2, "explicacion": "¡El 2 es un número par, muy bien!"},
  {"letra": "C", "valor": 3, "explicacion": "¡El 3 es un número impar, genial!"},
  {"letra": "D", "valor": 4, "explicacion": "¡El 4 es par, excelente trabajo!"}
]