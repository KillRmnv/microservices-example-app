"""DTOs for the LLM structure stage."""
from __future__ import annotations

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    language: str | None = None
    session_id: str | None = None
    force_reasoning: bool | None = None
