"""Deterministic Russian lexicon for venue atmosphere tags.

No LLM: review/description text and rubric names are matched against a small
curated set of Russian stems. Tags are a closed vocabulary shared with the
Qdrant payload; ``atmosphere_text`` turns them back into Russian words for the
searchable venue text.
"""
from __future__ import annotations

import re

# Canonical order: stable output for tests, storage and payload diffs.
TAGS = (
    "quiet",
    "cozy",
    "romantic",
    "live_music",
    "loud",
    "crowded",
    "hookah",
    "outdoor",
    "kids_friendly",
    "business",
    "hipster",
    "trendy",
    "atmospheric",
)
_TAG_ORDER = {tag: index for index, tag in enumerate(TAGS)}

# Tag -> Russian words used in search_text (dense/sparse/BM25).
TAG_WORDS = {
    "quiet": "тихо",
    "cozy": "уютно",
    "romantic": "романтично",
    "live_music": "живая музыка",
    "loud": "шумно",
    "crowded": "многолюдно",
    "hookah": "кальян",
    "outdoor": "веранда",
    "kids_friendly": "для детей",
    "business": "для работы",
    "hipster": "хипстерское место",
    "trendy": "модное место",
    "atmospheric": "атмосферное место",
}

# Stem patterns per tag. ``\b`` works for Cyrillic in Python's Unicode regex.
_RULES: dict[str, tuple[str, ...]] = {
    "quiet": (
        r"\bтих(?:о|ий|ая|ое|ие|им|ую|ой|их|ого|онько)\b",
        r"\bтишин",
        r"\bспокойн",
        r"\bнегромк",
        r"\bуединен",
        r"\bбез музык",
        r"\bнет музык",
    ),
    "cozy": (
        r"\bуютн",
        r"\bкомфортн",
        r"\bдомашн",
        r"\bлампов",
        r"\bтепл[а-я]*",
    ),
    "romantic": (
        r"\bромантичн",
        r"\bромантик",
        r"\bсвидан",
        r"\bдля двоих",
        r"\bсвеч[а-я]*",
        r"\bпри свечах",
    ),
    "live_music": (
        r"\bжив(?:ая|ой|ую|ым|ыми)?\s+музык",
        r"\bживой звук",
        r"\bживьем",
        r"\bживьём",
        r"\bвыступлен",
        r"\bиграет групп",
        r"\bмузыкант",
        r"\bконцерт",
    ),
    "loud": (
        r"\bгромк",
        r"\bшум[а-я]*",
        r"\bорат",
        r"\bкричит",
        r"\bгрохот",
        r"\bдолбит",
        r"\bне слышно",
        r"\bне поговорить",
        r"\bдиджей",
        r"\bdj\b",
    ),
    "crowded": (
        r"\bтолп",
        r"\bмноголюдн",
        r"\bочеред",
        r"\bбитком",
        r"\bне протолкнут",
        r"\bполный зал",
        r"\bаншлаг",
        r"\bмного людей",
        r"\bмест нет",
    ),
    "hookah": (
        r"\bкальян",
    ),
    "outdoor": (
        r"\bверанд",
        r"\bтеррас",
        r"\bна улице",
        r"\bпод открытым небом",
        r"\bлетн[а-я]* площадк",
        r"\bоткрыт[а-я]* площадк",
        r"\bво дворе",
        r"\bдворик",
        r"\boutdoor",
    ),
    "kids_friendly": (
        r"\bдетск",
        r"\bдетям",
        r"\bс детьми",
        r"\bсемейн",
        r"\bдля детей",
        r"\bигров[а-я]* комнат",
        r"\bаниматор",
    ),
    "business": (
        r"\bбизнес",
        r"\bделов[а-я]*",
        r"\bпереговор",
        r"\bковоркинг",
        r"\bдля работ",
        r"\bноутбук",
        r"\bпрезентац",
    ),
    "hipster": (
        r"\bхипстер",
        r"\bинди\b",
        r"\bкрафт",
        r"\bвинил",
        r"\bарт[- ]?пространств",
        r"\bлофт",
        r"\bандеграунд",
    ),
    "trendy": (
        r"\bмодн",
        r"\bтренд",
        r"\bпопулярн",
        r"\bстильн",
        r"\bсовременн",
        r"\bхайп",
        r"\bнашумев",
    ),
    "atmospheric": (
        r"\bатмосфер",
        r"\bинтерьер",
        r"\bэстетик",
        r"\bкрасив",
        r"\bвинтаж",
        r"\bдизайн",
        r"\bпанорам",
        r"\bвид на",
    ),
}

# A positive stem is ignored when the same sentence explicitly negates it
# ("не шумно", "без живой музыки"). Small and explicit on purpose.
_NEGATIONS: dict[str, tuple[str, ...]] = {
    "quiet": (r"\bне тихо\b", r"\bсовсем не тихо\b"),
    "live_music": (r"\bбез живой музык", r"\bнет живой музык", r"\bбез музык"),
    "loud": (r"\bне шумн", r"\bне громк", r"\bбез шума\b"),
    "crowded": (r"\bне многолюдн", r"\bбез толп", r"\bнет толп",
                r"\bбез очеред", r"\bнет очеред"),
    "hookah": (r"\bбез кальян", r"\bнет кальян"),
    "outdoor": (r"\bбез веранд", r"\bнет веранд", r"\bбез террас",
                r"\bнет террас"),
    "kids_friendly": (r"\bбез детей", r"\bне для детей"),
    "business": (r"\bне для работ",),
}

_COMPILED = {tag: tuple(re.compile(p) for p in patterns)
             for tag, patterns in _RULES.items()}
_NEGATED = {tag: tuple(re.compile(p) for p in patterns)
            for tag, patterns in _NEGATIONS.items()}

# Conservative name/rubric fallback: only unambiguous venue kinds.
_RUBRIC_RULES = (
    (re.compile(r"\bбар\b|\bпаб\b|\bpub\b|\bbar\b"), ("loud", "trendy")),
    (re.compile(r"\bночн[а-я]* клуб|\bnight ?club"), ("loud", "crowded", "trendy")),
    (re.compile(r"\bбиблиотек|\bкнижн|\bкниг"), ("quiet",)),
    (re.compile(r"\bкафе\b|\bкофейн|\bcoffee"), ("cozy",)),
    (re.compile(r"\bтеатр|\bмузе[йя]\b|\bмузей|\bгалере|\bвыставк"),
     ("atmospheric",)),
    (re.compile(r"\bпарк\b|\bсквер"), ("outdoor", "quiet")),
    (re.compile(r"\bдетск"), ("kids_friendly",)),
    (re.compile(r"\bкараоке"), ("loud", "live_music")),
    (re.compile(r"\bкальян"), ("hookah",)),
)
_WHITESPACE_RE = re.compile(r"\s+")


def _normalize(text: str | None) -> str:
    return _WHITESPACE_RE.sub(" ", str(text or "").casefold().replace("ё", "е")).strip()


def _ordered(tags) -> list[str]:
    return sorted(set(tags), key=lambda tag: _TAG_ORDER.get(tag, len(TAGS)))


def atmosphere_tags(text: str | None) -> list[str]:
    """Map free Russian text onto the closed atmosphere tag vocabulary."""
    normalized = _normalize(text)
    if not normalized:
        return []
    found: list[str] = []
    for tag in TAGS:
        if not any(pattern.search(normalized) for pattern in _COMPILED[tag]):
            continue
        if any(pattern.search(normalized) for pattern in _NEGATED.get(tag, ())):
            continue
        found.append(tag)
    return found


def atmosphere_from_rubric(name: str | None, rubric: str | None) -> list[str]:
    """Conservative name/rubric heuristics used when no text is available."""
    normalized = _normalize(f"{name or ''} {rubric or ''}")
    tags: list[str] = []
    for pattern, matched in _RUBRIC_RULES:
        if pattern.search(normalized):
            tags.extend(matched)
    return _ordered(tags)


def atmosphere_text(tags) -> str:
    """Tags -> Russian words for `search_text` (unknown tags are ignored)."""
    if not tags:
        return ""
    selected = set(tags)
    return ", ".join(TAG_WORDS[tag] for tag in TAGS if tag in selected)
