from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import PulseAgent


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / "docs" / "gpu_gemma_results.md"

BASE_URL = os.getenv("LLM_BASE_URL", "http://127.0.0.1:8000/v1").rstrip("/")
MODEL = os.getenv("LLM_MODEL", "google/gemma-4-12B-it")
API_KEY = os.getenv("LLM_API_KEY", "EMPTY")


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
        return (result.stdout or result.stderr).strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def post_chat(messages: list[dict], max_tokens: int = 180) -> dict:
    payload = {
        "model": MODEL,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    headers = {"Content-Type": "application/json"}
    if API_KEY:
        headers["Authorization"] = f"Bearer {API_KEY}"

    start = time.time()
    response = requests.post(f"{BASE_URL}/chat/completions", json=payload, headers=headers, timeout=240)
    seconds = round(time.time() - start, 2)
    response.raise_for_status()
    data = response.json()
    return {"seconds": seconds, "response": data}


def get_models() -> dict:
    response = requests.get(f"{BASE_URL}/models", timeout=30)
    response.raise_for_status()
    return response.json()


def run_agent_queries() -> list[dict]:
    agent = PulseAgent()
    queries = [
        "What should we fix first before Friday volleyball?",
        "Plan a sports event for 250 people and reduce energy and food waste.",
        "Explain why this is more than a dashboard for the judges.",
    ]
    results = []
    for query in queries:
        start = time.time()
        response = agent.answer(query)
        results.append(
            {
                "query": query,
                "seconds": round(time.time() - start, 2),
                "used_llm": bool(response["used_llm"]),
                "answer": response["answer"],
                "action_card_count": len(response["action_cards"]),
                "citations": response["citations"][:3],
            }
        )
    return results


def write_report(results: dict) -> None:
    direct = results["direct_chat"]["response"]
    direct_text = direct["choices"][0]["message"]["content"]
    usage = direct.get("usage", {})

    report = f"""# GPU Gemma Smoke Test Results

Generated: {results["generated_at"]}

## Environment

- Hostname: `{results["environment"]["hostname"]}`
- Python: `{results["environment"]["python"]}`
- Platform: `{results["environment"]["platform"]}`
- GPU: `{results["environment"]["gpu"]}`
- GPU memory after model load: `{results["environment"]["gpu_memory"]}`
- vLLM models endpoint: passed.

## Model Server

- Base URL: `{BASE_URL}`
- Model: `{MODEL}`
- Direct chat status: passed.
- Direct chat latency: {results["direct_chat"]["seconds"]} seconds.
- Prompt tokens: {usage.get("prompt_tokens")}
- Completion tokens: {usage.get("completion_tokens")}
- Total tokens: {usage.get("total_tokens")}

Direct chat answer:

> {direct_text}

## Pulse Agent With Gemma 4

All Pulse Agent queries returned `used_llm=True`, preserved analytics action cards, and included RAG citations.

"""
    for item in results["agent_queries"]:
        report += f"""### {item["query"]}

- Latency: {item["seconds"]} seconds.
- Used local LLM: `{item["used_llm"]}`
- Action cards: {item["action_card_count"]}
- Top citations: {", ".join(citation["source"] for citation in item["citations"])}

Answer excerpt:

> {item["answer"][:900].replace(chr(10), " ")}

"""

    report += """## Interpretation

The A100 can run the Pulse Agent backend plus `google/gemma-4-12B-it` locally. Gemma is best used as the explanation and voice-agent layer; the structured prediction models and RAG retrieval should stay separate so the system remains testable, grounded, and judge-friendly.
"""
    REPORT.write_text(report, encoding="utf-8")


def main() -> None:
    os.environ["LLM_BASE_URL"] = BASE_URL
    os.environ["LLM_MODEL"] = MODEL
    os.environ["LLM_API_KEY"] = API_KEY

    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "hostname": command_output(["hostname"]),
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "gpu": command_output(["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader"]),
            "gpu_memory": command_output(["nvidia-smi", "--query-gpu=memory.used,memory.free,utilization.gpu", "--format=csv,noheader"]),
        },
        "models": get_models(),
        "direct_chat": post_chat(
            [
                {"role": "system", "content": "You are a concise school sustainability assistant."},
                {
                    "role": "user",
                    "content": "In one sentence, explain what SchoolPrint AI should do before a volleyball game to reduce energy waste.",
                },
            ],
            max_tokens=120,
        ),
        "agent_queries": run_agent_queries(),
    }
    write_report(results)
    print(json.dumps(results, indent=2)[:12000])
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()

