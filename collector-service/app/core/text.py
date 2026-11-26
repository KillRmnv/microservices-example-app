"""Text cleanup for scraped event copy.

Sources (Telegram previews in particular) decorate descriptions with emoji,
dingbats, flags and box-drawing separators.  This module keeps the readable
text, punctuation, URLs and line structure while dropping the decoration.

No third-party dependencies: the ranges below are Unicode ranges handled by
the stdlib ``re`` engine; ``unicodedata`` only normalises the result.
"""
from __future__ import annotations

import re
import unicodedata

__all__ = ["clean_text", "strip_emoji"]


# Emoji, pictographs, dingbats and the symbol blocks Telegram posts abuse.
# Keep this a single character class so one pass removes whole ZWJ/flag
# sequences (their individual code points all live in these ranges).
_EMOJI_CLASS = (
    "\U0001F000-\U0001FAFF"  # pictographs, emoticons, transport, supplemental
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flag halves)
    "\U0001F3FB-\U0001F3FF"  # skin-tone modifiers
    "\U000E0020-\U000E007F"  # tag characters (subdivision flags)
    "\u2600-\u27BF"          # misc symbols + dingbats (☀ ✅ ❤ ➡ ...)
    "\u2B00-\u2BFF"          # misc symbols and arrows (⭐ ⬛ ...)
    "\u2300-\u23FF"          # technical symbols (⌚ ⏰ ⏳ ...)
    "\u25A0-\u25FF"          # geometric shapes (■ ● ▲ ...)
    "\u2190-\u21FF"          # arrows (↔️ ↩️ → ...)
    "\u2049\u203C"           # ‼ ⁉
    "\u20E3"                 # combining enclosing keycap
    "\u2139\u24C2"           # ℹ Ⓜ
    "\u3030\u303D\u3297\u3299"
)
EMOJI_RE = re.compile(f"[{_EMOJI_CLASS}]")

# Invisible formatting characters: zero-width spaces/joiners, BOM, bidi
# controls, soft hyphen, variation selectors (FE0F makes ❤️ out of ❤).
_INVISIBLE_CLASS = (
    "\u00AD\u061C\u180E"
    "\u200B-\u200F"
    "\u202A-\u202E"
    "\u2060-\u2064"
    "\u2066-\u206F"
    "\uFE00-\uFE0F"
    "\uFEFF"
    "\U000E0100-\U000E01EF"  # variation selectors supplement
)
INVISIBLE_RE = re.compile(f"[{_INVISIBLE_CLASS}]")

# Pure decoration: box drawing, block elements, list bullets.  Replaced by a
# space so "текст ─── ещё" stays two words instead of becoming one.
DECORATION_RE = re.compile(r"[\u2500-\u259F\u2022\u2023\u2043\u25E6\u2219\u22C5]")

# Telegram MarkdownV2 / legacy Markdown wrappers.  Longest markers first so
# ``**bold**`` is not consumed as two single-asterisk runs.  The inner text is
# kept; only the markers are dropped.
MARKUP_PAIRS_RE = re.compile(
    r"(?<!\w)(\*\*\*|\*\*|\*|___|__|_|~~~|~~|~|\|\||`{3}|`{2}|`)"
    r"(?=\S)([^\n]+?)(?<=\S)\1(?!\w)"
)
TELEGRAM_LINK_RE = re.compile(r"\[([^\]\n]+)\]\((https?://[^)\s]+)\)")
URL_RE = re.compile(r"(?:https?://|www\.|t\.me/)[^\s<>\"']+", re.I)
HAS_WORD_RE = re.compile(r"[^\W_]", re.UNICODE)


def strip_emoji(value: str | None) -> str:
    """Remove emoji/pictographs, flags, modifiers and invisible characters.

    Whitespace and line structure are left untouched; use :func:`clean_text`
    for the full normalisation pipeline.
    """
    if not value:
        return ""
    text = unicodedata.normalize("NFC", str(value))
    return INVISIBLE_RE.sub("", EMOJI_RE.sub("", text))


def _strip_markup_segment(segment: str) -> str:
    previous = None
    while previous != segment:
        previous = segment
        segment = MARKUP_PAIRS_RE.sub(r"\2", segment)
    return segment


def _strip_markup(text: str) -> str:
    """Drop Telegram Markdown wrappers without touching text inside URLs."""
    parts: list[str] = []
    position = 0
    for match in URL_RE.finditer(text):
        parts.append(_strip_markup_segment(text[position:match.start()]))
        parts.append(match.group(0))
        position = match.end()
    parts.append(_strip_markup_segment(text[position:]))
    text = "".join(parts)
    return TELEGRAM_LINK_RE.sub(r"\1 (\2)", text)


def clean_text(value: str | None) -> str | None:
    """Return clean, human-readable text or ``None`` when nothing is left.

    Removes emoji/decoration, collapses runs of spaces and blank lines, drops
    lines that consist only of symbols, and preserves ordinary Russian text,
    punctuation, URLs and paragraph breaks.
    """
    if value is None:
        return None
    text = str(value).replace("\r\n", "\n").replace("\r", "\n")

    lines: list[str] = []
    for raw_line in text.split("\n"):
        # Only a genuinely empty source line survives as a paragraph break;
        # lines emptied by emoji/decoration removal are dropped entirely.
        blank_source = not raw_line.strip()
        line = strip_emoji(raw_line)
        line = _strip_markup(line)
        line = DECORATION_RE.sub(" ", line)
        line = re.sub(r"[^\S\n]+", " ", line).strip()
        if not line:
            if blank_source:
                lines.append("")
        elif HAS_WORD_RE.search(line):
            lines.append(line)
        # else: a separator/symbol-only line — drop it entirely.

    result = "\n".join(lines)
    result = re.sub(r"\n{3,}", "\n\n", result).strip()
    return result or None
