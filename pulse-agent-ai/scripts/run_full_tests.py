from __future__ import annotations

import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agent import PulseAgent
from app.analytics import AnalyticsService
from app.database import ensure_database
from app.main import energy, event_plan, health, overview, query_agent, search_rag, waste, water
from app.rag import RagRetriever
from app.schemas import AgentQuery, RagSearchQuery


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "synthetic"
MODELS = ROOT / "models"
REPORT = ROOT / "docs" / "test_results.md"


def command_output(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
        return (result.stdout or result.stderr).strip()
    except Exception as exc:
        return f"unavailable: {exc}"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def test_data() -> dict:
    expected_minimums = {
        "energy_logs.csv": 10000,
        "event_plans.csv": 30,
        "water_alerts.csv": 50,
        "waste_logs.csv": 500,
        "transport_plans.csv": 30,
    }
    results = {}
    for filename, minimum in expected_minimums.items():
        frame = pd.read_csv(DATA / filename)
        assert_true(len(frame) >= minimum, f"{filename} had {len(frame)} rows, expected at least {minimum}")
        results[filename] = {"rows": int(len(frame)), "columns": list(frame.columns)}
    return results


def test_models() -> dict:
    energy_bundle = joblib.load(MODELS / "energy_waste_classifier.joblib")
    event_bundle = joblib.load(MODELS / "event_servings_regressor.joblib")
    metrics = json.loads((MODELS / "training_metrics.json").read_text(encoding="utf-8"))
    assert_true("evaluation_note" in metrics, "training_metrics.json must include synthetic-only note")
    assert_true(len(energy_bundle["feature_columns"]) > 5, "energy model feature columns missing")
    assert_true(len(event_bundle["feature_columns"]) > 3, "event model feature columns missing")
    return {
        "energy_model": type(energy_bundle["model"]).__name__,
        "event_model": type(event_bundle["model"]).__name__,
        "metrics": metrics,
    }


def test_rag() -> dict:
    retriever = RagRetriever()
    rubric = retriever.search("judging rubric responsible AI", top_k=3)
    energy = retriever.search("energy waste after hours event schedule", top_k=3)
    assert_true(rubric, "RAG returned no rubric results")
    assert_true(energy, "RAG returned no energy results")
    assert_true(
        any("context/briefs" in item["source"] or "context/README" in item["source"] for item in rubric),
        "Rubric query should retrieve challenge/context docs",
    )
    return {
        "rubric_sources": [item["source"] for item in rubric],
        "energy_sources": [item["source"] for item in energy],
    }


def test_services() -> dict:
    ensure_database()
    service = AnalyticsService()
    overview_data = service.overview()
    assert_true(overview_data["top_action_cards"], "overview must return action cards")
    assert_true(overview_data["impact_totals"]["events_analyzed"] >= 30, "overview event count too low")

    plan = service.recommend_event_plan("sports", 250, 3.0)
    assert_true(plan["recommended_servings"] > 0, "event plan servings must be positive")
    return {"overview": overview_data["impact_totals"], "sample_event_plan": plan}


def test_agent() -> dict:
    response = PulseAgent().answer("What should we fix first before Friday volleyball?")
    assert_true(response["answer"], "agent answer missing")
    assert_true(response["action_cards"], "agent action cards missing")
    assert_true("Human check" in response["answer"] or "human" in response["answer"].lower(), "agent needs human-check language")
    return {
        "used_llm": bool(response["used_llm"]),
        "answer_excerpt": response["answer"][:500],
        "action_card_count": len(response["action_cards"]),
        "citations": response["citations"],
    }


def test_route_handlers() -> dict:
    assert_true(health()["status"] == "ok", "health route failed")
    assert_true(overview()["top_action_cards"], "overview route returned no cards")
    assert_true(energy()["top_cards"], "energy route returned no cards")
    assert_true(water()["top_cards"], "water route returned no cards")
    assert_true("rows" in waste(), "waste route missing rows")
    assert_true(event_plan("sports", 250, 3.0)["recommended_servings"] > 0, "event-plan route failed")
    agent_response = query_agent(AgentQuery(query="What is the top issue?"))
    rag_response = search_rag(RagSearchQuery(query="responsible AI", top_k=2))
    assert_true(agent_response["answer"], "agent route answer missing")
    assert_true(rag_response["results"], "rag route missing results")
    return {
        "health": health(),
        "overview_card_count": len(overview()["top_action_cards"]),
        "energy_card_count": len(energy()["top_cards"]),
        "water_card_count": len(water()["top_cards"]),
        "rag_result_count": len(rag_response["results"]),
    }


def write_report(results: dict) -> None:
    metrics = results["models"]["metrics"]
    report = f"""# Pulse Agent AI Test Results

Generated: {results["generated_at"]}

## Environment

- Python: `{results["environment"]["python"]}`
- Platform: `{results["environment"]["platform"]}`
- GPU: `{results["environment"]["gpu"]}`

## Pipeline Checks

- Synthetic data: passed.
- Model artifacts: passed.
- RAG retrieval: passed.
- Analytics/action cards: passed.
- Agent response: passed.
- Backend route handlers: passed.

## Dataset Counts

| File | Rows |
| --- | ---: |
"""
    for filename, details in results["data"].items():
        report += f"| `{filename}` | {details['rows']} |\n"

    report += f"""
## Model Results

- Energy classifier: `{results["models"]["energy_model"]}`
- Event servings regressor: `{results["models"]["event_model"]}`
- Evaluation note: {metrics["evaluation_note"]}
- Energy rows: {metrics["energy_waste_classifier"]["rows"]}
- Synthetic energy F1: {metrics["energy_waste_classifier"]["f1"]:.3f}
- Event servings MAE: {metrics["event_servings_regressor"]["mae_servings"]:.2f} servings

## Agent Smoke Result

- Used external LLM: `{results["agent"]["used_llm"]}`
- Action cards returned: {results["agent"]["action_card_count"]}
- Answer excerpt: {results["agent"]["answer_excerpt"]}

## RAG Smoke Result

- Rubric sources: {", ".join(results["rag"]["rubric_sources"])}
- Energy sources: {", ".join(results["rag"]["energy_sources"])}

## Sample Event Plan

```json
{json.dumps(results["services"]["sample_event_plan"], indent=2)}
```

## Notes

This report validates the structured backend pipeline. If it is run on a GPU machine, the environment section records the detected GPU. Local LLM/vLLM results are tracked separately in `docs/gpu_gemma_results.md`.
"""
    REPORT.write_text(report, encoding="utf-8")


def main() -> None:
    results = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python": sys.version.replace("\n", " "),
            "platform": platform.platform(),
            "gpu": command_output(["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"]),
        },
        "data": test_data(),
        "models": test_models(),
        "rag": test_rag(),
        "services": test_services(),
        "agent": test_agent(),
        "routes": test_route_handlers(),
    }
    write_report(results)
    print(json.dumps(results, indent=2))
    print(f"Wrote {REPORT}")


if __name__ == "__main__":
    main()
