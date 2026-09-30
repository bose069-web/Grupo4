"""Reto del dia 2 (TEXTO): analisis avanzado de texto con Gemini.

Pipeline por cada texto (4 llamadas, cada una con salida JSON estricta):
  1. Deteccion de idioma
  2. Extraccion de entidades nombradas (NER)
  3. Analisis de sentimiento
  4. Resumen automatico

Los resultados se comparan con las etiquetas de referencia de `datos/corpus_textos.json`.

Uso:
    python analisis_textos.py
    python analisis_textos.py --modelo models/gemini-2.5-flash
    python analisis_textos.py --solo T01 T02
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from typing import Any

import comun as C

RUTA_CORPUS = C.DIR_DATOS / "corpus_textos.json"
NOMBRE_RESULTADO = "resultados_textos.json"

TAREAS = ("idioma", "entidades", "sentimiento", "resumen")


def analizar_texto(cliente, texto: str, modelo: str) -> dict[str, Any]:
    """Ejecuta las 4 tareas del pipeline sobre un texto, una llamada por tarea."""
    esquemas = {
        "idioma": C.ESQUEMA_IDIOMA,
        "entidades": C.ESQUEMA_ENTIDADES,
        "sentimiento": C.ESQUEMA_SENTIMIENTO,
        "resumen": C.ESQUEMA_RESUMEN,
    }
    prompts = {
        "idioma": C.PROMPT_IDIOMA,
        "entidades": C.PROMPT_ENTIDADES,
        "sentimiento": C.PROMPT_SENTIMIENTO,
        "resumen": C.PROMPT_RESUMEN,
    }
    return {
        tarea: C.pedir_json(cliente, prompts[tarea].format(texto=texto), esquemas[tarea], modelo=modelo)
        for tarea in TAREAS
    }


def evaluar(caso: dict[str, Any], salida: dict[str, Any]) -> dict[str, Any]:
    """Compara la salida de Gemini con las etiquetas de referencia del texto."""
    gold = caso["gold"]
    ev: dict[str, Any] = {}

    idioma_pred = salida["idioma"].get("idioma", "").lower()
    ev["idioma"] = {
        "esperado": gold["idioma"],
        "predicho": idioma_pred,
        "acierto": idioma_pred == gold["idioma"],
        "confianza": salida["idioma"].get("confianza"),
        "pistas": salida["idioma"].get("pistas", []),
    }

    sent_pred = salida["sentimiento"].get("sentimiento", "").lower()
    ev["sentimiento"] = {
        "esperado": gold["sentimiento"],
        "predicho": sent_pred,
        "acierto": sent_pred == gold["sentimiento"],
        "confianza": salida["sentimiento"].get("confianza"),
        "explicacion": salida["sentimiento"].get("explicacion", ""),
    }

    ents = [e.get("texto", "") for e in salida["entidades"].get("entidades", [])]
    precision, recall, f1, aciertos, fp, fn = C.prf_etiquetas(ents, gold["entidades"])
    ev["entidades"] = {
        "esperadas": gold["entidades"],
        "predichas": ents,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "aciertos": aciertos,
        "falsos_positivos": fp,
        "falsos_negativos": fn,
        "total_esperadas": len(gold["entidades"]),
        "total_predichas": len(ents),
    }

    resumen = salida["resumen"].get("resumen", "")
    p, r, f1r, comunes = C.f1_texto(resumen, gold["resumen"])
    palabras_orig = len(C.palabras(caso["texto"]))
    palabras_res = len(C.palabras(resumen))
    ev["resumen"] = {
        "esperado": gold["resumen"],
        "predicho": resumen,
        "precision_palabras": round(p, 4),
        "recall_palabras": round(r, 4),
        "f1_palabras": round(f1r, 4),
        "palabras_comunes": comunes,
        "palabras_originales": palabras_orig,
        "palabras_resumen": palabras_res,
        "tasa_compresion": round(palabras_res / palabras_orig, 4) if palabras_orig else 0.0,
        "similitud_caracteres": round(C.texto_similitud(resumen, gold["resumen"]), 4),
        "palabras_clave": salida["resumen"].get("palabras_clave", []),
    }
    return ev


def procesar(corpus: dict[str, Any], cliente, modelo: str, solo: list[str] | None) -> list[dict[str, Any]]:
    casos = corpus["textos"]
    if solo:
        casos = [c for c in casos if c["id"] in solo]

    registros = []
    for i, caso in enumerate(casos, 1):
        print(f"[{i}/{len(casos)}] {caso['id']} ({caso['categoria']}, {len(C.palabras(caso['texto']))} palabras)")
        inicio = time.perf_counter()
        try:
            salida = analizar_texto(cliente, caso["texto"], modelo)
            evaluacion = evaluar(caso, salida)
            error = None
        except Exception as exc:  # noqa: BLE001
            salida, evaluacion = {}, {}
            error = f"{type(exc).__name__}: {exc}"
            print(f"    ERROR: {error}")
        registros.append(
            {
                "id": caso["id"],
                "categoria": caso["categoria"],
                "texto": caso["texto"],
                "salida": salida,
                "evaluacion": evaluacion,
                "segundos": round(time.perf_counter() - inicio, 2),
                "error": error,
            }
        )
    return registros


def resumir(registros: list[dict[str, Any]]) -> dict[str, Any]:
    """Agrega las metricas por texto, por categoria y global."""
    validos = [r for r in registros if r["evaluacion"]]

    por_texto = [
        {
            "id": r["id"],
            "categoria": r["categoria"],
            "idioma_ok": r["evaluacion"]["idioma"]["acierto"],
            "idioma": f"{r['evaluacion']['idioma']['esperado']}/{r['evaluacion']['idioma']['predicho']}",
            "sentimiento_ok": r["evaluacion"]["sentimiento"]["acierto"],
            "sentimiento": f"{r['evaluacion']['sentimiento']['esperado']}/{r['evaluacion']['sentimiento']['predicho']}",
            "entidades_f1": r["evaluacion"]["entidades"]["f1"],
            "entidades_esperadas": r["evaluacion"]["entidades"]["total_esperadas"],
            "entidades_predichas": r["evaluacion"]["entidades"]["total_predichas"],
            "resumen_f1": r["evaluacion"]["resumen"]["f1_palabras"],
            "resumen_similitud": r["evaluacion"]["resumen"]["similitud_caracteres"],
            "compresion": r["evaluacion"]["resumen"]["tasa_compresion"],
            "segundos": r["segundos"],
        }
        for r in validos
    ]

    global_ = {
        "textos_analizados": len(validos),
        "textos_con_error": len(registros) - len(validos),
        "accuracy_idioma": C.promedio(1.0 if t["idioma_ok"] else 0.0 for t in por_texto),
        "accuracy_sentimiento": C.promedio(1.0 if t["sentimiento_ok"] else 0.0 for t in por_texto),
        "f1_entidades": C.promedio(t["entidades_f1"] for t in por_texto),
        "f1_resumen": C.promedio(t["resumen_f1"] for t in por_texto),
        "similitud_resumen": C.promedio(t["resumen_similitud"] for t in por_texto),
        "tasa_compresion": C.promedio(t["compresion"] for t in por_texto),
        "segundos_medio": C.promedio(t["segundos"] for t in por_texto),
    }

    por_categoria: dict[str, list[dict[str, Any]]] = {}
    for r in validos:
        por_categoria.setdefault(r["categoria"], []).append(r["evaluacion"])
    resumen_categorias = {
        cat: {
            "n": len(evs),
            "accuracy_idioma": C.promedio(1.0 if e["idioma"]["acierto"] else 0.0 for e in evs),
            "accuracy_sentimiento": C.promedio(1.0 if e["sentimiento"]["acierto"] else 0.0 for e in evs),
            "f1_entidades": C.promedio(e["entidades"]["f1"] for e in evs),
            "f1_resumen": C.promedio(e["resumen"]["f1_palabras"] for e in evs),
        }
        for cat, evs in sorted(por_categoria.items())
    }

    idiomas: dict[str, int] = {}
    for r in validos:
        codigo = r["evaluacion"]["idioma"]["esperado"]
        idiomas[codigo] = idiomas.get(codigo, 0) + 1

    discrepancias = [
        f"{r['id']} ({r['categoria']}): idioma {r['evaluacion']['idioma']['esperado']}"
        f"->{r['evaluacion']['idioma']['predicho']}, sentimiento "
        f"{r['evaluacion']['sentimiento']['esperado']}->{r['evaluacion']['sentimiento']['predicho']}"
        for r in validos
        if not r["evaluacion"]["idioma"]["acierto"] or not r["evaluacion"]["sentimiento"]["acierto"]
    ]

    return {
        "global": global_,
        "por_categoria": resumen_categorias,
        "por_texto": por_texto,
        "distribucion_idiomas": idiomas,
        "discrepancias": discrepancias,
    }


def imprimir_resumen(metricas: dict[str, Any]) -> None:
    g = metricas["global"]
    print("\n=== RESUMEN TEXTO ===")
    print(f"Textos analizados: {g['textos_analizados']} (con error: {g['textos_con_error']})")
    print(f"Idioma      accuracy: {g['accuracy_idioma'] * 100:5.1f}%")
    print(f"Sentimiento accuracy: {g['accuracy_sentimiento'] * 100:5.1f}%")
    print(f"Entidades   F1      : {g['f1_entidades'] * 100:5.1f}%")
    print(f"Resumen     F1      : {g['f1_resumen'] * 100:5.1f}%")
    print(f"Resumen     similitud: {g['similitud_resumen'] * 100:5.1f}%")
    if metricas["discrepancias"]:
        print("\nDiscrepancias respecto al gold:")
        for d in metricas["discrepancias"]:
            print(f"  {d}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisis avanzado de texto con Gemini")
    parser.add_argument("--modelo", default=C.MODELO_TEXTO, help="Modelo de Gemini para texto")
    parser.add_argument("--solo", nargs="+", help="IDs de texto a procesar (p.ej. T01 T02)")
    args = parser.parse_args()

    corpus = json.loads(RUTA_CORPUS.read_text(encoding="utf-8"))
    cliente = C.cargar_cliente()

    print(f"Modelo: {args.modelo}")
    print(f"Corpus: {RUTA_CORPUS.name} ({len(corpus['textos'])} textos)\n")

    registros = procesar(corpus, cliente, args.modelo, args.solo)
    metricas = resumir(registros)
    resultado = {
        "meta": {
            "tarea": "analisis de texto",
            "modelo": args.modelo,
            "fecha": datetime.now().isoformat(timespec="seconds"),
            "corpus": RUTA_CORPUS.name,
        },
        "metricas": metricas,
        "registros": registros,
    }

    ruta = C.guardar_json(NOMBRE_RESULTADO, resultado)
    imprimir_resumen(metricas)
    print(f"\nResultados: {ruta}")


if __name__ == "__main__":
    main()
