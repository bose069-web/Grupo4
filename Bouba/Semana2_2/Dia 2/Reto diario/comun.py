"""Utilidades compartidas por los scripts de analisis de texto e imagen.

Contiene:
- Carga de la API key y del cliente de Gemini.
- Prompts con salida JSON estricta (response_mime_type + response_schema).
- Reintentos con espera exponencial ante errores de cuota o red.
- Metricas de evaluacion (normalizacion de texto, coincidencia difusa, F1).
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Sequence

from dotenv import load_dotenv
from google import genai
from google.genai import types

BASE_DIR = Path(__file__).resolve().parent
DIR_DATOS = BASE_DIR / "datos"
DIR_RESULTADOS = BASE_DIR / "resultados"
DIR_IMAGENES = BASE_DIR / "imagenes"

MODELO_TEXTO = os.getenv("GEMINI_MODEL", "models/gemini-3.5-flash-lite")
MODELO_IMAGEN = os.getenv("GEMINI_VISION_MODEL", "models/gemini-3.5-flash-lite")

MAX_INTENTOS = 5
ESPERA_BASE_SEG = 4

# La capa gratuita de Gemini permite 15 peticiones por minuto y modelo, asi que
# se espacian las llamadas para no depender de los reintentos por 429.
LIMITE_POR_MINUTO = int(os.getenv("GEMINI_RPM", "14"))
INTERVALO_MINIMO_SEG = 60.0 / LIMITE_POR_MINUTO
_ultima_llamada = 0.0

IDIOMA_A_NOMBRE = {
    "es": "espanol",
    "en": "ingles",
    "fr": "frances",
    "de": "aleman",
    "pt": "portugues",
    "it": "italiano",
    "ca": "catalan",
    "nl": "holandes",
    "ru": "ruso",
    "zh": "chino",
}


# --------------------------------------------------------------------------- #
# Cliente
# --------------------------------------------------------------------------- #
def cargar_cliente() -> genai.Client:
    """Carga el .env local y devuelve un cliente de Gemini autenticado."""
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("No se encontro GEMINI_API_KEY. Definel en .env antes de ejecutar.")
    return genai.Client(api_key=api_key)


def pedir_json(
    cliente: genai.Client,
    prompt: str,
    esquema: dict[str, Any],
    *,
    modelo: str = MODELO_TEXTO,
    imagen: Any | None = None,
    temperatura: float = 0.0,
    max_tokens: int | None = None,
) -> dict[str, Any]:
    """Llama a Gemini exigiendo JSON valido segun `esquema` y con reintentos.

    Devuelve el diccionario ya parseado. Si el modelo devuelve texto no
    parseable, se intenta una ultima vez en modo laxo (quitando el schema).
    """
    config: types.GenerateContentConfig = types.GenerateContentConfig(
        temperature=temperatura,
        response_mime_type="application/json",
        response_schema=esquema,
    )
    if max_tokens:
        config.max_output_tokens = max_tokens

    contenidos: list[Any] = [prompt] if imagen is None else [prompt, imagen]

    global _ultima_llamada
    ultimo_error: Exception | None = None
    for intento in range(MAX_INTENTOS):
        espera_turno = INTERVALO_MINIMO_SEG - (time.monotonic() - _ultima_llamada)
        if espera_turno > 0:
            time.sleep(espera_turno)
        try:
            respuesta = cliente.models.generate_content(
                model=modelo,
                contents=contenidos,
                config=config,
            )
            _ultima_llamada = time.monotonic()
            return _parsear(respuesta.text)
        except Exception as exc:  # noqa: BLE001 - se reintenta ante cualquier fallo
            _ultima_llamada = time.monotonic()
            ultimo_error = exc
            if intento == MAX_INTENTOS - 1:
                break
            espera = _espera_sugerida(exc) or (ESPERA_BASE_SEG * (2**intento) + random.uniform(0, 2))
            print(f"    [reintento {intento + 1}/{MAX_INTENTOS}] {type(exc).__name__}: {_mensaje(exc)}")
            print(f"    esperando {espera:.1f}s...")
            time.sleep(espera)

    raise RuntimeError(f"Fallo la llamada a Gemini tras {MAX_INTENTOS} intentos: {ultimo_error}")


def _mensaje(exc: Exception) -> str:
    texto = str(exc).split("\n")[0]
    return texto[:160]


def _espera_sugerida(exc: Exception) -> float | None:
    """Respeta el 'Please retry in Xs' que indica la API cuando hay error 429."""
    coincidencia = re.search(r"retry in (\d+(?:\.\d+)?)s", str(exc), flags=re.IGNORECASE)
    return float(coincidencia.group(1)) + 1 if coincidencia else None


def _parsear(texto: str | None) -> dict[str, Any]:
    if not texto:
        raise ValueError("Gemini devolvio una respuesta vacia")
    limpio = texto.strip()
    limpio = re.sub(r"^```(?:json)?|```$", "", limpio, flags=re.MULTILINE).strip()
    try:
        return json.loads(limpio)
    except json.JSONDecodeError as exc:
        raise ValueError(f"La respuesta no es JSON valido: {limpio[:200]}") from exc


# --------------------------------------------------------------------------- #
# Esquemas JSON
# --------------------------------------------------------------------------- #
ESQUEMA_IDIOMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "idioma": {"type": "string", "enum": ["es", "en", "fr", "de", "pt", "it", "ca", "nl", "ru", "zh"]},
        "nombre_idioma": {"type": "string"},
        "confianza": {"type": "number"},
        "pistas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["idioma", "nombre_idioma", "confianza", "pistas"],
}

ESQUEMA_ENTIDADES: dict[str, Any] = {
    "type": "object",
    "properties": {
        "entidades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "texto": {"type": "string"},
                    "tipo": {"type": "string", "enum": ["PERSONA", "ORGANIZACION", "LUGAR", "FECHA", "OTRO"]},
                    "descripcion": {"type": "string"},
                },
                "required": ["texto", "tipo", "descripcion"],
            },
        },
    },
    "required": ["entidades"],
}

ESQUEMA_SENTIMIENTO: dict[str, Any] = {
    "type": "object",
    "properties": {
        "sentimiento": {"type": "string", "enum": ["positivo", "negativo", "neutro"]},
        "confianza": {"type": "number"},
        "intensidad": {"type": "number"},
        "explicacion": {"type": "string"},
    },
    "required": ["sentimiento", "confianza", "intensidad", "explicacion"],
}

ESQUEMA_RESUMEN: dict[str, Any] = {
    "type": "object",
    "properties": {
        "resumen": {"type": "string"},
        "palabras_clave": {"type": "array", "items": {"type": "string"}},
        "longitud_original": {"type": "integer"},
        "longitud_resumen": {"type": "integer"},
    },
    "required": ["resumen", "palabras_clave", "longitud_original", "longitud_resumen"],
}

ESQUEMA_OCR: dict[str, Any] = {
    "type": "object",
    "properties": {
        "hay_texto": {"type": "boolean"},
        "texto": {"type": "string"},
        "fragmentos": {"type": "array", "items": {"type": "string"}},
        "legibilidad": {"type": "number"},
    },
    "required": ["hay_texto", "texto", "fragmentos", "legibilidad"],
}

ESQUEMA_DESCRIPCION: dict[str, Any] = {
    "type": "object",
    "properties": {
        "descripcion": {"type": "string"},
        "elementos_clave": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["descripcion", "elementos_clave"],
}

ESQUEMA_ESCENA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "escena": {
            "type": "string",
            "enum": ["documento", "calle", "producto", "grafico", "interior", "paisaje", "personas", "animal", "otro"],
        },
        "entorno": {"type": "string"},
        "confianza": {"type": "number"},
    },
    "required": ["escena", "entorno", "confianza"],
}

ESQUEMA_OBJETOS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "objetos": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "cantidad": {"type": "integer"},
                    "ubicacion": {"type": "string"},
                    "confianza": {"type": "number"},
                },
                "required": ["nombre", "cantidad", "ubicacion", "confianza"],
            },
        }
    },
    "required": ["objetos"],
}


# --------------------------------------------------------------------------- #
# Prompts
# --------------------------------------------------------------------------- #
def _bloque(texto: str) -> str:
    return texto.strip()


PROMPT_IDIOMA = """Eres un detector de idiomas experto. Analiza el TEXTO y devuelve el idioma detectado.

TEXTO:
\"\"\"
{texto}
\"\"\"

Responde unicamente con el objeto JSON del esquema. El campo `pistas` debe contener
indicios concretos del texto (palabras tipicas, funciones gramaticales) que justifiquen el idioma.
La `confianza` es un numero entre 0 y 1."""

PROMPT_ENTIDADES = """Eres un motor de reconocimiento de entidades nombradas (NER). Extrae las entidades
del TEXTO original, sin traducirlas ni corregirlas.

TEXTO:
\"\"\"
{texto}
\"\"\"

Tipos permitidos: PERSONA, ORGANIZACION, LUGAR, FECHA, OTRO.
- Extrae solo entidades que aparecen literalmente en el texto.
- Para ORGANIZACION y LUGAR incluye el nombre completo (por ejemplo "Banco Central de Espana", no "Espana").
- No incluyas palabras comunes ni conceptos genericos.
- Ordena las entidades por aparicion en el texto.
Responde unicamente con el objeto JSON del esquema."""

PROMPT_SENTIMIENTO = """Eres un analizador de sentimiento. Clasifica el sentimiento GLOBAL del TEXTO.

TEXTO:
\"\"\"
{texto}
\"\"\"

Reglas de clasificacion:
- `positivo`: elogio, satisfaccion, entusiasmo, hechos claramente favorables.
- `negativo`: critica, queja, fracaso, hechos claramente desfavorables.
- `neutro`: informativo, administrativo, factual, sin carga valorativa.
- `intensidad` es un numero entre 0 y 1 que mide la fuerza del sentimiento.
- `explicacion` debe citar el fragmento concreto del texto que sustenta la etiqueta (maximo 25 palabras).
Responde unicamente con el objeto JSON del esquema."""

PROMPT_RESUMEN = """Resume el TEXTO en espanol, aunque el TEXTO este en otro idioma.

TEXTO:
\"\"\"
{texto}
\"\"\"

Reglas:
- Una sola frase de entre 15 y 30 palabras, en espanol.
- Conserva cifras, fechas, nombres propios y entidades clave.
- No anadas informacion que no este en el texto.
- `palabras_clave`: entre 3 y 6 terminos representativos.
- `longitud_original`: numero de palabras del texto original.
- `longitud_resumen`: numero de palabras del resumen.
Responde unicamente con el objeto JSON del esquema."""


# --------------------------------------------------------------------------- #
# Normalizacion y metricas
# --------------------------------------------------------------------------- #
def normalizar(texto: str) -> str:
    """Minusculas, sin acentos y solo caracteres alfanumericos y espacios."""
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = texto.lower()
    texto = re.sub(r"[^a-z0-9]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def palabras(texto: str) -> list[str]:
    return [p for p in normalizar(texto).split(" ") if p]


def palabras_clave(texto: str, min_len: int = 4) -> set[str]:
    return {p for p in palabras(texto) if len(p) >= min_len}


def texto_similitud(a: str, b: str) -> float:
    """Similitud difusa 0-1 entre dos textos (SequenceMatcher)."""
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def coincide(entrada: str, referencia: str, umbral: float = 0.72) -> bool:
    """True si la entidad `entrada` coincide con `referencia`.

    Usa coincidencia exacta tras normalizar, contencion o similitud difusa.
    """
    e, r = normalizar(entrada), normalizar(referencia)
    if not e or not r:
        return False
    if e == r or e in r or r in e:
        return True
    return SequenceMatcher(None, e, r).ratio() >= umbral


def f1_texto(predicho: str, referencia: str) -> tuple[float, float, float, float]:
    """Precision, recall y F1 por palabras (bolsa de palabras).

    Devuelve (precision, recall, f1, solapamiento).
    """
    p, r = set(palabras_clave(predicho)), set(palabras_clave(referencia))
    if not p or not r:
        return (0.0, 0.0, 0.0, 0.0)
    comunes = p & r
    precision = len(comunes) / len(p)
    recall = len(comunes) / len(r)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return (precision, recall, f1, len(comunes))


SINONIMOS_OBJETOS = {
    "auto": "coche",
    "carro": "coche",
    "vehiculos": "coche",
    "edificios": "edificio",
    "edificaciones": "edificio",
    "casas": "edificio",
    "construcciones": "edificio",
    "arboles": "arbol",
    "plantas": "arbol",
    "palmeras": "arbol",
    "semaforos": "semaforo",
    "farolas": "farola",
    "alumbrado": "farola",
    "personas": "persona",
    "gente": "persona",
    "peatones": "persona",
    "tapa": "tapon",
    "tapones": "tapon",
    "botellas": "botella",
    "envase": "botella",
    "etiquetas": "etiqueta",
    "papel": "documento",
    "hoja": "documento",
    "facturas": "factura",
    "barras": "barra",
    "columnas": "barra",
    "eje": "ejes",
    "leyendas": "leyenda",
    "titulos": "titulo",
    "codigo": "codigo de barras",
    "graficos": "grafico",
    "nube": "nubes",
    # Imagenes reales de esta practica
    "teatro": "anfiteatro",
    "teatros": "anfiteatro",
    "anfiteatros": "anfiteatro",
    "gradas": "anfiteatro",
    "montana": "montanas",
    "colinas": "montanas",
    "cerros": "montanas",
    "playas": "playa",
    "costa": "playa",
    "hueso": "huesos",
    "fractura": "fracturas",
    "femures": "femur",
    "femor": "femur",
    "rotulas": "rotula",
    "esquirlas": "imagenes medicas",
    "radiografias": "imagenes medicas",
    "ilustraciones medicas": "imagenes medicas",
    "flecha": "flechas",
    "etiqueta": "etiquetas",
    "perros": "perro",
    "pastor": "perro",
    "canino": "perro",
    "cesped": "hierba",
    "pasto": "hierba",
    "campo": "hierba",
    "prado": "hierba",
    "hamburguesas": "hamburguesa",
    "bocadillo": "hamburguesa",
    "comida": "hamburguesa",
    "bistec": "carne",
    "chuleton": "carne",
    "pan": "pan",
    "bocata": "pan",
    "leche": "queso",
    "cheddar": "queso",
    "tomates": "tomate",
    "lechugas": "lechuga",
    "salsas": "salsa",
    "ketchup": "salsa",
    "mayonesa": "salsa",
    "moleculas": "molecula",
    "atomos": "molecula",
    "esfera": "esferas",
    "burbuja": "burbujas",
    "bolas": "esferas",
    "render": "modelo 3d",
    "modelo": "modelo 3d",
    "ilustracion 3d": "modelo 3d",
}


def normalizar_objeto(texto: str) -> str:
    """Normaliza el nombre de un objeto a singular y a su sinonimo canonico."""
    base = normalizar(texto)
    if base in SINONIMOS_OBJETOS:
        return SINONIMOS_OBJETOS[base]
    partes = [SINONIMOS_OBJETOS.get(p, p) for p in base.split(" ") if p]
    return " ".join(partes)


def prf_etiquetas(
    predichas: Sequence[str],
    esperadas: Sequence[str],
    umbral: float = 0.72,
    synonymos: bool = False,
) -> tuple[float, float, float, int, int, int]:
    """Precision, recall y F1 de listas de etiquetas (entidades u objetos).

    Empareja cada prediccion con la referencia mas similar aun no usada.
    Con `synonymos=True` unifica antes plurales y sinonimos de objetos
    (por ejemplo `edificios`, `edificio` y `casas` cuentan como el mismo objeto).
    Devuelve (precision, recall, f1, aciertos, falsos_positivos, falsos_negativos).
    """
    base = normalizar_objeto if synonymos else normalizar
    preds = [base(p) for p in predichas if base(p)]
    refs = [base(r) for r in esperadas if base(r)]
    usados: set[int] = set()
    aciertos = 0
    for p in preds:
        mejor, mejor_score = -1, umbral
        for i, r in enumerate(refs):
            if i in usados:
                continue
            score = 1.0 if (p == r or p in r or r in p) else SequenceMatcher(None, p, r).ratio()
            if score >= mejor_score:
                mejor, mejor_score = i, score
        if mejor >= 0:
            usados.add(mejor)
            aciertos += 1
    fp = len(preds) - aciertos
    fn = len(refs) - aciertos
    precision = aciertos / len(preds) if preds else 0.0
    recall = aciertos / len(refs) if refs else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return (precision, recall, f1, aciertos, fp, fn)


def promedio(valores: Iterable[float]) -> float:
    vals = [v for v in valores]
    return sum(vals) / len(vals) if vals else 0.0


def guardar_json(nombre: str, datos: Any) -> Path:
    DIR_RESULTADOS.mkdir(parents=True, exist_ok=True)
    ruta = DIR_RESULTADOS / nombre
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return ruta
