from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from .agent import PulseAgent
from .analytics import AnalyticsService
from .config import ALLOWED_ORIGINS, ELEVENLABS_API_KEY, LLM_BASE_URL, LLM_MODEL, PROJECT_ROOT
from .database import ensure_database
from .rag import RagRetriever
from .schemas import AgentQuery, RagSearchQuery, VoiceSpeakRequest
from .voice import ElevenLabsVoiceService


app = FastAPI(
    title="Pulse Agent AI",
    description="SchoolPrint AI backend for RAG, recommendations, energy/event intelligence, and voice-agent responses.",
    version="0.1.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

static_dir = PROJECT_ROOT / "app" / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")

analytics = AnalyticsService()
agent = PulseAgent()
rag = RagRetriever()
voice = ElevenLabsVoiceService()


@app.on_event("startup")
def startup() -> None:
    ensure_database()


@app.get("/")
def dashboard() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "pulse-agent-ai",
        "llm_configured": bool(LLM_BASE_URL),
        "llm_model": LLM_MODEL,
        "voice_configured": bool(ELEVENLABS_API_KEY),
    }


@app.get("/api/overview")
def overview() -> dict:
    return analytics.overview()


@app.get("/api/energy")
def energy() -> dict:
    return analytics.energy_summary()


@app.get("/api/water")
def water() -> dict:
    return analytics.water_summary()


@app.get("/api/waste")
def waste() -> dict:
    return analytics.waste_summary()


@app.get("/api/events")
def events() -> dict:
    frames = analytics.load_frames()
    return analytics.events_summary(frames.events, frames.transport)


@app.post("/api/agent/query")
def query_agent(payload: AgentQuery) -> dict:
    return agent.answer(payload.query, language=payload.language)


@app.get("/api/voice/status")
def voice_status() -> dict:
    return voice.status()


@app.post("/api/voice/speak")
def speak(payload: VoiceSpeakRequest) -> Response:
    try:
        audio = voice.speak(payload.text, language=payload.language, voice_id=payload.voice_id)
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Voice generation is unavailable.") from exc
    return Response(content=audio.content, media_type=audio.media_type)


@app.post("/api/voice/transcribe")
async def transcribe_voice(
    file: UploadFile = File(...),
    language: str = Query(default="en-US", min_length=2, max_length=12),
) -> dict:
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="No audio received.")
    try:
        return voice.transcribe(
            audio_bytes,
            filename=file.filename or "voice.webm",
            content_type=file.content_type or "audio/webm",
            language=language,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Voice transcription is unavailable.") from exc


@app.post("/api/rag/search")
def search_rag(payload: RagSearchQuery) -> dict:
    return {"results": rag.search(payload.query, payload.top_k)}


@app.get("/api/event-plan")
def event_plan(event_type: str = "sports", expected_attendance: int = 200, duration_hr: float = 2.5) -> dict:
    return analytics.recommend_event_plan(event_type, expected_attendance, duration_hr)
