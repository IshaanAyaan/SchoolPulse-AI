from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = PROJECT_ROOT.parent


def resolve_project_path(value: str | None, default: str) -> Path:
    candidate = value or default
    path = Path(candidate)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def default_database_path() -> Path:
    configured = os.getenv("DATABASE_PATH")
    if configured:
        return resolve_project_path(configured, "data/processed/schoolprint_ai.db")
    if os.getenv("VERCEL"):
        return Path("/tmp/schoolprint_ai.db")
    return resolve_project_path(None, "data/processed/schoolprint_ai.db")


def parse_csv_env(name: str, default: str = "") -> list[str]:
    raw = os.getenv(name, default)
    return [item.strip() for item in raw.split(",") if item.strip()]


DATABASE_PATH = default_database_path()
RAG_INDEX_PATH = resolve_project_path(os.getenv("RAG_INDEX_PATH"), "rag_index/index.joblib")

LLM_BASE_URL = os.getenv("LLM_BASE_URL", "").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "google/gemma-4-12B-it")
LLM_API_KEY = os.getenv("LLM_API_KEY", "EMPTY")
ALLOWED_ORIGINS = parse_csv_env("ALLOWED_ORIGINS", "*")

ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY", "").strip()
ELEVENLABS_API_BASE_URL = os.getenv("ELEVENLABS_API_BASE_URL", "https://api.elevenlabs.io/v1").rstrip("/")
ELEVENLABS_VOICE_ID = os.getenv("ELEVENLABS_VOICE_ID", "JBFqnCBsd6RMkjVDRZzb")
ELEVENLABS_TTS_MODEL = os.getenv("ELEVENLABS_TTS_MODEL", "eleven_flash_v2_5")
ELEVENLABS_STT_MODEL = os.getenv("ELEVENLABS_STT_MODEL", "scribe_v2")

SYNTHETIC_DIR = PROJECT_ROOT / "data" / "synthetic"
MODELS_DIR = PROJECT_ROOT / "models"
