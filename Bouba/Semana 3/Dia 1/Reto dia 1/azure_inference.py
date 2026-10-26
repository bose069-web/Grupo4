#!/usr/bin/env python3
"""Lista los modelos de la VM de Azure y ejecuta el mismo prompt en varios.

Supone una API compatible con OpenAI (/v1/models, /v1/chat/completions).
Variables de entorno:
  AZURE_VM_URL      URL base, p. ej. http://<host>:<puerto>  (obligatoria)
  AZURE_VM_API_KEY  API key (opcional si la VM no exige autenticación)

Uso:
  python3 azure_inference.py list
  python3 azure_inference.py run -m modelo1 modelo2 -p "Tu prompt"
  python3 azure_inference.py run -m modelo1 modelo2          # prompt por defecto
"""
import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_PROMPT = (
    "Un tren sale a 80 km/h y otro a 100 km/h en sentido contrario desde "
    "puntos separados 450 km. ¿Cuándo se cruzan? Explica paso a paso."
)


def request(method, path, payload=None):
    base = os.environ.get("AZURE_VM_URL", "").rstrip("/")
    if not base:
        sys.exit("Falta la variable de entorno AZURE_VM_URL")
    headers = {"Content-Type": "application/json"}
    key = os.environ.get("AZURE_VM_API_KEY")
    if key:
        headers["Authorization"] = f"Bearer {key}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} en {path}: {e.read().decode(errors='replace')[:500]}")
    except urllib.error.URLError as e:
        sys.exit(f"No se pudo conectar a {base}: {e.reason}")


def list_models():
    data = request("GET", "/v1/models")
    return [m["id"] for m in data.get("data", [])]


def ask(model, prompt, temperature, max_tokens):
    start = time.perf_counter()
    data = request(
        "POST",
        "/v1/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
    )
    elapsed = time.perf_counter() - start
    usage = data.get("usage", {})
    out_tokens = usage.get("completion_tokens")
    return {
        "model": model,
        "answer": data["choices"][0]["message"]["content"],
        "seconds": round(elapsed, 2),
        "completion_tokens": out_tokens,
        "tokens_per_s": round(out_tokens / elapsed, 1) if out_tokens else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="Lista los modelos desplegados")
    run = sub.add_parser("run", help="Ejecuta un prompt en varios modelos")
    run.add_argument("-m", "--models", nargs="+", help="Modelos (por defecto, los 2 primeros de la VM)")
    run.add_argument("-p", "--prompt", default=DEFAULT_PROMPT)
    run.add_argument("-t", "--temperature", type=float, default=0.2)
    run.add_argument("--max-tokens", type=int, default=1024)
    run.add_argument("-o", "--output", default="resultados_azure.json")
    args = parser.parse_args()

    available = list_models()
    if args.cmd == "list":
        print("Modelos desplegados:")
        for m in available:
            print(f"  - {m}")
        return

    models = args.models or available[:2]
    if len(models) < 2:
        sys.exit("Se necesitan al menos 2 modelos para comparar")
    missing = [m for m in models if m not in available]
    if missing:
        sys.exit(f"Modelos no desplegados: {missing}. Disponibles: {available}")

    results = []
    for m in models:
        print(f"\n=== {m} ===")
        r = ask(m, args.prompt, args.temperature, args.max_tokens)
        print(r["answer"])
        print(f"\n[{r['seconds']} s | {r['completion_tokens']} tokens | {r['tokens_per_s']} tok/s]")
        results.append(r)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({"prompt": args.prompt, "results": results}, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {args.output}")


if __name__ == "__main__":
    main()
