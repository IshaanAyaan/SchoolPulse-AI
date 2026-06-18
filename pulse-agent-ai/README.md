# Pulse Agent AI

Pulse Agent AI is Ishaan's SchoolPrint AI backend layer for the USAII Global AI Hackathon 2026. It connects the water, compost/waste, energy, event, and transportation pieces into one school operations assistant.

The dashboard can stay simple. This folder is the backend brain:

```text
school context + synthetic/real logs
-> SQLite database
-> forecasting/anomaly/recommendation models
-> RAG over project docs and source notes
-> Gemma-ready voice/chat agent
-> simple API endpoints for the dashboard
```

## What This Builds

- A synthetic school-year dataset for energy, water, waste, events, and transportation.
- Training scripts for energy waste detection and event planning recommendations.
- A RAG index over the repo context, challenge notes, email summary, and research sources.
- A FastAPI backend with dashboard-friendly endpoints.
- A simple built-in dashboard for testing only.
- A Gemma 4 / Lambda deployment path using an OpenAI-compatible local model server.

## Quick Start

From the repo root:

```bash
cd pulse-agent-ai
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/generate_synthetic_data.py
python scripts/train_models.py
python scripts/build_rag_index.py
python scripts/init_db.py

uvicorn app.main:app --reload --port 8010
```

Open:

- Dashboard test page: `http://127.0.0.1:8010`
- API docs: `http://127.0.0.1:8010/docs`

## Main API Endpoints

```text
GET  /api/overview
GET  /api/energy
GET  /api/water
GET  /api/waste
GET  /api/events
POST /api/agent/query
POST /api/rag/search
```

The teammate building the real dashboard should only need these endpoints.

## Gemma 4 Mode

By default, the agent uses a deterministic fallback so the project runs on any laptop.

When a GPU server is available, run Gemma 4 behind a local OpenAI-compatible endpoint and set:

```bash
export LLM_BASE_URL="http://YOUR_LAMBDA_IP:8000/v1"
export LLM_MODEL="google/gemma-4-12B-it"
export LLM_API_KEY="EMPTY"
```

Then restart the FastAPI server. The RAG, database tools, and dashboard endpoints stay the same.

Recommended first GPU model: `google/gemma-4-12B-it`.

See [docs/gemma_lambda.md](docs/gemma_lambda.md) for the Lambda setup.

## Vercel, GPU, Supabase, and Google Sheets

For the public demo path, deploy this folder (`pulse-agent-ai`) on Vercel and run Gemma on the A100 as an OpenAI-compatible vLLM server. Supabase stores durable agent/log/context records, and Google Sheets can act as a staff-editable school data surface.

See [docs/deployment_vercel_gpu_supabase.md](docs/deployment_vercel_gpu_supabase.md).

## Why Judges Should Like This

- Problem understanding: school waste is framed as hidden operational memory loss, not generic sustainability.
- AI reasoning: uses anomaly detection, forecasting, retrieval, recommendations, and a voice/chat agent.
- Solution design: every insight becomes a human-checkable action card.
- Impact: estimates wasted kWh, gallons, food waste, compost diversion, and event footprint.
- Responsible AI: the agent explains confidence and always asks a human to verify before real-world action.
