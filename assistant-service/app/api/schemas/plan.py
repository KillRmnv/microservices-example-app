"""DTOs for the LLM plan stage and the extended query response."""
from __future__ import annotations

from pydantic import BaseModel

from .contract import StateContract


class PlanRequest(BaseModel):
    contract: StateContract


class QueryResponse(BaseModel):
    contract: StateContract
    reasoning_used: bool = False
    complex: bool = False
    intent: str = "event_search"
    supported: bool = True
    reply: str | None = None
