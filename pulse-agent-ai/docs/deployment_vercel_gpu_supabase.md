# Vercel + A100 + Supabase Deployment

## Runtime Shape

```text
Browser dashboard on Vercel
  -> FastAPI endpoints on Vercel
  -> OpenAI-compatible Gemma endpoint on the A100
  -> Supabase for durable logs and synced school context
```

Vercel should deploy from the `pulse-agent-ai` directory. The GPU should run vLLM. Supabase stores agent runs, operational logs, and source documents. Google Sheets can be used as a staff-editable operational log surface.

## Vercel

Set the Vercel project root directory to:

```text
pulse-agent-ai
```

Environment variables:

```bash
DATABASE_PATH=/tmp/schoolprint_ai.db
RAG_INDEX_PATH=rag_index/index.joblib
LLM_BASE_URL=http://129.153.110.167:8000/v1
LLM_MODEL=google/gemma-4-12B-it
LLM_API_KEY=<same secret passed to vLLM --api-key>
ALLOWED_ORIGINS=*
```

Deploy:

```bash
cd pulse-agent-ai
vercel --prod
```

## A100 GPU

Clone or pull the repo on the GPU:

```bash
git clone https://github.com/vignesh-nagarajan-vn/SchoolPrint-AI.git
cd SchoolPrint-AI/pulse-agent-ai
git pull
```

Start the model and backend:

```bash
export LLM_API_KEY=<secret shared with Vercel>
bash scripts/start_gpu_stack.sh
```

Check it:

```bash
LLM_API_KEY=<secret shared with Vercel> bash scripts/check_gpu_stack.sh
```

## Supabase

Install package:

```bash
npm install @supabase/server @supabase/supabase-js
```

Required environment variables, copied from the Supabase dashboard Connect dialog:

```bash
SUPABASE_URL=
SUPABASE_PUBLISHABLE_KEY=
SUPABASE_SECRET_KEY=
SUPABASE_JWKS_URL=
```

Apply the SQL in:

```text
supabase/migrations/20260618213000_schoolprint_core.sql
```

Deploy the Edge Function:

```bash
supabase functions deploy schoolprint-sync
```

Because this function uses `auth: "secret"`, `supabase/config.toml` sets `verify_jwt = false` for this function. Callers must send the secret key in the `apikey` header.

Sync seed data:

```bash
export SUPABASE_SYNC_URL=https://<project-ref>.supabase.co/functions/v1/schoolprint-sync
export SUPABASE_SECRET_KEY=<secret key>
python scripts/sync_supabase_seed.py
```

## Google Sheets

Create a Google Sheet with tabs for energy, water, waste, event, and transportation logs. Share it with the service account email.

Install optional dependencies:

```bash
pip install -r requirements-google.txt
```

Sync synthetic demo logs into the sheet:

```bash
export GOOGLE_SERVICE_ACCOUNT_JSON='<service-account-json>'
export GOOGLE_SHEET_ID=<spreadsheet-id>
python scripts/sync_google_sheets.py
```

The expected tabs are:

- `energy_logs`
- `water_logs`
- `waste_logs`
- `event_logs`
- `transport_plans`
