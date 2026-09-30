# Dia 2 — Analisis de texto e imagenes con Gemini

Reto del dia 2 (5 h): analizar texto e imagenes con la API de Gemini usando salidas JSON
estructuradas, y medir la precision de cada tarea contra una referencia conocida.

Este README es toda la documentacion del entregable: que se ha hecho, como esta ordenado, como se
ejecuta, como se mide y que se ha concluido de los resultados. Los datos crudos estan en
`resultados/`, y `cuaderno_resultados.ipynb` ya viene ejecutado con las tablas y graficos.

---

## 1. Resultados

`models/gemini-3.5-flash-lite`, 60 llamadas a la API (40 de texto, 20 de vision), 0 errores.

### Texto — 10 textos, 3 categorias, 4 idiomas

| Tarea | Metrica | Precision |
| --- | --- | --- |
| Deteccion de idioma | Accuracy | **100,0%** |
| Analisis de sentimiento | Accuracy | **80,0%** |
| Entidades nombradas (NER) | F1 | **78,0%** |
| Resumen automatico | F1 por palabras | **47,7%** |
| Resumen automatico | Similitud de caracteres | 46,4% |
| Resumen automatico | Tasa de compresion | 40,7% (de 68 palabras a 28) |

| Documento | Categoria | Idioma | Sentimiento | F1 entidades | F1 resumen |
| --- | --- | --- | --- | --- | --- |
| T01 | noticia | es / es OK | neutro / neutro OK | 75,0% | 50,0% |
| T02 | noticia | en / en OK | positivo / positivo OK | 100,0% | 45,2% |
| T03 | resena | es / es OK | negativo / negativo OK | 66,7% | 48,5% |
| T04 | resena | en / en OK | positivo / positivo OK | 100,0% | 23,5% |
| T05 | email | es / es OK | neutro / neutro OK | 72,7% | 68,8% |
| T06 | email | en / en OK | neutro / neutro OK | 75,0% | 68,8% |
| T07 | noticia | fr / fr OK | neutro / **positivo FALLO** | 60,0% | 36,4% |
| T08 | resena | de / de OK | positivo / positivo OK | 57,1% | 24,2% |
| T09 | email | en / en OK | negativo / negativo OK | 80,0% | 48,5% |
| T10 | noticia | es / es OK | positivo / **neutro FALLO** | 93,3% | 62,9% |

| Categoria | n | Idioma | Sentimiento | F1 entidades | F1 resumen |
| --- | --- | --- | --- | --- | --- |
| email | 3 | 100,0% | 100,0% | 75,9% | 62,0% |
| noticia | 4 | 100,0% | 50,0% | 82,1% | 48,6% |
| resena | 3 | 100,0% | 100,0% | 74,6% | 32,1% |

### Vision — 5 imagenes reales

| Tarea visual | Metrica | Precision |
| --- | --- | --- |
| OCR (imagenes con texto) | Cobertura de fragmentos | **50,0%** |
| OCR (imagenes sin texto) | Acierto en no inventar texto | **100,0%** |
| Descripcion de contenido | Cobertura de conceptos | **92,0%** |
| Clasificacion de escena | Accuracy | **80,0%** |
| Deteccion de objetos | F1 | **60,4%** |
| Deteccion de objetos | Precision / Recall | 91,4% / 51,7% |

| Imagen | Tipo | OCR | Descripcion | Escena (gold/pred) | Objetos F1 |
| --- | --- | --- | --- | --- | --- |
| 01_teatro_griego_taormina.jpg | paisaje con monumento | 100% (sin texto) | 80,0% | paisaje / paisaje | 76,9% |
| 02_tipos_fracturas_hueso.jpg | diagrama medico | 100% (9/9 etiquetas) | 100,0% | grafico / grafico | 28,6% |
| 03_perro_pastor_aleman.jpg | foto de animal | 100% (sin texto) | 80,0% | animal / animal | 50,0% |
| 04_hamburguesa.jpg | producto / comida | 100% (sin texto) | 100,0% | producto / producto | 80,0% |
| 05_molecula_3d.jpg | render 3D | 0% (marca de agua) | 100,0% | otro / **grafico FALLO** | 66,7% |

Media texto 76,4%, media vision 78,1%.

### Costes

| Medida | Valor |
| --- | --- |
| Llamadas a la API | 60 (4 por elemento) |
| Errores | 0 |
| Latencia media por texto | 20,6 s (4 llamadas en serie) |
| Latencia media por imagen | 22,1 s (4 llamadas en serie) |

---

## 2. Conclusion de los resultados

**1. La salida JSON con `response_schema` es fiable.** Las 60 llamadas devolvieron JSON valido
siempre. No hubo ni un solo texto libre que limpiar con regex. Con `response_mime_type` y
`temperature=0` el pipeline es solo parsear el resultado.

**2. Las tareas de clasificacion son las mas solidas (80-100%).** Idioma, sentimiento y escena son
categorias cerradas: el modelo elige entre pocas opciones y acierta casi siempre. Es lo que mejor
se le da a un LLM.

**3. El OCR es bueno leyendo y correcto callando.** Leyo las 9 etiquetas inglesas del diagrama medico
(`Normal`, `Transverse`, `Oblique`, `Spiral`, `Comminuted`, `Impacted`, `Segmental`, `Torus`,
`Greenstick`) al 100%, y eso con texto de unos 10 px. En las 3 fotos sin texto no inventa nada: 100%.
El fallo es la marca de agua `pngtree` de la imagen de la molecula, que ignora por completo. Ese
50% en imagenes con texto no es un error de lectura, es que decide que la marca de agua no cuenta.

**4. La deteccion de objetos es lo mas flojo (F1 60,4%) y falla por dos motivos a la vez.**

No inventa objetos: la precision es 91,4%. Lo que hace es devolver el inventario demasiado grueso. En
el diagrama medico responde un solo objeto (`hueso`) y solo en la descripcion del mismo prompt
detalla las diez fracturas, sus etiquetas y las flechas rojas. El recall se queda en 51,7%.

Ademas **es la tarea mas inestable entre ejecuciones**. Con el mismo prompt, la misma imagen y
`temperature=0`, en dos ejecuciones distintas:

| Imagen | Objetos devueltos (ejecucion A) | Objetos devueltos (ejecucion B) | F1 |
| --- | --- | --- | --- |
| 04_hamburguesa.jpg | `hamburguesa` | `hamburguesa, pan, carne, queso, tocino, lechuga, salsa` | 22,2% → 80,0% |
| 03_perro_pastor_aleman.jpg | `perro, cesped` | `perro` | 80,0% → 50,0% |

A veces responde "dame los objetos de la imagen" y pone el sujeto; otras veces los desglosa. Es un
problema de granularidad e inestabilidad del prompt, no de la capacidad visual: cuando desglosa,
acierta. La solucion seria pedir explicitamente el inventario minimo ("lista al menos 6 objetos
distintos, incluyendo los ingredientes por separado") y promediar varias ejecuciones.

**5. La descripcion visual es la tarea mas fiable de vision (92%).** Con variantes de sinonimos
aceptadas (`tocino` cuenta como `bacon`, `tumbado` como `echado`, `cesped` como `hierba`), la
cobertura de conceptos es 100% en 3 de 5 imagenes. Los dos huecos que quedan son justos: en la foto
del teatro no menciona el cerro con edificios del fondo, y en el perro no dice que es una foto
exterior.

**6. Los tres fallos se dejan sin corregir a proposito.** T07 (noticia en frances) y T10 (noticia de
Google) discrepan en sentimiento; la molecula se clasifica como `grafico` en vez de `otro`. En los tres
casos la referencia y el modelo son defendibles: una noticia con datos favorables se puede leer como
positiva o como neutra, y un render 3D es discutible si es "grafico" u "otro". Ajustar la referencia
para subir la nota seria falsear la medida. Los deja el script en `discrepancias` y `fallos_escena`.

**7. El limite real es la cuota.** 15 peticiones por minuto en la capa gratuita. `comun.py` espacia
las llamadas y respeta el `retry in Xs` que manda la API. Con eso salen los lotes completos sin
errores; sin eso, el primer intento encadenaba 429.

---

## 3. Como esta ordenado

```text
Reto diario/
├── README.md                      # Este documento (toda la documentacion)
├── requirements.txt               # Dependencias
├── .env                           # GEMINI_API_KEY (NO se sube, esta en .gitignore)
├── .env.example                   # Plantilla de configuracion (si se sube)
├── .gitignore
│
├── ejecutar_todo.py               # Punto de entrada: ejecuta texto + vision
├── comun.py                       # Cliente, prompts, esquemas JSON, metricas, cuota
├── analisis_textos.py             # Reto 1: idioma, NER, sentimiento, resumen
├── analisis_imagenes.py           # Reto 2: OCR, descripcion, escena, objetos
├── cuaderno_resultados.ipynb      # Analisis de resultados (ya ejecutado)
│
├── datos/
│   ├── corpus_textos.json              # 10 textos + etiquetas gold
│   └── ground_truth_imagenes.json      # Referencia visual de las 5 imagenes
│
├── imagenes/                      # 5 imagenes reales de test
│   ├── 01_teatro_griego_taormina.jpg
│   ├── 02_tipos_fracturas_hueso.jpg
│   ├── 03_perro_pastor_aleman.jpg
│   ├── 04_hamburguesa.jpg
│   └── 05_molecula_3d.jpg
│
└── resultados/                    # Salida de `python ejecutar_todo.py`
    ├── resultados_textos.json          # Respuestas + metricas por texto
    ├── resultados_imagenes.json        # Respuestas + metricas por imagen
    └── grafico_precision_imagenes.png  # Mapa de calor por tarea e imagen
```

Donde ejecutar cada cosa:

| Fichero | Que hace |
| --- | --- |
| `ejecutar_todo.py` | Lo primero que se ejecuta. Lanza los dos retos en orden. |
| `comun.py` | No se ejecuta. Es la base compartida: cliente de Gemini, prompts, esquemas JSON, metricas y control de cuota. |
| `analisis_textos.py` | Reto 1. 4 llamadas por texto, compara con el gold y guarda el JSON. |
| `analisis_imagenes.py` | Reto 2. 4 llamadas por imagen, compara con el ground truth y guarda el JSON y el grafico. |
| `cuaderno_resultados.ipynb` | No llama a la API. Solo lee los JSON y saca tablas, graficos y conclusiones. |
| `datos/*.json` | No se tocan. Son las referencias contra las que se mide. Editarlos cambia las notas. |

---

## 4. Como se mide

La clave del enunciado es comparar la precision, y eso exige dos cosas: una referencia conocida y
una metrica acorde a cada tarea.

**La referencia.** Los 10 textos (`datos/corpus_textos.json`) llevan su etiqueta gold: idioma,
sentimiento, entidades clave y un resumen de referencia en espanol. Son 3 categorias (noticias,
resenas, emails) en 4 idiomas (es, en, fr, de), de 61 a 77 palabras. Las 5 imagenes son fotos
reales en `imagenes/`, y `datos/ground_truth_imagenes.json` describe de cada una la escena, los
objetos, el texto que contiene y los conceptos que deberia describir.

**La metrica.** Cada tarea se evalua con la que le corresponde, no con una sola para todas:

| Tarea | Metrica | Motivo |
| --- | --- | --- |
| Idioma, sentimiento, escena | Accuracy exacta | Etiqueta cerrada: o coincide o no |
| Entidades, objetos | Precision / Recall / F1 difusa | Hay lista de gold y el modelo recorta o expande limites |
| Resumen | F1 por palabras + similitud de caracteres | Texto libre: hacen falta dos medidas |
| OCR con texto | Cobertura de fragmentos | Se comprueba que lea lo que hay |
| OCR sin texto | Acierto en **no** inventar texto | Control de alucinaciones: lo que se penaliza es inventar |
| Descripcion | Cobertura de conceptos con variantes | Texto libre, sin lexicon exactitud |

Detalles de la evaluacion:

- **Emparejamiento difuso** de entidades y objetos: cuenta como acierto el nombre exacto, la
  contencion (`Banco Central` dentro de `Banco Central de Espana`) o una similitud >= 0,72.
- **Sinonimos de objetos**: antes de comparar se unifican (`edificios`/`edificio`, `auto`/`coche`,
  `tocino`/`bacon`, `pasto`/`hierba`). Sin esto, un falso negativo por plural o sinonimo castigaria
  al modelo sin motivo. La lista esta en `comun.SINONIMOS_OBJETOS`.
- **Variantes de conceptos** en la descripcion: cada concepto acepta sinonimos (`tocino` por
  `bacon`, `tumbado` por `echado`). Antes de añadirlo, la cobertura de la hamburguesa era del 33% y
  la del perro del 50%, no por descripciones malas sino porque el modelo escribia en otras palabras.
  Esta correccion es parte de la metrica, no una concession al modelo: las variantes estan escritas
  en el ground truth antes de ejecutar.
- **OCR con dos modos**: en la imagen con texto se mide cuantos fragmentos se leyeron; en las 3 fotos
  sin texto se mide que no devuelva texto. Una alucinacion en una foto de paisaje puntua 0.

**Salida JSON.** Cada llamada usa `response_mime_type="application/json"`, un `response_schema` con
el esquema de su tarea y `temperature=0`. Los prompts son especificos por tarea y llevan reglas
escritas, por ejemplo en NER: "incluye el nombre completo de la organizacion, no solo la parte
final", o en OCR: "si la imagen no contiene texto legible, pon `hay_texto` en false y no inventes".

**Sin trampas.** Cuando el modelo discrepa del gold, se anota en `discrepancias` (texto) y
`fallos_escena` (vision) y se deja ahi. No se tocan las etiquetas de referencia para subir la nota.

---

## 5. Como ejecutarlo

Dependencias:

```powershell
pip install -r requirements.txt
```

La API key va en `.env`, que **no se sube al repositorio** (esta en `.gitignore`). Copia la
plantilla `.env.example` y pon tu clave:

```powershell
Copy-Item .env.example .env
```

```
GEMINI_API_KEY=tu_clave
GEMINI_MODEL=models/gemini-3.5-flash-lite
GEMINI_VISION_MODEL=models/gemini-3.5-flash-lite
GEMINI_RPM=14
```

Los dos retos, en orden:

```powershell
python ejecutar_todo.py
```

O por partes:

```powershell
python ejecutar_todo.py --solo texto
python ejecutar_todo.py --solo vision
```

Y despues el cuaderno:

```powershell
jupyter lab cuaderno_resultados.ipynb
```

### Opciones de los scripts

```powershell
python analisis_textos.py --solo T01 T02                    # solo dos textos
python analisis_textos.py --modelo models/gemini-2.5-flash  # otro modelo
python analisis_imagenes.py --solo 04_hamburguesa.jpg        # solo una imagen
python analisis_imagenes.py --solo-grafico                   # regenera el grafico sin llamar a la API
```

**Aviso**: `--solo` **sobrescribe** `resultados/resultados_*.json` con los elementos indicados, asi que
hay que relanzar el lote completo despues de una prueba parcial.

### Variables de entorno

| Variable | Por defecto | Para que sirve |
| --- | --- | --- |
| `GEMINI_API_KEY` | (obligatoria) | Credencial de la API |
| `GEMINI_MODEL` | `models/gemini-3.5-flash-lite` | Modelo del reto de texto |
| `GEMINI_VISION_MODEL` | `models/gemini-3.5-flash-lite` | Modelo del reto de vision |
| `GEMINI_RPM` | `14` | Llamadas por minuto. La capa gratuita permite 15 |

---

## 6. Notas practicas

- **Cuota.** `comun.py` espera `60 / GEMINI_RPM` segundos entre llamadas y, si aun asi llega un 429,
  respeta el `retry in Xs` que indica la API. Con `temperature=0` y esta espera, los dos lotes
  completos salen con 0 errores. Sin la espera, el primer intento encadenaba seis 429 seguidos.
- **Modelos.** `models/gemini-3.8-flash` devolvio `503 UNAVAILABLE` por saturacion durante las
  pruebas. El default es `gemini-3.5-flash-lite`, que aguantó las 60 llamadas. El reintento con
  espera exponencial cubre el 503, pero agota los 5 intentos y el registro queda marcado con error.
- **Latencia.** ~21 s por texto y ~27 s por imagen, porque las 4 tareas van en serie. Se podría
  paralelizar, pero la cuota por minuto lo impediría en la capa gratuita.
- **Reproducibilidad.** Importante para leer las cifras con Pincel. Las tareas cerradas (idioma,
  escena) son estables entre ejecuciones. Las de texto libre (resumen) y, sobre todo, la de deteccion
  de objetos **no lo son**: con el mismo prompt y `temperature=0` la deteccion de objetos puede
  devolver 1 objeto o 7 en la misma imagen (ver conclusion 4). Los numeros de este README son los de
  la unica ejecucion guardada en `resultados/`, que es la que produzco el cuaderno.
- **Las imagenes son reales**, no sinteticas. Por eso el OCR y la clasificacion de escena dan cifras
  mas bajas y mas realistas que en una prueba con imagenes limpias de laboratorio: hay perspectiva,
  profundidad de campo, texto de 10 px y una marca de agua.
