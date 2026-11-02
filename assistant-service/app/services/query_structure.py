"""Structure stage: free-form RU request -> dialogue state contract (LLM)."""
from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from zoneinfo import ZoneInfo

from ..api.schemas.contract import ANONYMOUS_SESSION, StateContract, sanitize
from ..clients.llm.base import LLMProvider
from ..core.config import Settings
from ..errors import UpstreamError
from ..models import intent as intents
from .query_complexity import classify

log = logging.getLogger(__name__)

KNOWN_CATEGORIES = {
    "concert", "theatre", "exhibition", "film", "sport", "kids", "other",
}

PROMPT = """Ты — классификатор и парсер запросов к городской афише и справочнику мест. Думай кратко, затем верни ТОЛЬКО JSON:
{{
  "intent": "find_events",
  "dialogue_action": "search",
  "hard_filters": {{
    "datetime": {{"start": "ISO-8601 или null", "end": "ISO-8601 или null", "raw_expression": "...", "any": false}},
    "location": {{"city": null, "any": false}},
    "category": ["concert"],
    "themes": ["classical"],
    "party_size": null,
    "budget": null
  }},
  "semantic_payload": {{"vector_query": "...", "language": "{language}"}}
}}
Правила: сегодня {today}, пояс {timezone}; относительные даты ("завтра",
"в субботу") переводи в ISO; диапазоны ("02.11-05.11", "с 2 по 5 ноября")
переводи в start/end. Если пользователь говорит "не важно", "любая дата",
"без даты" — datetime.any=true, start=null. Если город/цена/компания не
названы — city=null/any=false, budget=null, party_size=null; не выдумывай
Минск, цену или 2 человека. category — список подходящих категорий из
concert, theatre, exhibition, film, sport, kids, other. Для классики это
["concert","theatre"], для балета/оперы — ["theatre"]. Для общих запросов
("что-нибудь", "любые события") category — []; themes — жанровые темы,
например ["classical"], ["jazz"], ["rock"], ["beer"], ["fitness"]; budget —
только если сумма названа; vector_query — только тема, жанр или атмосфера.
Не включай в vector_query дату, цену, город, размер компании и служебные
слова ("найди", "что-нибудь", "на компанию"); если темы нет — "".

intent — главное решение, выбери ровно одно:
- find_events — пользователь ищет мероприятия без явной категории;
- find_event_concert, find_event_theatre, find_event_exhibition,
  find_event_film, find_event_sport, find_event_kids, find_event_other —
  если категория названа явно;
- find_venues — пользователь ищет место/заведение без явной рубрики;
- find_venue_bar, find_venue_cafe, find_venue_restaurant,
  find_venue_cinema, find_venue_theatre, find_venue_exhibition,
  find_venue_gym, find_venue_library — если тип места назван явно
  (спортзал/фитнес — gym, почитать/библиотека/книжный — library);
- both — просит и события, и места;
- plan — просит собрать план/маршрут вечера;
- booking — просит забронировать/купить билет;
- weather — спрашивает только погоду;
- capabilities — спрашивает, что ты умеешь, или здоровается;
- unsupported — запрос не про досуг, еду, места, события или город.
"Место, чтобы выпить с друзьями" и "где можно пивка попить" — find_venue_bar.
"Найди что-нибудь с друзьями почиллить", "куда сходить", "что есть
интересного" без явного события/места — both (события + места).
"Потом хочу почитать" — find_venue_library, тема books/reading.
"Покажи концерты", "что есть по театру", "выставки" — соответствующий
find_event_* с категорией; не оставляй category пустым.
"Концерт в баре" — find_event_concert, если главное событие.
"зоопарк", "дельфинарий", "океанариум", "с животными" — это события/досуг:
find_events или both, не find_venue_*, если нет явного "место", "кафе" или
"ресторан". category для них — [] (не "other"), themes — ["animals"],
vector_query "животные, зоопарк, дельфинарий, океанариум, контактный зоопарк,
питомцы".
"цена неважна", "без бюджета" — budget.any=true; "2-4 человек" —
party_size=4; "не важно" — datetime.any=true, city=null/any=true,
budget.any=true, party_size=0.
"""


def _extract_json(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        raise UpstreamError("LLM вернула пустой ответ")
    # Models often wrap JSON in a markdown fence or add a short preface.
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise UpstreamError("LLM вернула не JSON")
    candidate = text[start:end + 1]
    # Trailing commas are the most common near-valid JSON failure.
    candidate = re.sub(r",(\s*[}\]])", r"\1", candidate)
    try:
        data = json.loads(candidate, strict=False)
    except ValueError as exc:
        raise UpstreamError(f"LLM вернула некорректный JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise UpstreamError("LLM вернула не объект JSON")
    return data


_FILLER_RE = re.compile(
    r"\b(?:найди(?:те)?|подбери(?:те)?|покажи(?:те)?|"
    r"что[- ]нибудь|что[- ]то|что\s+угодно|пожалуйста|пожалуй)\b",
    re.IGNORECASE)
_PARTY_RE = re.compile(
    r"\b(?:на|для)\s+компани\w*(?:\s+из)?(?:\s+\d{1,2})?"
    r"(?:\s+человек\w*)?|\bкомпани\w*\b|\b\d{1,2}\s+человек\w*|"
    r"\bвдво[её]м\b|\bвтро[её]м\b",
    re.IGNORECASE)
_DATE_RE = re.compile(
    r"\b(?:сегодня|завтра|послезавтра|выходн\w*)\b", re.IGNORECASE)

def _clean_vector_query(text: str, city: str) -> str:
    """Strip slots the search already filters on from the semantic query.

    "найди что-нибудь на компанию из 3 человек на завтра" carries no theme;
    leaving it in vector_query makes dense search match "команда"/"человек".
    """
    cleaned = _FILLER_RE.sub(" ", text or "")
    cleaned = _PARTY_RE.sub(" ", cleaned)
    cleaned = _DATE_RE.sub(" ", cleaned)
    if city:
        cleaned = re.sub(rf"\b{re.escape(city)}\w*\b", " ", cleaned,
                         flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return "" if len(cleaned) <= 2 else cleaned[:300]


def _normalise(data: dict, settings: Settings) -> dict:
    """LLMs omit or null nested objects; make the shape valid before pydantic."""
    actions = {"search", "update_filters", "confirm_booking", "ask_clarification"}
    if data.get("dialogue_action") not in actions:
        data["dialogue_action"] = "search"
    data["intent"] = intents.normalize(data.get("intent"))
    hard = data.get("hard_filters")
    if not isinstance(hard, dict):
        hard = {}
    location = hard.get("location")
    if not isinstance(location, dict):
        location = {"city": None, "any": False}
    hard["location"] = location
    datetime_filter = hard.get("datetime")
    hard["datetime"] = datetime_filter if isinstance(datetime_filter, dict) else None
    budget = hard.get("budget")
    hard["budget"] = budget if isinstance(budget, dict) else None
    category = hard.get("category")
    if isinstance(category, str):
        category = [category]
    if isinstance(category, list):
        cleaned = [str(item).strip().lower() for item in category
                   if str(item).strip().lower() in KNOWN_CATEGORIES]
    else:
        cleaned = []
    # Multiple categories are a supported filter (e.g. classics: concert +
    # theatre); keep every known value, deduplicated. "All seven" is just a
    # broad request — no category filter.
    if set(cleaned) >= KNOWN_CATEGORIES:
        cleaned = []
    hard["category"] = list(dict.fromkeys(cleaned))
    themes = hard.get("themes")
    if isinstance(themes, str):
        themes = [themes]
    hard["themes"] = (list(dict.fromkeys(
        str(theme).strip().lower() for theme in themes
        if str(theme).strip())) if isinstance(themes, list) else [])
    # "other" is a catch-all, not a real genre: with a concrete theme it would
    # exclude kids/concert/etc. events that match the theme.
    if hard["category"] == ["other"] and hard["themes"]:
        hard["category"] = []
    try:
        raw_party = hard.get("party_size")
        hard["party_size"] = (None if raw_party is None
                              else 0 if raw_party == 0
                              else int(raw_party))
    except (TypeError, ValueError):
        hard["party_size"] = None
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


CLARIFICATION_PROMPT = """Ты заполняешь только пропущенные параметры поиска.
Ассистент спросил: {slots}. Сегодня {today}, пояс {timezone}.
Верни ТОЛЬКО JSON:
{{
  "topic_changed": false,
  "city": null,
  "city_any": false,
  "budget_any": false,
  "budget_max": null,
  "party_size": null,
  "party_any": false,
  "datetime_any": false,
  "datetime_start": null,
  "datetime_end": null
}}
Правила:
- Заполняй только то, что пользователь явно назвал в этом ответе. Не выдумывай.
- "не важно", "не важен", "любой", "без разницы" — соответствующий *_any=true.
  Если спросили несколько слотов и ответ просто "не важно" — поставь any для всех
  спрошенных слотов.
- "2-3 человек" → party_size=3; "вдвоём" → 2.
- "до 100 рублей" → budget_max=100.
- Даты переводи в ISO-8601 (today={today}, timezone={timezone}).
- topic_changed=true только если пользователь не отвечает, а просит другую тему
  (например, вместо обеда хочет театр). В этом случае остальные поля не заполняй.
Не добавляй комментарии и текст вокруг JSON."""

SLOT_LABELS = {
    "datetime": "дата",
    "city": "город",
    "budget": "бюджет",
    "party": "количество человек",
}


def _clamp_party(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return 0
    return min(20, max(1, number))


def _set_any_slot(hard: dict, slot: str) -> None:
    if slot == "datetime":
        hard["datetime"] = {"any": True, "start": None, "end": None}
    elif slot == "city":
        hard["location"] = {**(hard.get("location") or {}),
                            "city": None, "any": True}
    elif slot == "budget":
        hard["budget"] = {"any": True, "max_price_per_person": None}
    elif slot == "party":
        hard["party_size"] = 0


def _missing_slots(contract: StateContract) -> list[str]:
    """Recompute open slots so old persisted chats still get slot parsing."""
    hard = contract.hard_filters
    slots: list[str] = []
    if intents.spec(contract.intent).scope in ("events", "both"):
        date_filter = hard.datetime
        if date_filter is None or (not date_filter.any
                                   and not date_filter.start):
            slots.append("datetime")
    if not hard.location.any and not hard.location.city:
        slots.append("city")
    budget = hard.budget
    if budget is None or (not budget.any
                          and budget.max_price_per_person is None):
        slots.append("budget")
    if hard.party_size is None:
        slots.append("party")
    return slots


def _fallback_clarification(text: str, previous: StateContract,
                            slots: list[str], settings: Settings) -> StateContract:
    """Last-resort slot fill when the model cannot produce valid JSON."""
    data = previous.model_dump()
    hard = data["hard_filters"]
    lowered = text.casefold()
    filled: set[str] = set()
    city = settings.default_city
    if city and city.casefold() in lowered and "city" in slots:
        hard["location"] = {**hard.get("location", {}),
                            "city": city, "any": False}
        filled.add("city")
    party_range = re.search(r"(\d{1,2})\s*[-–—]\s*(\d{1,2})\s*человек",
                            lowered)
    if party_range and "party" in slots:
        hard["party_size"] = _clamp_party(party_range.group(2))
        filled.add("party")
    else:
        party = re.search(r"нас\s+(\d{1,2})|(\d{1,2})\s+человек", lowered)
        if party and "party" in slots:
            value = party.group(1) or party.group(2)
            hard["party_size"] = _clamp_party(value)
            filled.add("party")
        elif re.search(r"вдво[её]м|двое", lowered) and "party" in slots:
            hard["party_size"] = 2
            filled.add("party")
        elif re.search(r"втро[её]м", lowered) and "party" in slots:
            hard["party_size"] = 3
            filled.add("party")
    budget_max = re.search(
        r"(?:до|не\s+дороже|бюджет)\s+(\d[\d\s]*)", lowered)
    if budget_max and "budget" in slots:
        hard["budget"] = {"max_price_per_person": float(
            budget_max.group(1).replace(" ", ""))}
        filled.add("budget")
    if re.search(r"не\s+важн|все\s+равно|любой|без\s+разницы", lowered):
        for slot in slots:
            if slot not in filled:
                _set_any_slot(hard, slot)
    data["dialogue_action"] = "search"
    data["needs_clarification"] = False
    data["clarification_slots"] = []
    return StateContract.model_validate(data)


def _apply_clarification(data: dict, previous: StateContract,
                         slots: list[str]) -> StateContract | None:
    """Merge a slot-only answer into the previous contract. None = topic change."""
    if data.get("topic_changed"):
        return None
    merged = previous.model_dump()
    hard = merged["hard_filters"]
    city = data.get("city")
    if isinstance(city, str) and city.strip():
        hard["location"] = {**hard.get("location", {}),
                            "city": city.strip(), "any": False}
    if data.get("city_any"):
        hard["location"] = {**hard.get("location", {}),
                            "city": None, "any": True}
    if data.get("budget_any"):
        hard["budget"] = {"any": True, "max_price_per_person": None}
    else:
        budget_max = data.get("budget_max")
        if isinstance(budget_max, (int, float)) and budget_max > 0:
            hard["budget"] = {"max_price_per_person": float(budget_max)}
    party = _clamp_party(data.get("party_size"))
    if party is not None:
        hard["party_size"] = party
    if data.get("party_any"):
        hard["party_size"] = 0
    if data.get("datetime_any"):
        hard["datetime"] = {"any": True, "start": None, "end": None}
    else:
        start = data.get("datetime_start")
        if isinstance(start, str) and start.strip():
            hard["datetime"] = {
                "start": start.strip(),
                "end": (data.get("datetime_end")
                        if isinstance(data.get("datetime_end"), str)
                        else None),
            }
    merged["dialogue_action"] = "search"
    merged["needs_clarification"] = False
    merged["clarification_slots"] = []
    return StateContract.model_validate(merged)


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
                    force_reasoning: bool | None = None,
                    previous: StateContract | None = None) -> StateContract:
        contract, _, _ = await self.parse_meta(
            query, language=language, session_id=session_id,
            force_reasoning=force_reasoning, previous=previous)
        return contract

    async def _ask_json(self, provider: LLMProvider, system: str, query: str,
                        max_tokens: int, attempts: int = 3) -> dict:
        """Ask for JSON, tolerating fences/trailing commas and retrying."""
        last_error: Exception | None = None
        suffix = ""
        for attempt in range(attempts):
            raw = await provider.complete(
                system=system + suffix, user=query.strip(), json_mode=True,
                max_tokens=max_tokens)
            try:
                return _extract_json(raw)
            except UpstreamError as exc:
                last_error = exc
                log.warning("structure JSON invalid (attempt %d/%d): %s",
                            attempt + 1, attempts, exc)
                suffix = ("\nВерни строго валидный JSON без комментариев, "
                          "без markdown и без незакрытых строк.")
        raise UpstreamError(f"LLM вернула некорректный JSON: {last_error}")

    async def parse_meta(self, query: str, language: str | None = None,
                         session_id: str | None = None,
                         force_reasoning: bool | None = None,
                         previous: StateContract | None = None
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

        # An answer to a clarification question only fills the asked slots;
        # it must never replace the topic with the wording of the answer.
        if (previous is not None and previous.needs_clarification
                and (previous.clarification_slots
                     or _missing_slots(previous))):
            slots = [slot for slot in
                     (previous.clarification_slots or _missing_slots(previous))
                     if slot in SLOT_LABELS]
            if slots:
                system = CLARIFICATION_PROMPT.format(
                    slots=", ".join(SLOT_LABELS[slot] for slot in slots),
                    today=today, timezone=validate)
                try:
                    data = await self._ask_json(
                        self._provider, system, query,
                        max(256, min(self._max_tokens, 768)))
                    contract = _apply_clarification(data, previous, slots)
                except UpstreamError as exc:
                    log.warning("clarification parse failed, using fallback: %s",
                                exc)
                    contract = _fallback_clarification(
                        query, previous, slots, self._settings)
                if contract is not None:
                    contract.context_state.session_id = (
                        session_id or ANONYMOUS_SESSION)
                    contract.context_state.turn_count = 1
                    contract.semantic_payload.language = language
                    log.info(
                        "clarification slots: %s -> city=%s budget=%s party=%s",
                        slots, contract.hard_filters.location.city,
                        contract.hard_filters.budget,
                        contract.hard_filters.party_size)
                    return sanitize(contract), False, complexity.complex
                # The user changed topic instead of answering: use the
                # full parser below, but without clarification bias.
                previous = previous.model_copy(deep=True)
                previous.needs_clarification = False
                previous.clarification_slots = []

        system = PROMPT.format(city=self._settings.default_city,
                               timezone=validate, language=language,
                               today=today)
        if previous is not None:
            system += (
                "\nЭто продолжение диалога. Предыдущий intent: "
                f"{previous.intent}. Если запрос является уточнением, сохрани "
                "intent и уже известные слоты (дата, город, тема, категории), "
                "если пользователь явно не сменил тему. Если тема сменилась "
                "(например, после бара просит почитать), выбери новый intent.")
        contract = None
        try:
            data = await self._ask_json(provider, system, query, max_tokens)
            data = _normalise(data, self._settings)
            contract = StateContract.model_validate(data)
        except (UpstreamError, ValueError) as exc:
            raise UpstreamError(
                f"LLM вернула контракт неверной формы: {exc}") from exc
        contract.context_state.session_id = session_id or ANONYMOUS_SESSION
        contract.context_state.turn_count = 1
        contract.semantic_payload.language = language
        if contract.dialogue_action == "search":
            vector = _clean_vector_query(
                contract.semantic_payload.vector_query,
                self._settings.default_city)
            if not vector:
                vector = _clean_vector_query(query, self._settings.default_city)
            contract.semantic_payload.vector_query = vector
        log.info("structure stage: %s -> categories=%s datetime=%s reasoning=%s",
                 query[:80], contract.hard_filters.category,
                 contract.hard_filters.datetime.start if contract.hard_filters.datetime else None,
                 reasoning_used)
        return sanitize(contract), reasoning_used, complexity.complex
