# Pulse Agent AI Test Results

Generated: 2026-06-17T19:02:22.271784+00:00

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
| `energy_logs.csv` | 16632 |
| `event_plans.csv` | 40 |
| `water_alerts.csv` | 70 |
| `waste_logs.csv` | 900 |
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
- Answer excerpt: Highest priority: After-hours energy spike in Gym. Check room schedule, lights, HVAC setpoint, and event teardown checklist. Evidence: 33.5 kWh actual vs 14.5 kWh expected. Estimated impact: About 19.0 kWh potentially wasted in this hour. Human check: Facilities staff confirms whether the room was actually occupied before changing controls. I grounded this in `Google Doc Final Idea`. Current totals show about 6953.3 wasted kWh, 1190.1 gallons at water risk, and 254.6 lb food waste logged.

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

## Remote GPU Status

The first A10 SSH test was attempted with `ssh ubuntu@170.9.49.205`, but the host rejected the available local keys with `Permission denied (publickey)`.

Next step for GPU/Gemma testing: add this machine's public key to the A10 server or provide the matching private key, then run this same script plus the Gemma/vLLM server test on the GPU box.
