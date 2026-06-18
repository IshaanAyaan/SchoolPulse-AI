#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://127.0.0.1:8010}"
VLLM_BASE_URL="${VLLM_BASE_URL:-http://127.0.0.1:8000/v1}"
API_KEY="${LLM_API_KEY:-EMPTY}"

echo "FastAPI health:"
curl -sS "$API_BASE_URL/api/health"
echo

echo "vLLM models:"
curl -sS "$VLLM_BASE_URL/models" -H "Authorization: Bearer $API_KEY"
echo

