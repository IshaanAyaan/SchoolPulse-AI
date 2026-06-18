# Pulse Agent AI Test Results

Generated: 2026-06-18T22:24:14.570946+00:00

## Environment

- Python: `3.12.13 (main, Mar  3 2026, 15:35:03) [Clang 21.1.4 ]`
- Platform: `macOS-26.5.1-arm64-arm-64bit`
- GPU: `unavailable: [Errno 2] No such file or directory: 'nvidia-smi'`

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
| `energy_logs.csv` | 200 |
| `event_logs.csv` | 50 |
| `water_logs.csv` | 50 |
| `waste_logs.csv` | 50 |
| `transport_plans.csv` | 40 |

## Model Results

- Energy classifier: `RandomForestClassifier`
- Event servings regressor: `RandomForestRegressor`
- Evaluation note: Metrics are for synthetic MVP wiring only. Real school or BDG2 data should be used before claiming real-world accuracy.
- Energy rows: 16632
- Synthetic energy F1: 1.000
- Event servings MAE: 32.46 servings

## Agent Smoke Result

- Used external LLM: `False`
- Action cards returned: 6
- Answer excerpt: Highest priority: Possible leak at B-Wing Bathroom Toilet 3 in B-Wing Bathroom Toilet 3. Send a custodian to listen/check the fixture before opening a repair ticket. Evidence: 20 min continuous-flow pattern, confidence 96%. Estimated impact: About 113 gallons at risk. Human check: Custodian confirms a visible leak or stuck fixture before escalation. I grounded this in `Google Doc Final Idea`. Current totals show about 61.0 wasted kWh, 559.2 gallons at water risk, and 18.0 lb food waste logged.

## RAG Smoke Result

- Rubric sources: context/briefs/README.md, context/README.md, info/email-summary.md
- Energy sources: README.md, pulse-agent-ai/docs/data_strategy.md, pulse-agent-ai/docs/data_strategy.md

## Sample Event Plan

```json
{
  "event_type": "sports",
  "expected_attendance": 250,
  "recommended_servings": 185,
  "energy_note": "Schedule HVAC/lights to start 45 minutes before arrival and shut down 20 minutes after teardown.",
  "waste_note": "Log actual attendance, leftovers, compost, and trash bags after the event to improve next forecast.",
  "human_check": "Event lead reviews the order and facilities schedule before anything is purchased or changed."
}
```

## Notes

This report validates the structured backend pipeline. If it is run on a GPU machine, the environment section records the detected GPU. Local LLM/vLLM results are tracked separately in `docs/gpu_gemma_results.md`.
