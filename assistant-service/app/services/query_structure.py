"""Structure stage: free-form RU request -> dialogue state contract (LLM)."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from ..api.schemas.contract import ANONYMOUS_SESSION, StateContract, sanitize
from ..clients.llm.base import LLMProvider
from ..core.config import Settings
from ..errors import UpstreamError
from .query_complexity import classify

log = logging.getLogger(__name__)

PROMPT = """Ты — парсер запросов к городской афише. Думай кратко, затем верни ТОЛЬКО JSON:
{{
  "dialogue_action": "search",
  "hard_filters": {{
    "datetime": {{"start": "ISO-8601 или null", "raw_expression": "..."}},
    "location": {{"city": "{city}"}},
    "category": ["concert"],
    "party_size": 2,
    "budget": null
  }},
  "semantic_payload": {{"vector_query": "...", "language": "{language}"}}
}}
Правила: сегодня {today}, пояс {timezone}; относительные даты ("завтра",
"в субботу") переводи в ISO; category только из concert, theatre, exhibition,
film, sport, kids, other; budget — {{"max_price_per_person": N}} только если
сумма названа; vector_query — смысл запроса без дат, цен и города.
"""


def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise UpstreamError("LLM вернула пустой ответ")
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise UpstreamError("LLM вернула не JSON")
    try:
        data = json.loads(text[start:end + 1])
    except ValueError as exc:
        raise UpstreamError(f"LLM вернула некорректный JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise UpstreamError("LLM вернула не объект JSON")
    return data


def _normalise(data: dict, settings: Settings) -> dict:
    """LLMs omit or null nested objects; make the shape valid before pydantic."""
    actions = {"search", "update_filters", "confirm_booking", "ask_clarification"}
    if data.get("dialogue_action") not in actions:
        data["dialogue_action"] = "search"
    hard = data.get("hard_filters")
    if not isinstance(hard, dict):
        hard = {}
    location = hard.get("location")
    if not isinstance(location, dict):
        location = {"city": settings.default_city}
    hard["location"] = location
    datetime_filter = hard.get("datetime")
    hard["datetime"] = datetime_filter if isinstance(datetime_filter, dict) else None
    budget = hard.get("budget")
    hard["budget"] = budget if isinstance(budget, dict) else None
    category = hard.get("category")
    if isinstance(category, str):
        category = [category]
    hard["category"] = category if isinstance(category, list) else []
    try:
        hard["party_size"] = int(hard.get("party_size") or settings.default_party_size)
    except (TypeError, ValueError):
        hard["party_size"] = settings.default_party_size
    data["hard_filters"] = hard
    negative = data.get("negative_filters")
    data["negative_filters"] = negative if isinstance(negative, dict) else {}
    payload = data.get("semantic_payload")
    if not isinstance(payload, dict):
        payload = {}
    if not isinstance(payload.get("vector_query"), str):
        payload["vector_query"] = ""
    data["semantic_payload"] = payload
    context = data.get("context_state")
    data["context_state"] = context if isinstance(context, dict) else {}
    return data


class QueryStructureService:
    def __init__(self, provider: LLMProvider, settings: Settings,
                 *, max_tokens: int | None = None,
                 reasoning_provider: LLMProvider | None = None) -> None:
        self._provider = provider
        self._settings = settings
        self._max_tokens = max_tokens or settings.llm_structure_max_tokens
        self._reasoning = reasoning_provider

    async def parse(self, query: str, language: str | None = None,
                    session_id: str | None = None,
                    force_reasoning: bool | None = None) -> StateContract:
        contract, _, _ = await self.parse_meta(
            query, language=language, session_id=session_id,
            force_reasoning=force_reasoning)
        return contract

    async def parse_meta(self, query: str, language: str | None = None,
                         session_id: str | None = None,
                         force_reasoning: bool | None = None
                         ) -> tuple[StateContract, bool, bool]:
        """Parse the request; also report (reasoning_used, complex)."""
        language = language or self._settings.default_language
        complexity = classify(query, self._settings)
        use_reasoning = (force_reasoning if force_reasoning is not None
                         else complexity.complex)
        provider = (self._reasoning if use_reasoning and self._reasoning
                    is not None else self._provider)
        reasoning_used = provider is self._reasoning
        max_tokens = (self._settings.llm_max_tokens if reasoning_used
                      else self._max_tokens)
        validate = self._settings.default_timezone
        today = datetime.now(ZoneInfo(validate)).date().isoformat()
        system = PROMPT.format(city=self._settings.default_city,
                               timezone=validate, language=language,
                               today=today)
        raw = await provider.complete(
            system=system, user=query.strip(), json_mode=True,
            max_tokens=max_tokens)
        data = _normalise(_extract_json(raw), self._settings)
        try:
            contract = StateContract.model_validate(data)
        except ValueError as exc:
            raise UpstreamError(f"LLM вернула контракт неверной формы: {exc}") from exc
        contract.context_state.session_id = session_id or ANONYMOUS_SESSION
        contract.context_state.turn_count = 1
        contract.semantic_payload.language = language
        if contract.dialogue_action == "search" and not contract.semantic_payload.vector_query:
            contract.semantic_payload.vector_query = query.strip()[:300]
        log.info("structure stage: %s -> categories=%s datetime=%s reasoning=%s",
                 query[:80], contract.hard_filters.category,
                 contract.hard_filters.datetime.start if contract.hard_filters.datetime else None,
                 reasoning_used)
        return sanitize(contract), reasoning_used, complexity.complex
