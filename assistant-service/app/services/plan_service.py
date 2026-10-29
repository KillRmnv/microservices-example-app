"""Plan stage: search hits -> an evening itinerary (LLM with reasoning).

Unlike structure (slot extraction, no-think), planning is genuinely
multi-step: pick compatible stops, respect times/budget/weather, order them.
It runs only on explicit request ("Собрать план"), async from the fast lane,
so minutes of reasoning don't block normal search turns.
"""
from __future__ import annotations

import json
import logging

from ..api.schemas.contract import StateContract, sanitize
from ..api.schemas.dialogue import ChatMessage, DialogResponse
from ..clients.llm.base import LLMProvider
from ..core.config import Settings
from ..errors import UpstreamError
from .dialogue_service import DialogueService

log = logging.getLogger(__name__)

PROMPT = """Ты — составитель вечернего плана досуга. Сначала кратко рассуди
(совместимость по времени, бюджет, погода), затем верни ТОЛЬКО JSON:
{{"summary": "одно предложение", "steps": [
  {{"time": "19:00", "title": "...", "detail": "место · цена", "source": "..."}}]}}
Правила: 2–4 шага; время — из данных кандидатов, не выдумывай; порядок
хронологический; уложись в бюджет {budget}; город {city}; погода: {weather}.
"""

MAX_CANDIDATES = 8


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


class PlanService:
    def __init__(self, provider: LLMProvider, dialogue: DialogueService,
                 settings: Settings) -> None:
        self._provider = provider
        self._dialogue = dialogue
        self._settings = settings

    async def build_plan(self, contract: StateContract) -> DialogResponse:
        clean = sanitize(contract)
        language = clean.semantic_payload.language or self._settings.default_language
        ruled = self._dialogue.apply_rules(clean, language)
        if ruled.needs_clarification:
            text = (ruled.clarification_prompt
                    or "Уточните дату и условия — тогда соберу план.")
            self._dialogue.record_run(ruled, 0)
            return DialogResponse(contract=ruled,
                                  messages=[ChatMessage(kind="assistant",
                                                        text=text)])
        response = await self._dialogue.search_turn(ruled)
        results = [message for message in response.messages
                   if message.kind == "results" and message.results]
        if not results:
            return response
        cards = results[0].results or []
        weather = next((message.text for message in response.messages
                        if message.kind == "weather"), "нет данных")
        budget = (ruled.hard_filters.budget.max_price_per_person
                  if ruled.hard_filters.budget else None)
        candidates = "\n".join(
            f"{index + 1}. {card.title} | {card.meta} | {card.price}"
            for index, card in enumerate(cards[:MAX_CANDIDATES]))
        system = PROMPT.format(
            budget=(f"до {budget}" if budget else "без ограничений"),
            city=ruled.hard_filters.location.city or self._settings.default_city,
            weather=weather)
        raw = await self._provider.complete(
            system=system, user=candidates, json_mode=True,
            max_tokens=self._settings.llm_max_tokens)
        data = _extract_json(raw)
        steps = data.get("steps")
        if not isinstance(steps, list) or not steps:
            raise UpstreamError("LLM вернула план без шагов")
        plan = [{"time": str(step.get("time", "—")),
                 "title": str(step.get("title", "")),
                 "detail": str(step.get("detail", "")),
                 "source": str(step.get("source", "assistant"))}
                for step in steps if isinstance(step, dict)]
        plan = [step for step in plan if step["title"]]
        if not plan:
            raise UpstreamError("LLM вернула план без шагов")
        summary = (data.get("summary")
                   or "Готовый план вечера — проверьте шаги и подтвердите.")
        log.info("plan stage: %d candidates -> %d steps", len(cards), len(plan))
        message = ChatMessage(kind="plan", text=str(summary), plan=plan)
        return DialogResponse(contract=response.contract,
                              messages=[*response.messages, message])
