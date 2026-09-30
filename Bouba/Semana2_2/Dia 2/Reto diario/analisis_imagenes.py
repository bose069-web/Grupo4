"""Reto del dia 2 (VISION): analisis de imagenes con las capacidades multimodales de Gemini.

Pipeline por cada imagen (4 llamadas, cada una con salida JSON estricta):
  1. OCR: extraccion del texto de la imagen
  2. Descripcion del contenido visual
  3. Clasificacion de la escena
  4. Deteccion de objetos

Los resultados se comparan con la referencia de `datos/ground_truth_imagenes.json`.

Uso:
    python analisis_imagenes.py
    python analisis_imagenes.py --modelo models/gemini-2.5-flash
    python analisis_imagenes.py --solo 04_hamburguesa.jpg
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

import comun as C

RUTA_GT = C.DIR_DATOS / "ground_truth_imagenes.json"
NOMBRE_RESULTADO = "resultados_imagenes.json"

TAREAS = ("ocr", "descripcion", "escena", "objetos")


def construir_prompts(nombre: str) -> dict[str, str]:
    return {
        "ocr": f"""Eres un motor de OCR aplicado a la imagen "{nombre}".

Primero decide si la imagen contiene texto legible:
- Si NO hay texto (por ejemplo una foto de un paisaje, un animal o un producto sin etiqueta),
  pon `hay_texto` en false, deja `texto` y `fragmentos` vacios y `legibilidad` en 0.
- Si hay texto, pon `hay_texto` en true, transcribe literalmente en `texto` respetando el idioma
  original y pon en `fragmentos` las palabras o etiquetas sueltas que se leen.
`legibilidad` es un numero entre 0 y 1 segun la nitidez.

No inventes texto que no se ve y no describas la imagen.
Responde unicamente con el objeto JSON del esquema.""",
        "descripcion": f"""Describe el contenido visual de la imagen "{nombre}" en espanol.
Incluye: tipo de imagen, elementos principales, colores dominante, composicion y,
si aparecen, textos relevantes.
Redacta entre 30 y 60 palabras. En `elementos_clave` lista entre 4 y 8 conceptos sueltos
que describen lo esencial de la imagen.
Responde unicamente con el objeto JSON del esquema.""",
        "escena": f"""Clasifica la escena de la imagen "{nombre}" en UNA sola categoria de esta lista:
- documento: hoja, informe, factura, texto impreso o escaneado.
- calle: via urbana, edificios, perdidas, trafico.
- producto: objeto aislado o sujeto de catalogo, comida o ecommerce.
- grafico: grafico de datos, diagrama, tabla o infografia.
- interior: espacio interior cerrado (casa, oficina, tienda).
- paisaje: naturaleza, costa, campo, montana o monumento al aire libre.
- personas: retrato o grupo de personas como sujeto principal.
- animal: un animal como sujeto principal.
- otro: no encaja en ninguna.
Responde unicamente con el objeto JSON del esquema.""",
        "objetos": f"""Detecta los objetos visibles en la imagen "{nombre}".
Para cada objeto indica su nombre en espanol (en singular), la cantidad aproximada
y donde se encuentra en la imagen (por ejemplo "centro", "izquierda", "arriba a la derecha").
Ordena los objetos del mas prominente al menos visible.
Responde unicamente con el objeto JSON del esquema.""",
    }


def analizar_imagen(cliente, ruta: Path, nombre: str, modelo: str) -> dict[str, Any]:
    """Abre la imagen y ejecuta las 4 tareas visuales, una llamada por tarea."""
    esquemas = {
        "ocr": C.ESQUEMA_OCR,
        "descripcion": C.ESQUEMA_DESCRIPCION,
        "escena": C.ESQUEMA_ESCENA,
        "objetos": C.ESQUEMA_OBJETOS,
    }
    with Image.open(ruta) as img:
        imagen = img.convert("RGB")
        prompts = construir_prompts(nombre)
        return {
            tarea: C.pedir_json(cliente, prompts[tarea], esquemas[tarea], modelo=modelo, imagen=imagen)
            for tarea in TAREAS
        }


def evaluar(caso: dict[str, Any], salida: dict[str, Any]) -> dict[str, Any]:
    """Compara la salida de Gemini con la referencia de la imagen."""
    ev: dict[str, Any] = {}

    # --- OCR -------------------------------------------------------------- #
    # Dos casos distintos: si la imagen tiene texto se mide la cobertura de los
    # fragmentos esperados; si no tiene texto, lo que se mide es que el modelo
    # NO se invente texto (control de alucinaciones).
    texto = salida["ocr"].get("texto", "")
    predice_texto = bool(C.palabras(texto))
    declaro_texto = bool(salida["ocr"].get("hay_texto"))
    esperados = caso["texto_esperado"]
    ev["ocr"] = {
        "hay_texto_esperado": bool(esperados),
        "hay_texto_predicho": declaro_texto,
        "texto_transcrito": texto,
        "legibilidad": salida["ocr"].get("legibilidad"),
    }
    if esperados:
        detectados = [frag for frag in esperados if C.coincide(frag, texto, umbral=0.6)]
        ev["ocr"].update(
            {
                "fragmentos_esperados": esperados,
                "fragmentos_detectados": detectados,
                "cobertura": round(len(detectados) / len(esperados), 4),
                "texto_inventado": False,
                "puntuacion": round(len(detectados) / len(esperados), 4),
            }
        )
    else:
        ev["ocr"].update(
            {
                "fragmentos_esperados": [],
                "fragmentos_detectados": [],
                "cobertura": None,
                "texto_inventado": predice_texto,
                "puntuacion": 0.0 if predice_texto else 1.0,
            }
        )

    # --- Descripcion ----------------------------------------------------- #
    # La descripcion es texto libre, asi que se puntua por cobertura de conceptos.
    # Cada concepto tiene variantes admitidas para no castigar un sinonimo
    # ("tocino" por bacon, "tumbado" por echado).
    descripcion = salida["descripcion"].get("descripcion", "")
    elementos = salida["descripcion"].get("elementos_clave", [])
    texto_busqueda = C.normalizar(descripcion + " " + " ".join(elementos))
    cubiertos, faltantes = [], []
    for concepto in caso["conceptos_descripcion"]:
        variantes = [concepto["concepto"], *concepto["variantes"]]
        if any(C.normalizar(v) in texto_busqueda for v in variantes if v):
            cubiertos.append(concepto["concepto"])
        else:
            faltantes.append(concepto["concepto"])
    ev["descripcion"] = {
        "predicho": descripcion,
        "elementos_clave": elementos,
        "conceptos_esperados": [c["concepto"] for c in caso["conceptos_descripcion"]],
        "conceptos_cubiertos": cubiertos,
        "conceptos_faltantes": faltantes,
        "cobertura": round(len(cubiertos) / len(caso["conceptos_descripcion"]), 4) if caso["conceptos_descripcion"] else 0.0,
    }

    # --- Escena ----------------------------------------------------------- #
    escena_pred = salida["escena"].get("escena", "").lower()
    ev["escena"] = {
        "esperado": caso["escena_esperada"],
        "predicho": escena_pred,
        "acierto": escena_pred == caso["escena_esperada"],
        "entorno": salida["escena"].get("entorno", ""),
        "confianza": salida["escena"].get("confianza"),
    }

    # --- Objetos ---------------------------------------------------------- #
    objetos = [o.get("nombre", "") for o in salida["objetos"].get("objetos", [])]
    precision, recall, f1, aciertos, fp, fn = C.prf_etiquetas(objetos, caso["objetos_esperados"], synonymos=True)
    ev["objetos"] = {
        "esperados": caso["objetos_esperados"],
        "predichos": objetos,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "aciertos": aciertos,
        "falsos_positivos": fp,
        "falsos_negativos": fn,
        "total_esperados": len(caso["objetos_esperados"]),
        "total_predichos": len(objetos),
    }
    return ev


def procesar(gt: dict[str, Any], cliente, modelo: str, solo: list[str] | None) -> list[dict[str, Any]]:
    casos = gt["imagenes"]
    if solo:
        casos = [c for c in casos if c["archivo"] in solo]

    registros = []
    for i, caso in enumerate(casos, 1):
        ruta = C.DIR_IMAGENES / caso["archivo"]
        print(f"[{i}/{len(casos)}] {caso['archivo']} ({caso['tipo']})")
        inicio = time.perf_counter()
        try:
            salida = analizar_imagen(cliente, ruta, caso["archivo"], modelo)
            evaluacion = evaluar(caso, salida)
            error = None
        except Exception as exc:  # noqa: BLE001
            salida, evaluacion = {}, {}
            error = f"{type(exc).__name__}: {exc}"
            print(f"    ERROR: {error}")
        registros.append(
            {
                "id": caso["archivo"],
                "tipo": caso["tipo"],
                "salida": salida,
                "evaluacion": evaluacion,
                "segundos": round(time.perf_counter() - inicio, 2),
                "error": error,
            }
        )
    return registros


def resumir(registros: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega las metricas por imagen, por tipo y global."""
    validos = [r for r in registros if r["evaluacion"]]

    por_imagen = []
    for r in validos:
        ev = r["evaluacion"]
        por_imagen.append(
            {
                "id": r["id"],
                "tipo": r["tipo"],
                "ocr": ev["ocr"]["puntuacion"],
                "ocr_modo": "cobertura de fragmentos" if ev["ocr"]["hay_texto_esperado"] else "sin texto (control)",
                "descripcion": ev["descripcion"]["cobertura"],
                "escena": 1.0 if ev["escena"]["acierto"] else 0.0,
                "escena_texto": f"{ev['escena']['esperado']}/{ev['escena']['predicho']}",
                "objetos_f1": ev["objetos"]["f1"],
                "objetos_precision": ev["objetos"]["precision"],
                "objetos_recall": ev["objetos"]["recall"],
                "segundos": r["segundos"],
            }
        )

    global_ = {
        "imagenes_analizadas": len(validos),
        "imagenes_con_error": len(registros) - len(validos),
        "ocr": C.promedio(t["ocr"] for t in por_imagen),
        "ocr_cobertura_texto": C.promedio(t["ocr"] for t in por_imagen if t["ocr_modo"].startswith("cobertura")),
        "ocr_control_sin_texto": C.promedio(
            t["ocr"] for t in por_imagen if t["ocr_modo"].startswith("sin texto")
        ),
        "ocr_texto_inventado": [r["id"] for r in validos if r["evaluacion"]["ocr"]["texto_inventado"]],
        "descripcion_cobertura": C.promedio(t["descripcion"] for t in por_imagen),
        "escena_accuracy": C.promedio(t["escena"] for t in por_imagen),
        "objetos_f1": C.promedio(t["objetos_f1"] for t in por_imagen),
        "objetos_precision": C.promedio(t["objetos_precision"] for t in por_imagen),
        "objetos_recall": C.promedio(t["objetos_recall"] for t in por_imagen),
        "segundos_medio": C.promedio(t["segundos"] for t in por_imagen),
    }

    por_tipo: dict[str, list[dict[str, Any]]] = {}
    for r in validos:
        por_tipo.setdefault(r["tipo"], []).append(r["evaluacion"])
    resumen_tipos = {
        tipo: {
            "n": len(evs),
            "ocr": C.promedio(e["ocr"]["puntuacion"] for e in evs),
            "descripcion_cobertura": C.promedio(e["descripcion"]["cobertura"] for e in evs),
            "escena_accuracy": C.promedio(1.0 if e["escena"]["acierto"] else 0.0 for e in evs),
            "objetos_f1": C.promedio(e["objetos"]["f1"] for e in evs),
        }
        for tipo, evs in sorted(por_tipo.items())
    }

    fallos_escena = [
        {"id": r["id"], "esperado": r["evaluacion"]["escena"]["esperado"], "predicho": r["evaluacion"]["escena"]["predicho"]}
        for r in validos
        if not r["evaluacion"]["escena"]["acierto"]
    ]

    return {
        "global": global_,
        "por_tipo": resumen_tipos,
        "por_imagen": por_imagen,
        "fallos_escena": fallos_escena,
    }


def grafico_por_imagen(metricas: dict[str, Any]) -> Path:
    """Mapa de calor con la precision de cada tarea visual en cada imagen."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    tareas = ["ocr", "descripcion", "escena", "objetos_f1"]
    etiquetas = ["OCR", "Descripcion", "Escena", "Objetos (F1)"]
    datos = [[100 * fila[tarea] for tarea in tareas] for fila in metricas["por_imagen"]]

    fig, ax = plt.subplots(figsize=(7, 3.2))
    mapa = ax.imshow(datos, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(etiquetas)), etiquetas)
    ax.set_yticks(range(len(metricas["por_imagen"])), [r["id"] for r in metricas["por_imagen"]])
    for i, fila in enumerate(datos):
        for j, valor in enumerate(fila):
            ax.text(j, i, f"{valor:.0f}", ha="center", va="center", fontsize=8)
    ax.set_title("Precision por tarea visual e imagen (%)")
    fig.colorbar(mapa, ax=ax, shrink=0.85)
    fig.tight_layout()
    ruta = C.DIR_RESULTADOS / "grafico_precision_imagenes.png"
    fig.savefig(ruta, dpi=140)
    plt.close(fig)
    return ruta


def imprimir_resumen(metricas: dict[str, Any]) -> None:
    g = metricas["global"]
    print("\n=== RESUMEN VISION ===")
    print(f"OCR        (mixta)    : {g['ocr'] * 100:5.1f}%")
    print(f"  con texto (cobertura): {g['ocr_cobertura_texto'] * 100:5.1f}%")
    print(f"  sin texto (control) : {g['ocr_control_sin_texto'] * 100:5.1f}%")
    print(f"Descripcion cobertura : {g['descripcion_cobertura'] * 100:5.1f}%")
    print(f"Escena     accuracy   : {g['escena_accuracy'] * 100:5.1f}%")
    print(f"Objetos    F1         : {g['objetos_f1'] * 100:5.1f}%")
    if g["ocr_texto_inventado"]:
        print(f"\nALERTA: texto inventado en {len(g['ocr_texto_inventado'])} imagen(es) sin texto: {g['ocr_texto_inventado']}")
    if metricas["fallos_escena"]:
        print("\nEscenas falladas:")
        for f in metricas["fallos_escena"]:
            print(f"  {f['id']}: {f['esperado']} -> {f['predicho']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisis de imagenes con Gemini")
    parser.add_argument("--modelo", default=C.MODELO_IMAGEN, help="Modelo multimodal de Gemini")
    parser.add_argument("--solo", nargs="+", help="Nombres de imagen a procesar")
    parser.add_argument("--solo-grafico", action="store_true", help="Regenera el grafico desde el JSON existente")
    args = parser.parse_args()

    ruta_json = C.DIR_RESULTADOS / NOMBRE_RESULTADO
    if args.solo_grafico:
        datos = json.loads(ruta_json.read_text(encoding="utf-8"))
        ruta = grafico_por_imagen(resumenir(datos["registros"]))
        print(f"Grafico: {ruta}")
        return

    gt = json.loads(RUTA_GT.read_text(encoding="utf-8"))
    cliente = C.cargar_cliente()

    print(f"Modelo: {args.modelo}")
    print(f"Imagenes: {RUTA_GT.name} ({len(gt['imagenes'])} referencias)\n")

    registros = procesar(gt, cliente, args.modelo, args.solo)
    metricas = resumir(registros)
    resultado = {
        "meta": {
            "tarea": "analisis de imagenes (vision)",
            "modelo": args.modelo,
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "ground_truth": RUTA_GT.name,
        },
        "metricas": metricas,
        "registros": registros,
    }

    ruta = C.guardar_json(NOMBRE_RESULTADO, resultado)
    print(f"\nGrafico: {grafico_por_imagen(metricas)}")
    imprimir_resumen(metricas)
    print(f"\nResultados: {ruta}")


if __name__ == "__main__":
    main()
