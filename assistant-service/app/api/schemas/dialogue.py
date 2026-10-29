"""Dialogue DTOs (response shape consumed by the frontend)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from .contract import StateContract

MessageKind = Literal["assistant", "filters", "results", "plan", "weather"]


class ResultCard(BaseModel):
    event_id: str
    title: str
    meta: str
    price: str
    source: str = ""


class PlanStep(BaseModel):
    time: str = "—"
    title: str = ""
    detail: str = ""
    source: str = "assistant"


class ChatMessage(BaseModel):
    kind: MessageKind
    text: str
    results: list[ResultCard] | None = None
    weather: str | None = None
    plan: list[PlanStep] | None = None


class DialogResponse(BaseModel):
    contract: StateContract
    messages: list[ChatMessage]
