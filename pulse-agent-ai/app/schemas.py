from __future__ import annotations

from pydantic import BaseModel, Field


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
