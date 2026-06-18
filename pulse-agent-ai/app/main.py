from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .agent import PulseAgent
from .analytics import AnalyticsService
from .config import ALLOWED_ORIGINS, LLM_BASE_URL, LLM_MODEL, PROJECT_ROOT
from .database import ensure_database
from .rag import RagRetriever
from .schemas import AgentQuery, RagSearchQuery


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
    return agent.answer(payload.query)


@app.post("/api/rag/search")
def search_rag(payload: RagSearchQuery) -> dict:
    return {"results": rag.search(payload.query, payload.top_k)}


@app.get("/api/event-plan")
def event_plan(event_type: str = "sports", expected_attendance: int = 200, duration_hr: float = 2.5) -> dict:
    return analytics.recommend_event_plan(event_type, expected_attendance, duration_hr)
