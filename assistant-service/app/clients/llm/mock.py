"""Deterministic offline backend ("mock"): no network, valid contract fragment."""
from __future__ import annotations

from .base import LLMProvider

MOCK_CONTRACT = (
    '{"dialogue_action": "ask_clarification", '
    '"needs_clarification": true, '
    '"clarification_prompt": "Mock provider: please specify date and time"}'
)


class MockProvider(LLMProvider):
    name = "mock"

    async def complete(self, *, system: str, user: str,
                       json_mode: bool = False, max_tokens: int = 512) -> str:
        return MOCK_CONTRACT
