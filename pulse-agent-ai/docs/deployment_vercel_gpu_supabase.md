# Vercel + A100 + Supabase Deployment

## Runtime Shape

```text
Browser dashboard on Vercel
  -> Vercel rewrites /api/* to the A100 public tunnel
  -> FastAPI + RAG + analytics on the A100
  -> OpenAI-compatible Gemma/vLLM on the same A100
  -> Supabase for durable logs and synced school context
```

Vercel should deploy from the `pulse-agent-ai` directory. The GPU should run both the FastAPI backend and vLLM. Supabase stores agent runs, operational logs, and source documents. Google Sheets can be used as a staff-editable operational log surface.

For the current demo, the A100 API is exposed through a temporary Cloudflare quick tunnel because direct traffic to `129.153.110.167:8010` is blocked by the cloud firewall:

```text
https://mls-shaw-stack-folding.trycloudflare.com
```

If the A100 is restarted or the tunnel process stops, start a new tunnel and update `vercel.json` with the new URL. The more stable option is to open inbound TCP port `8010` in the Lambda firewall/security settings and change `vercel.json` back to `http://129.153.110.167:8010`.

Tunnel restart command on the A100:

```bash
cd ~/SchoolPrint-AI/pulse-agent-ai
bash scripts/start_api_tunnel.sh
```

## Vercel

Set the Vercel project root directory to:

```text
pulse-agent-ai
```

Environment variables:

```bash
# No Python runtime env is required for the static Vercel dashboard.
# API traffic is proxied to the A100 in vercel.json.
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

Optional voice environment on the A100:

```bash
mkdir -p ~/.config/schoolprint
chmod 700 ~/.config/schoolprint
printf '%s\n' '<elevenlabs-api-key>' > ~/.config/schoolprint/elevenlabs_api_key
chmod 600 ~/.config/schoolprint/elevenlabs_api_key
```

`scripts/start_gpu_stack.sh` reads that private file and exposes it only to the FastAPI process as `ELEVENLABS_API_KEY`. The browser never receives the key. You can also override:

```bash
ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb
ELEVENLABS_TTS_MODEL=eleven_flash_v2_5
ELEVENLABS_STT_MODEL=scribe_v2
```

## Model sizing

The current GPU path runs `google/gemma-4-12B-it` in bf16 because it fits comfortably on an A100 40 GB, leaving room for the API, KV cache, and demo traffic. A larger bf16 model may exceed memory once KV cache is included. A larger quantized model can be tested next, but keep the 12B model as the demo-safe default unless the replacement is verified for latency, multilingual quality, and action-card grounding.

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
