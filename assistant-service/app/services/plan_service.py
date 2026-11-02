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

PROMPT = """Ты — составитель плана досуга. Сначала кратко рассуди
(совместимость по времени, бюджет, погода), затем верни ТОЛЬКО JSON:
{{"summary": "одно предложение", "steps": [
  {{"candidate": 1, "time": "19:00", "title": "...", "detail": "место · цена", "source": "..."}}]}}
Правила: 2–4 шага; candidate — номер кандидата из списка. Окно плана:
{window_start} — {window_end}; все шаги должны быть внутри него. Кандидаты
собраны из всей беседы: [event] — событие, [venue] — место. Если среди
кандидатов есть событие из предыдущей темы, обязательно включи хотя бы одно
событие в план, а места добавь вокруг него. Если у события end_at позже
start_at, оно идёт несколько дней: дата плана внутри периода значит, что
событие доступно, не исключай его из-за даты начала. Время одиночного
события бери из start_at; для многодневного не используй start_at как время
визита — поставь время внутри окна и отметь "сеанс уточняется". Если времени
нет — пиши "уточняется", не выдумывай.
Для места без времени можно предложить время внутри окна. Название заведения
не превращай в активность: "Гуляем в ГУМе" — это кафе, а не прогулка.
Порядок хронологический; уложись в бюджет {budget}; город {city};
погода: {weather}. Не называй план вечерним, если в контракте время не
вечернее; это план на указанный период."""

MAX_CANDIDATES = 10


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
                 settings: Settings, *,
                 fallback_provider: LLMProvider | None = None) -> None:
        self._provider = provider
        self._fallback = fallback_provider
        self._dialogue = dialogue
        self._settings = settings

    async def _model_plan(self, system: str, user: str) -> tuple[list[dict], str]:
        """Ask the reasoning model, then retry without thinking, then give up.

        Ling can burn the whole budget on reasoning and return empty content;
        a no-think retry is cheap and usually yields the JSON.
        """
        providers = [self._provider]
        if self._fallback is not None and self._fallback is not self._provider:
            providers.append(self._fallback)
        last_error: Exception | None = None
        for provider in providers:
            try:
                raw = await provider.complete(
                    system=system, user=user, json_mode=True,
                    max_tokens=self._settings.llm_plan_max_tokens)
                data = _extract_json(raw)
                steps = data.get("steps")
                if not isinstance(steps, list) or not steps:
                    raise UpstreamError("LLM вернула план без шагов")
                plan = [{"candidate": int(step.get("candidate") or 0),
                         "time": str(step.get("time", "—")),
                         "title": str(step.get("title", "")),
                         "detail": str(step.get("detail", "")),
                         "source": str(step.get("source", "assistant"))}
                        for step in steps if isinstance(step, dict)]
                plan = [step for step in plan if step["title"]]
                if not plan:
                    raise UpstreamError("LLM вернула план без шагов")
                summary = str(data.get("summary")
                              or "Готовый план досуга — проверьте шаги и подтвердите.")
                return plan, summary
            except Exception as exc:  # noqa: BLE001 — retry/fallback by design
                last_error = exc
                log.warning("plan provider %s failed: %s", provider.name, exc)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _fallback_steps(cards: list) -> list[dict]:
        """Deterministic itinerary from the best cards (no invented places)."""
        return [{"candidate": index + 1, "time": "—", "title": card.title,
                 "detail": " · ".join(part for part in (card.meta, card.price)
                                      if part),
                 "source": card.source or "assistant"}
                for index, card in enumerate(cards[:3])]

    @staticmethod
    def _attach_cards(plan: list[dict], cards: list) -> list[dict]:
        """Map model steps back to real cards; never trust bare titles."""
        def norm(value: str) -> str:
            return "".join(ch for ch in value.casefold() if ch.isalnum())

        by_title = {norm(card.title): card for card in cards}
        for step in plan:
            card = None
            index = step.get("candidate")
            if isinstance(index, int) and 1 <= index <= len(cards):
                card = cards[index - 1]
            if card is None:
                card = by_title.get(norm(step["title"]))
            if card is not None:
                step.update({
                    "kind": card.kind,
                    "detail_id": card.detail_id,
                    "event_id": card.event_id,
                    "bookable": bool(card.kind == "event"
                                     and card.event_id.isdigit()),
                    "title": step["title"] or card.title,
                    "source": card.source or step.get("source") or "assistant",
                })
            step.pop("candidate", None)
        return plan

    @staticmethod
    def _contract_key(contract: StateContract) -> tuple:
        hard = contract.hard_filters
        dt = hard.datetime
        return (
            contract.intent,
            tuple(hard.category),
            tuple(hard.themes),
            contract.semantic_payload.vector_query,
            dt.start if dt else None,
            dt.any if dt else False,
            hard.location.city,
            hard.party_size,
        )

    @staticmethod
    def _dedupe_cards(cards: list) -> list:
        seen: set[tuple] = set()
        unique = []
        for card in cards:
            key = (card.kind, card.detail_id or f"{card.title}|{card.source}")
            if key in seen:
                continue
            seen.add(key)
            unique.append(card)
        return unique

    @staticmethod
    def _balanced(cards: list, limit: int) -> list:
        """Keep events and places represented when both are in the chat."""
        events = [card for card in cards if card.kind == "event"]
        venues = [card for card in cards if card.kind == "venue"]
        mixed: list = []
        while len(mixed) < limit and (events or venues):
            if events:
                mixed.append(events.pop(0))
            if len(mixed) < limit and venues:
                mixed.append(venues.pop(0))
        return mixed

    @staticmethod
    def _event_step(card) -> dict:
        time = "уточняется"
        if len(card.start_at) >= 16 and "T" in card.start_at:
            time = card.start_at[11:16]
        detail = " · ".join(part for part in (card.meta, card.price) if part)
        return {"time": time, "title": card.title, "detail": detail,
                "source": card.source or "assistant"}

    @staticmethod
    def _period(card) -> str:
        start = card.start_at or "время не указано"
        if card.end_at and card.end_at != card.start_at:
            return f"{start} — {card.end_at}"
        return start

    @staticmethod
    def _is_spanning(card, plan_day: str | None) -> bool:
        if not plan_day or not card.start_at or not card.end_at:
            return False
        start_day = card.start_at[:10]
        end_day = card.end_at[:10]
        return bool(end_day > start_day and start_day < plan_day <= end_day)

    @staticmethod
    def _sort_plan(plan: list[dict]) -> list[dict]:
        def key(step: dict) -> tuple[int, int]:
            value = str(step.get("time") or "")
            if len(value) >= 5 and value[2] == ":":
                try:
                    return int(value[:2]), int(value[3:5])
                except ValueError:
                    pass
            return 99, 99
        return sorted(plan, key=key)

    async def _cards_for(self, contract: StateContract) -> tuple:
        clean = sanitize(contract)
        language = clean.semantic_payload.language or self._settings.default_language
        ruled = self._dialogue.apply_rules(clean, language)
        if ruled.needs_clarification:
            return ruled, None
        response = await self._dialogue.search_turn(ruled)
        cards = [
            card
            for message in response.messages
            if message.kind == "results"
            for card in (message.results or [])
        ]
        return ruled, (response, cards)

    async def build_plan(self, contract: StateContract,
                         contexts: list[StateContract] | None = None
                         ) -> DialogResponse:
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
        # "Потом покушать" replaces the topic. The plan still needs the
        # earlier animal/concert stop, so search every contract from the chat.
        queue: list[StateContract] = []
        seen: set[tuple] = set()
        for ctx in [contract, *(contexts or [])]:
            key = self._contract_key(ctx)
            if key in seen:
                continue
            seen.add(key)
            queue.append(ctx)
        responses = []
        cards: list = []
        primary = None
        for ctx in queue:
            ctx_ruled, found = await self._cards_for(ctx)
            if found is None:
                continue
            response, ctx_cards = found
            responses.append(response)
            if primary is None:
                primary = response
            cards.extend(ctx_cards)
        cards = self._dedupe_cards(cards)
        if not cards:
            if primary is not None:
                return primary
            return DialogResponse(
                contract=ruled,
                messages=[ChatMessage(
                    kind="assistant",
                    text="По этим условиям ничего не нашлось — смягчите фильтры "
                         "или уточните дату.")],
            )
        response = primary or responses[0]
        weather = next((message.text for message in response.messages
                        if message.kind == "weather"), "нет данных")
        budget = (ruled.hard_filters.budget.max_price_per_person
                  if ruled.hard_filters.budget else None)
        date_filter = ruled.hard_filters.datetime
        if date_filter is not None and not date_filter.any:
            window_start = date_filter.start or "не задано"
            window_end = date_filter.end or date_filter.start or "не задано"
        else:
            window_start = window_end = "не задано"
        plan_day = (window_start[:10]
                    if len(window_start) >= 10 and window_start[4] == "-"
                    else None)
        window_time = (window_start[11:16]
                       if len(window_start) >= 16 and "T" in window_start
                       else None)
        selected = self._balanced(cards, MAX_CANDIDATES)
        candidates = "\n".join(
            f"{index + 1}. [{card.kind}] {card.title} | {card.meta} | {card.price}"
            f" | {self._period(card)}"
            for index, card in enumerate(selected))
        system = PROMPT.format(
            budget=(f"до {budget}" if budget else "без ограничений"),
            city=ruled.hard_filters.location.city or self._settings.default_city,
            weather=weather,
            window_start=window_start,
            window_end=window_end)
        summary = "Готовый план досуга — проверьте шаги и подтвердите."
        try:
            plan, summary = await self._model_plan(system, candidates)
        except Exception as exc:  # noqa: BLE001 — deterministic fallback
            log.warning("plan stage fell back to cards: %s", exc)
            plan = self._fallback_steps(selected)
            summary = ("Модель не ответила — вот лучшие варианты из поиска. "
                       "Время и наличие уточните на странице события.")
        if not plan:
            raise UpstreamError("LLM вернула план без шагов")
        plan = self._attach_cards(plan, selected)
        events = [card for card in selected if card.kind == "event"]
        if (len(queue) > 1 and events
                and not any(step.get("kind") == "event" for step in plan)):
            # The model followed only the latest "покушать" request; keep the
            # earlier event as the anchor of the evening.
            extra = self._attach_cards([self._event_step(events[0])], selected)
            plan = [*plan, *extra][:4]
        by_detail = {card.detail_id: card for card in selected}
        for step in plan:
            card = by_detail.get(step.get("detail_id") or "")
            if card is not None and self._is_spanning(card, plan_day):
                step["time"] = window_time or "уточняется"
                suffix = "сеанс уточняется"
                if suffix not in step.get("detail", ""):
                    detail = " · ".join(part for part in
                                        (step.get("detail"), suffix) if part)
                    step["detail"] = detail
        plan = self._sort_plan(plan)
        log.info("plan stage: %d contexts -> %d candidates -> %d steps",
                 len(queue), len(selected), len(plan))
        message = ChatMessage(kind="plan", text=summary, plan=plan)
        return DialogResponse(contract=response.contract,
                              messages=[*response.messages, message])
