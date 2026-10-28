"""Telegram public previews (t.me/s/...): two live afisha channels.

IMPORTANT: verify every channel against the Mininform list before adding
it to TELEGRAM_CHANNELS. Some afisha channels are designated extremist.
Unstructured text: regex first, LLM fallback only when enabled
(TELEGRAM_LLM_FALLBACK) for ambiguous dates.
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from selectolax.lexbor import LexborHTMLParser

from ..core import db
from ..core.config import settings
from ..normalize import RawEvent, parse_price
from ..parse import clean_text
from ..repositories.store import upsert_events
from .base import CollectContext, RunStats, SourceAdapter
from ..text_ru import parse_ru_datetime

log = logging.getLogger(__name__)

BASE = "https://t.me/s"

INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
HAS_WORD_RE = re.compile(r"[^\W_]", re.UNICODE)


def first_meaningful_line(text: str, fallback: str) -> str:
    """First line with a letter/digit (skips ZWSP/emoji-only lines)."""
    for line in text.split("\n"):
        cleaned = INVISIBLE_RE.sub("", line).strip()
        if cleaned and HAS_WORD_RE.search(cleaned):
            return clean_text(cleaned) or fallback
    return fallback

CATEGORY_KEYWORDS = {
    "концерт": "concert",
    "спектакль": "theatre",
    "театр": "theatre",
    "выставк": "exhibition",
    "кино": "film",
    "стендап": "concert",
    "фестиваль": "concert",
    "спорт": "sport",
    "детск": "kids",
}


class TelegramAdapter(SourceAdapter):
    name = "telegram"

    def __init__(self, channels: list[str] | None = None, max_pages: int = 5,
                 llm_fallback: bool = False) -> None:
        self._channels = channels
        self._max_pages = max_pages
        self._llm_fallback = llm_fallback

    async def collect(self, ctx: CollectContext) -> RunStats:
        channels = self._channels or [
            name.strip() for name in settings.telegram_channels.split(",") if name.strip()]
        max_pages = self._max_pages if self._max_pages else settings.telegram_max_pages
        stats = RunStats()
        now = datetime.now(timezone.utc)
        with db.get_conn(ctx.db_url) as conn:
            for channel in channels:
                try:
                    await self._collect_channel(ctx, conn, stats, now, channel, max_pages)
                except Exception as exc:  # noqa: BLE001 — one channel must not kill the run
                    stats.fetch_errors += 1
                    conn.rollback()
                    log.warning("telegram channel %s failed: %s", channel, exc)
        if stats.fetched == 0:
            raise RuntimeError("all telegram channels failed")
        return stats

    async def _collect_channel(self, ctx, conn, stats, now, channel, max_pages) -> None:
        before: int | None = None
        for _ in range(max_pages):
            url = f"{BASE}/{channel}" + (f"?before={before}" if before else "")
            response = await ctx.http.get(self.name, url)
            stats.fetched += 1
            if response.status_code != 200:
                raise RuntimeError(f"{url} -> HTTP {response.status_code}")
            messages = extract_messages(response.text)
            if not messages:
                break
            events: list[RawEvent] = []
            for message in messages:
                if not (message.get("text") or "").strip():
                    continue  # service messages carry no event
                event = self.normalize(channel, message, now)
                if event is None:
                    stats.parse_errors += 1
                    continue
                stats.parsed += 1
                events.append(event)
            merged = upsert_events(conn, events)
            stats.rows_inserted += merged.rows_inserted
            stats.rows_updated += merged.rows_updated
            stats.duplicates += merged.duplicates
            conn.commit()
            ids = [message["id"] for message in messages]
            before = min(ids) - 1

    def normalize(self, channel: str, message: dict, now) -> RawEvent | None:
        text = message.get("text") or ""
        if not text.strip():
            return None
        sections = {key: value for key, value in split_sections(text).items()}
        start_at = parse_ru_datetime(sections.get("date", text), now)
        venue = clean_text(sections.get("place"))
        price_min, price_max = parse_price(sections.get("price"))
        title = first_meaningful_line(text, f"Telegram @{channel}")
        lowered = text.casefold()
        category = "other"
        for keyword, mapped in CATEGORY_KEYWORDS.items():
            if keyword in lowered:
                category = mapped
                break
        return RawEvent(
            source=self.name,
            source_id=f"{channel}/{message['id']}",
            source_url=message.get("url") or f"https://t.me/{channel}/{message['id']}",
            title=title[:200],
            description=clean_text(text[:2000]),
            category=category,
            start_at=start_at,
            venue_name=venue,
            city=settings.default_city,
            price_min=price_min,
            price_max=price_max,
            raw={"channel": channel, "message_id": message["id"]},
        )


def split_sections(text: str) -> dict:
    """Split ⏰ date / 📍 place / 💵 price sections by emoji position."""
    markers = {"⏰": "date", "📍": "place", "💵": "price"}
    positions = [(text.index(emoji), key) for emoji, key in markers.items()
                 if emoji in text]
    if not positions:
        return {}
    positions.sort()
    sections: dict[str, str] = {}
    for index, (start, key) in enumerate(positions):
        end = positions[index + 1][0] if index + 1 < len(positions) else len(text)
        value = text[start + 1:end].strip(" |\n")
        if value:
            sections[key] = value
    return sections


def extract_messages(html: str) -> list[dict]:
    """Preview messages newest-first: id, utc post time, text, url."""
    tree = LexborHTMLParser(html)
    messages = []
    for wrap in tree.css("div.tgme_widget_message_wrap"):
        node = wrap.css_first("div.tgme_widget_message")
        if node is None:
            continue
        data_post = node.attributes.get("data-post", "")
        try:
            message_id = int(data_post.split("/")[-1])
        except (ValueError, IndexError):
            continue
        time_node = wrap.css_first("time")
        posted_at = time_node.attributes.get("datetime") if time_node else None
        text_node = wrap.css_first(".tgme_widget_message_text")
        text = text_node.text(separator="\n", strip=True) if text_node else ""
        link = wrap.css_first("a.tgme_widget_message_date")
        messages.append({
            "id": message_id,
            "posted_at": posted_at,
            "text": text,
            "url": link.attributes.get("href") if link else None,
        })
    return messages
