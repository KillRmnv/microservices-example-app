"""DTOs for the LLM plan stage and the extended query response."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .contract import StateContract


class PlanRequest(BaseModel):
    contract: StateContract
    # Earlier search contracts from the same chat, so "потом покушать" does
    # not erase the animal/concert part of the evening.
    contexts: list[StateContract] = Field(default_factory=list)


class QueryResponse(BaseModel):
    contract: StateContract
    reasoning_used: bool = False
    complex: bool = False
    intent: str = "event_search"
    supported: bool = True
    reply: str | None = None
