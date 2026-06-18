from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field
from pydantic import field_validator


class AgentQuery(BaseModel):
    query: str = Field(..., min_length=2)
    voice_mode: bool = False
    language: str = Field(default="en-US", min_length=2, max_length=12)


class RagSearchQuery(BaseModel):
    query: str = Field(..., min_length=2)
    top_k: int = Field(default=5, ge=1, le=10)


class ActionCard(BaseModel):
    module: str
    priority: str
    title: str
    location: str
    recommendation: str
    evidence: str
    estimated_impact: str
    confidence: float
    human_check: str


class AgentResponse(BaseModel):
    answer: str
    action_cards: list[ActionCard]
    citations: list[dict]
    used_llm: bool


class VoiceSpeakRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    language: str = Field(default="en-US", min_length=2, max_length=12)
    voice_id: str | None = Field(default=None, max_length=80)


class WaterSensorReading(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=80)
    location: str = Field(default="Hackathon tank demo", min_length=1, max_length=120)
    recorded_at: datetime | None = None
    arduino_sequence: int | None = Field(default=None, ge=0)
    uptime_ms: int | None = Field(default=None, ge=0)
    distance_cm: float = Field(..., ge=0, le=400)
    fill_depth_cm: float = Field(..., ge=0, le=400)
    tank_depth_cm: float = Field(..., gt=0, le=400)
    fill_percent: float = Field(..., ge=0, le=100)
    status: str = Field(default="normal", min_length=3, max_length=20)
    confidence: float = Field(default=0.8, ge=0, le=1)
    sample_count: int = Field(default=1, ge=0, le=50)
    spread_cm: float | None = Field(default=None, ge=0, le=50)
    reading_source: str = Field(default="arduino-serial", min_length=2, max_length=40)

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"normal", "watch", "low", "critical", "sensor_fault"}
        if normalized not in allowed:
            raise ValueError(f"status must be one of: {', '.join(sorted(allowed))}")
        return normalized
