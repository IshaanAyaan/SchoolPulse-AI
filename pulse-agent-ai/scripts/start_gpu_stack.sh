#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODEL="${LLM_MODEL:-google/gemma-4-12B-it}"
VLLM_HOST="${VLLM_HOST:-0.0.0.0}"
VLLM_PORT="${VLLM_PORT:-8000}"
API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8010}"
MAX_MODEL_LEN="${MAX_MODEL_LEN:-8192}"
GPU_MEMORY_UTILIZATION="${GPU_MEMORY_UTILIZATION:-0.85}"

if [[ -z "${LLM_API_KEY:-}" && -f "$HOME/.config/schoolprint/llm_api_key" ]]; then
  LLM_API_KEY="$(< "$HOME/.config/schoolprint/llm_api_key")"
fi
API_KEY="${LLM_API_KEY:-EMPTY}"

if [[ -z "${ELEVENLABS_API_KEY:-}" && -f "$HOME/.config/schoolprint/elevenlabs_api_key" ]]; then
  ELEVENLABS_API_KEY="$(< "$HOME/.config/schoolprint/elevenlabs_api_key")"
fi

mkdir -p tmp/logs

python3 -m venv .venv-gemma
source .venv-gemma/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pip install -r requirements-gpu.txt

python scripts/init_db.py

RUNTIME_ENV="tmp/runtime.env"
: > "$RUNTIME_ENV"
chmod 600 "$RUNTIME_ENV"
printf "ELEVENLABS_API_KEY=%q\n" "${ELEVENLABS_API_KEY:-}" >> "$RUNTIME_ENV"
printf "ELEVENLABS_VOICE_ID=%q\n" "${ELEVENLABS_VOICE_ID:-JBFqnCBsd6RMkjVDRZzb}" >> "$RUNTIME_ENV"
printf "ELEVENLABS_TTS_MODEL=%q\n" "${ELEVENLABS_TTS_MODEL:-eleven_flash_v2_5}" >> "$RUNTIME_ENV"
printf "ELEVENLABS_STT_MODEL=%q\n" "${ELEVENLABS_STT_MODEL:-scribe_v2}" >> "$RUNTIME_ENV"

if [[ -f tmp/vllm.pid ]]; then
  kill "$(cat tmp/vllm.pid)" 2>/dev/null || true
fi
if [[ -f tmp/api.pid ]]; then
  kill "$(cat tmp/api.pid)" 2>/dev/null || true
fi

nohup bash -lc "source .venv-gemma/bin/activate && vllm serve '$MODEL' --host '$VLLM_HOST' --port '$VLLM_PORT' --dtype bfloat16 --max-model-len '$MAX_MODEL_LEN' --gpu-memory-utilization '$GPU_MEMORY_UTILIZATION' --api-key '$API_KEY' --trust-remote-code" \
  > tmp/logs/vllm.log 2>&1 &
echo "$!" > tmp/vllm.pid

nohup bash -lc "source .venv-gemma/bin/activate && set -a && source '$RUNTIME_ENV' && set +a && export DATABASE_PATH=/tmp/schoolprint_ai.db && export LLM_BASE_URL='http://127.0.0.1:$VLLM_PORT/v1' && export LLM_MODEL='$MODEL' && export LLM_API_KEY='$API_KEY' && uvicorn app.main:app --host '$API_HOST' --port '$API_PORT'" \
  > tmp/logs/api.log 2>&1 &
echo "$!" > tmp/api.pid

echo "Started vLLM pid $(cat tmp/vllm.pid), log tmp/logs/vllm.log"
echo "Started FastAPI pid $(cat tmp/api.pid), log tmp/logs/api.log"
echo "Health: http://$API_HOST:$API_PORT/api/health"
