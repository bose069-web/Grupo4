#!/usr/bin/env python3
"""Inventory and compare two OpenAI-compatible models exposed by Azure/Inetum."""

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


PROMPT = (
    "Explica en español, para una persona técnica no especialista, qué diferencia "
    "hay entre parámetros totales y parámetros activos en un modelo "
    "Mixture-of-Experts. Usa un ejemplo numérico sencillo, indica una ventaja y "
    "una limitación, y responde en un máximo de 180 palabras."
)


def request_json(url, method="GET", payload=None, api_key=None, auth_header="Authorization"):
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if api_key:
        headers[auth_header] = (
            f"Bearer {api_key}" if auth_header.lower() == "authorization" else api_key
        )
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            raw = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} en {url}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"No se pudo conectar con {url}: {exc.reason}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"La respuesta de {url} no es JSON válido: {raw[:500]}") from exc
    return parsed, status, round((time.perf_counter() - started) * 1000, 1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs=2, metavar=("MODEL_A", "MODEL_B"))
    parser.add_argument("--base-url", default=os.getenv("AZURE_API_BASE"))
    parser.add_argument("--api-key", default=os.getenv("AZURE_API_KEY"))
    parser.add_argument("--models-path", default="/v1/models")
    parser.add_argument("--chat-path", default="/v1/chat/completions")
    parser.add_argument("--auth-header", default="Authorization")
    parser.add_argument("--output", default="resultados-azure.json")
    args = parser.parse_args()

    if not args.base_url:
        parser.error("indica --base-url o define AZURE_API_BASE")
    if not args.models:
        parser.error("indica exactamente dos modelos con --models modelo-a modelo-b")

    base = args.base_url.rstrip("/")
    inventory, inventory_status, inventory_ms = request_json(
        base + args.models_path, api_key=args.api_key, auth_header=args.auth_header
    )
    available = [
        item.get("id") for item in inventory.get("data", [])
        if isinstance(item, dict) and item.get("id")
    ]
    missing = [model for model in args.models if model not in available]
    if missing:
        raise RuntimeError(
            "Los modelos solicitados no aparecen en /models: "
            + ", ".join(missing)
            + ". Disponibles: "
            + ", ".join(available)
        )

    responses = []
    for model in args.models:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "temperature": 0,
            "max_tokens": 256,
        }
        response, status, elapsed_ms = request_json(
            base + args.chat_path,
            method="POST",
            payload=payload,
            api_key=args.api_key,
            auth_header=args.auth_header,
        )
        choice = response.get("choices", [{}])[0]
        message = choice.get("message", {})
        responses.append(
            {
                "model": model,
                "http_status": status,
                "latency_ms": elapsed_ms,
                "text": message.get("content"),
                "usage": response.get("usage"),
                "raw_response": response,
            }
        )

    result = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "prompt": PROMPT,
        "model_inventory": {
            "http_status": inventory_status,
            "latency_ms": inventory_ms,
            "models": available,
            "raw_response": inventory,
        },
        "responses": responses,
    }
    with open(args.output, "w", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2)
    print(f"Inventario: {len(available)} modelos")
    print(f"Resultados guardados en {args.output}")


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
