#!/usr/bin/env python3
"""Concurrent load test for the local Flask proxy, Ollama, or OpenAI-compatible APIs."""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import statistics
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import aiohttp
import psutil


DEFAULT_PROMPTS = [
    "Explica en español qué es un modelo de lenguaje en tres frases.",
    "Enumera tres buenas prácticas para una API HTTP.",
    "Resume la diferencia entre CPU y GPU en cuatro frases.",
    "¿Qué ventajas tiene usar caché en una aplicación?",
]


@dataclass
class RequestResult:
    backend: str
    scenario: str
    concurrency: int
    request_id: int
    ok: bool
    status: int | None
    latency_ms: float
    output_tokens: int | None
    tokens_per_second: float | None
    error: str | None


def percentile(values: list[float], p: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, round((len(ordered) - 1) * p))
    return round(ordered[index], 2)


def parse_response(data: Any, protocol: str) -> tuple[str, int | None]:
    if protocol == "proxy":
        return str(data["respuesta"]), data.get("output_tokens")
    if protocol == "ollama":
        message = data["message"]["content"]
        return str(message), data.get("eval_count")
    choices = data.get("choices") or []
    message = choices[0].get("message", {}) if choices else {}
    usage = data.get("usage") or {}
    return str(message.get("content", "")), usage.get("completion_tokens")


def make_request(url: str, protocol: str, model: str, prompt: str, temperature: float, max_tokens: int) -> tuple[str, dict[str, Any]]:
    if protocol == "proxy":
        return url, {"mensaje": prompt}
    if protocol == "ollama":
        return url, {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": temperature, "num_predict": max_tokens},
        }
    return url, {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }


async def one_request(
    session: aiohttp.ClientSession,
    backend: str,
    scenario: str,
    concurrency: int,
    request_id: int,
    url: str,
    protocol: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
    headers: dict[str, str],
) -> RequestResult:
    target, payload = make_request(url, protocol, model, prompt, temperature, max_tokens)
    started = time.perf_counter()
    try:
        async with session.post(target, json=payload, headers=headers) as response:
            status = response.status
            data = await response.json(content_type=None)
            if status >= 400:
                raise RuntimeError(f"HTTP {status}: {str(data)[:300]}")
            _, output_tokens = parse_response(data, protocol)
            elapsed = time.perf_counter() - started
            rate = output_tokens / elapsed if output_tokens and elapsed > 0 else None
            return RequestResult(backend, scenario, concurrency, request_id, True, status,
                                 round(elapsed * 1000, 2), output_tokens,
                                 round(rate, 2) if rate else None, None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        return RequestResult(backend, scenario, concurrency, request_id, False, None,
                             round((time.perf_counter() - started) * 1000, 2),
                             None, None, str(exc)[:500])


async def run_scenario(
    backend: str,
    url: str,
    protocol: str,
    model: str,
    concurrency: int,
    requests_per_user: int,
    temperature: float,
    max_tokens: int,
    prompts: list[str],
    headers: dict[str, str],
    timeout: float,
) -> tuple[list[RequestResult], dict[str, float]]:
    scenario = f"{concurrency}_usuarios"
    total = concurrency * requests_per_user
    cpu_start = psutil.cpu_percent(interval=0.2)
    process = psutil.Process()
    rss_start = process.memory_info().rss
    connector = aiohttp.TCPConnector(limit=concurrency)
    request_timeout = aiohttp.ClientTimeout(total=timeout)
    async with aiohttp.ClientSession(connector=connector, timeout=request_timeout) as session:
        tasks = [
            one_request(session, backend, scenario, concurrency, request_id, url, protocol,
                        model, prompts[request_id % len(prompts)], temperature, max_tokens, headers)
            for request_id in range(total)
        ]
        results = await asyncio.gather(*tasks)
    cpu_end = psutil.cpu_percent(interval=0.2)
    rss_end = process.memory_info().rss
    resources = {
        "client_cpu_percent_avg": round((cpu_start + cpu_end) / 2, 2),
        "client_ram_mb_delta": round((rss_end - rss_start) / 1024 / 1024, 2),
    }
    return results, resources


def summarize(results: list[RequestResult], resources: dict[str, float]) -> dict[str, Any]:
    successful = [item for item in results if item.ok]
    latencies = [item.latency_ms for item in successful]
    rates = [item.tokens_per_second for item in successful if item.tokens_per_second]
    return {
        "backend": results[0].backend if results else "",
        "scenario": results[0].scenario if results else "",
        "concurrency": results[0].concurrency if results else 0,
        "total_requests": len(results),
        "successful_requests": len(successful),
        "errors": len(results) - len(successful),
        "error_rate_percent": round((len(results) - len(successful)) / len(results) * 100, 2) if results else 0,
        "latency_ms_avg": round(statistics.mean(latencies), 2) if latencies else None,
        "latency_ms_p50": percentile(latencies, 0.50),
        "latency_ms_p95": percentile(latencies, 0.95),
        "tokens_per_second_avg": round(statistics.mean(rates), 2) if rates else None,
        **resources,
    }


async def main(args: argparse.Namespace) -> None:
    headers = {"Accept": "application/json"}
    if args.api_key:
        headers[args.auth_header] = args.api_key if args.auth_header.lower() != "authorization" else f"Bearer {args.api_key}"
    all_summaries: list[dict[str, Any]] = []
    all_results: list[RequestResult] = []
    for concurrency in args.concurrency:
        results, resources = await run_scenario(
            args.backend, args.url, args.protocol, args.model, concurrency,
            args.requests_per_user, args.temperature, args.max_tokens,
            args.prompt or DEFAULT_PROMPTS, headers, args.timeout,
        )
        all_results.extend(results)
        summary = summarize(results, resources)
        all_summaries.append(summary)
        print(json.dumps(summary, ensure_ascii=False))

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    document = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "configuration": vars(args),
        "summary": all_summaries,
        "requests": [asdict(result) for result in all_results],
    }
    output.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = output.with_suffix(".csv")
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(all_summaries[0]) if all_summaries else ["backend"])
        writer.writeheader()
        writer.writerows(all_summaries)
    print(f"Resultados: {output}")
    print(f"Resumen CSV: {csv_path}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", required=True, help="Nombre descriptivo, por ejemplo local o azure")
    parser.add_argument("--url", required=True, help="Endpoint POST")
    parser.add_argument("--protocol", choices=("proxy", "ollama", "openai"), default="proxy")
    parser.add_argument("--model", default=os.getenv("MODELO", "gemma4:e4b"))
    parser.add_argument("--concurrency", nargs="+", type=int, default=[5, 10, 20])
    parser.add_argument("--requests-per-user", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=128)
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--prompt", action="append")
    parser.add_argument("--api-key", default=os.getenv("API_KEY"))
    parser.add_argument("--auth-header", default="Authorization")
    parser.add_argument("--output", default="resultados/carga.json")
    return parser.parse_args()


if __name__ == "__main__":
    asyncio.run(main(parse_args()))
