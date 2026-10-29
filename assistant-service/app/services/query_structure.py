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

log = logging.getLogger(__name__)

PROMPT = """\
Ты — парсер запросов к городской афише. Верни ТОЛЬКО JSON без пояснений.
Схема:
{{
  "dialogue_action": "search",
  "hard_filters": {{
    "datetime": {{"start": "ISO-8601 или null", "end": null,
                 "raw_expression": "как сказал пользователь или null",
                 "is_relative": false}},
    "location": {{"city": "{city}", "districts": [], "landmarks": []}},
    "category": ["concert"],
    "party_size": 2,
    "budget": {{"max_price_per_person": 50}} или null,
    "amenities_required": []
  }},
  "negative_filters": {{"exclude_categories": [], "exclude_tags": [],
                        "exclude_districts": []}},
  "semantic_payload": {{"vector_query": "смысл запроса без дат и цифр",
                       "language": "{language}"}},
  "context_state": {{"turn_count": 1, "session_id": ""}}
}}
Правила:
- Сегодня {today}, часовой пояс {timezone}. Относительные даты ("завтра",
  "в субботу") превращай в конкретный ISO start; если дата не названа — null.
- category только из: concert, theatre, exhibition, film, sport, kids, other.
- budget — на одного человека и ТОЛЬКО если сумма названа; иначе null.
- Не выдумывай бюджет, город, дату или категорию, которых нет в запросе.
- vector_query — короткая фраза для поиска (жанр, атмосфера, название),
  без дат, цен и слов «Минск», «куда сходить».
- Если запрос не про поиск (например, подтверждение) — dialogue_action
  "confirm_booking" или "ask_clarification".
"""

EXAMPLE = """\
Запрос: тихий джаз в субботу
Ответ: {"dialogue_action":"search","hard_filters":{"datetime":{"start":"2026-10-31T19:00:00","end":null,"raw_expression":"в субботу","is_relative":true},"location":{"city":"Минск","districts":[],"landmarks":[]},"category":["concert"],"party_size":2,"budget":null,"amenities_required":[]},"negative_filters":{"exclude_categories":[],"exclude_tags":[],"exclude_districts":[]},"semantic_payload":{"vector_query":"тихий джаз","language":"ru"},"context_state":{"turn_count":1,"session_id":""}}
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


class QueryStructureService:
    def __init__(self, provider: LLMProvider, settings: Settings) -> None:
        self._provider = provider
        self._settings = settings

    async def parse(self, query: str, language: str | None = None,
                    session_id: str | None = None) -> StateContract:
        language = language or self._settings.default_language
        validate = self._settings.default_timezone
        today = datetime.now(ZoneInfo(validate)).date().isoformat()
        system = PROMPT.format(city=self._settings.default_city,
                               timezone=validate, language=language,
                               today=today) + "\n" + EXAMPLE
        raw = await self._provider.complete(
            system=system, user=query.strip(), json_mode=True, max_tokens=512)
        data = _extract_json(raw)
        contract = StateContract.model_validate(data)
        contract.context_state.session_id = session_id or ANONYMOUS_SESSION
        contract.context_state.turn_count = 1
        contract.semantic_payload.language = language
        if contract.dialogue_action == "search" and not contract.semantic_payload.vector_query:
            contract.semantic_payload.vector_query = query.strip()[:300]
        log.info("structure stage: %s -> categories=%s datetime=%s",
                 query[:80], contract.hard_filters.category,
                 contract.hard_filters.datetime.start if contract.hard_filters.datetime else None)
        return sanitize(contract)
