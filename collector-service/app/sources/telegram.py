"""Telegram public previews (t.me/s/...): two live afisha channels.

IMPORTANT: verify every channel against the Mininform list before adding
it to TELEGRAM_CHANNELS. Some afisha channels are designated extremist.
Unstructured text: regex first, LLM fallback only when enabled
(TELEGRAM_LLM_FALLBACK) for ambiguous dates.
"""
from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape

from selectolax.lexbor import LexborHTMLParser

from ..core import db
from ..core.config import settings
from ..errors.domain import SourceFetchError
from ..parsing.normalize import RawEvent, parse_price
from ..parsing.relevance import ChannelRules, Decision, VENUE_RE, classify
from ..repositories.store import upsert_events
from ..core.text import clean_text
from .base import CollectContext, RunStats, SourceAdapter
from ..parsing.text_ru import parse_ru_datetime

log = logging.getLogger(__name__)

BASE = "https://t.me/s"
STATS_KEY_PREFIX = "telegram:stats:"

INVISIBLE_RE = re.compile(r"[\u200b\u200c\u200d\ufeff]")
HAS_WORD_RE = re.compile(r"[^\W_]", re.UNICODE)
CTA_RE = re.compile(
    r"^(?:жми|подробнее|переходи|подпишись|регистрац|записывайся|"
    r"бронируй|куп(?:и|ить) билет)", re.I)
PRICE_LINE_RE = re.compile(r"(?:руб|byn|р\.|вход свободн|бесплатн)", re.I)


def first_meaningful_line(text: str, fallback: str) -> str:
    """First non-CTA line with a letter/digit (skips ZWSP/emoji-only lines)."""
    for line in text.split("\n"):
        cleaned = INVISIBLE_RE.sub("", line).strip()
        if cleaned and HAS_WORD_RE.search(cleaned):
            if CTA_RE.search(cleaned):
                continue
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
HASHTAG_CATEGORIES = {
    "#детям": "kids",
    "#детск": "kids",
    "#концерт": "concert",
    "#спектакль": "theatre",
    "#театр": "theatre",
    "#выставка": "exhibition",
    "#квиз": "other",
    "#стендап": "concert",
    "#фестиваль": "concert",
    "#кино": "film",
    "#спорт": "sport",
}


@dataclass
class ChannelCounters:
    fetched: int = 0
    kept: int = 0
    dropped_housing: int = 0
    dropped_jobs: int = 0
    dropped_ad: int = 0
    dropped_resale: int = 0
    dropped_no_event: int = 0
    dropped_digest: int = 0
    dropped_undated: int = 0
    duplicates: int = 0
    errors: int = 0

    _REASONS = {
        "housing": "dropped_housing",
        "jobs": "dropped_jobs",
        "ad": "dropped_ad",
        "resale": "dropped_resale",
        "no_event": "dropped_no_event",
        "strict_event": "dropped_no_event",
        "companion": "dropped_no_event",
        "digest": "dropped_digest",
        "undated": "dropped_undated",
    }

    def record(self, decision: Decision) -> None:
        if decision.keep:
            self.kept += 1
            return
        field = self._REASONS.get(decision.reason, "dropped_no_event")
        setattr(self, field, getattr(self, field) + 1)

    @property
    def dropped(self) -> int:
        return (self.fetched - self.kept - self.errors) if self.fetched else 0

    def as_dict(self) -> dict:
        dropped = max(0, self.dropped)
        ratio = round(self.kept / self.fetched, 3) if self.fetched else 0.0
        return {"fetched": self.fetched, "kept": self.kept,
                "dropped": dropped, "keep_ratio": ratio,
                "dropped_housing": self.dropped_housing,
                "dropped_jobs": self.dropped_jobs,
                "dropped_ad": self.dropped_ad,
                "dropped_resale": self.dropped_resale,
                "dropped_no_event": self.dropped_no_event,
                "dropped_digest": self.dropped_digest,
                "dropped_undated": self.dropped_undated,
                "duplicates": self.duplicates, "errors": self.errors}


def message_time(message: dict, fallback: datetime) -> datetime:
    """Use the post's own timestamp for relative dates («сегодня/завтра»)."""
    raw = message.get("posted_at")
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = datetime.fromisoformat(raw.strip().replace("Z", "+00:00"))
        except ValueError:
            return fallback
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    return fallback


class TelegramAdapter(SourceAdapter):
    name = "telegram"

    def __init__(self, channels: list[str] | None = None,
                 max_pages: int | None = None,
                 llm_fallback: bool = False) -> None:
        self._channels = channels
        self._max_pages = max_pages
        self._llm_fallback = llm_fallback

    async def collect(self, ctx: CollectContext) -> RunStats:
        channels = self._channels or settings.telegram_channel_list()
        stats = RunStats()
        now = datetime.now(timezone.utc)
        with db.get_conn(ctx.db_url) as conn:
            for channel in channels:
                counters = ChannelCounters()
                try:
                    await self._collect_channel(
                        ctx, conn, stats, now, channel, counters)
                except Exception as exc:  # noqa: BLE001 — one channel must not kill the run
                    counters.errors += 1
                    stats.fetch_errors += 1
                    conn.rollback()
                    log.warning("telegram channel %s failed: %s", channel, exc)
                finally:
                    self._store_stats(conn, channel, counters)
                    summary = counters.as_dict()
                    log.info(
                        "telegram @%s: fetched=%d kept=%d ratio=%.0f%% "
                        "housing=%d jobs=%d ad=%d no_event=%d digest=%d "
                        "undated=%d errors=%d",
                        channel, summary["fetched"], summary["kept"],
                        summary["keep_ratio"] * 100, summary["dropped_housing"],
                        summary["dropped_jobs"], summary["dropped_ad"],
                        summary["dropped_no_event"], summary["dropped_digest"],
                        summary["dropped_undated"], summary["errors"])
        if stats.fetched == 0:
            raise SourceFetchError("all telegram channels failed")
        return stats

    async def _collect_channel(self, ctx, conn, stats, now, channel,
                               counters: ChannelCounters) -> None:
        max_pages = (self._max_pages or settings.telegram_pages_for(channel)
                     or settings.telegram_max_pages)
        rules = channel_rules(channel)
        observe = channel.casefold() in settings.telegram_observe_set()
        before: int | None = None
        for _ in range(max_pages):
            url = f"{BASE}/{channel}" + (f"?before={before}" if before else "")
            response = await ctx.http.get(self.name, url)
            stats.fetched += 1
            if response.status_code != 200:
                raise SourceFetchError(f"{url} -> HTTP {response.status_code}")
            messages = extract_messages(response.text)
            if not messages:
                break
            events: list[RawEvent] = []
            for message in messages:
                text = (message.get("text") or "").strip()
                if not text:
                    continue  # service messages carry no event
                counters.fetched += 1
                decision = classify(text, channel, rules)
                counters.record(decision)
                if not decision.keep:
                    if decision.reason == "digest":
                        log.info("telegram @%s digest skipped: id=%s",
                                 channel, message.get("id"))
                    continue
                if observe:
                    continue  # classify/count only; never write low-ratio channels
                event = self.normalize(
                    channel, message, message_time(message, now))
                if event is None:
                    counters.errors += 1
                    stats.parse_errors += 1
                    continue
                stats.parsed += 1
                events.append(event)
            merged = upsert_events(conn, events)
            stats.rows_inserted += merged.rows_inserted
            stats.rows_updated += merged.rows_updated
            stats.duplicates += merged.duplicates
            counters.duplicates += merged.duplicates
            conn.commit()
            ids = [message["id"] for message in messages]
            before = min(ids) - 1

    def _store_stats(self, conn, channel: str, counters: ChannelCounters) -> None:
        """Persist last-run counters in collector_kv (no migration needed)."""
        key = STATS_KEY_PREFIX + channel.casefold()
        payload = json.dumps(counters.as_dict(), ensure_ascii=False)
        try:
            conn.execute(
                """INSERT INTO collector_kv (key, value) VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
                                                   updated_at = now()""",
                (key, payload))
            conn.commit()
        except Exception as exc:  # noqa: BLE001 — stats must not break collection
            conn.rollback()
            log.warning("telegram stats write failed for %s: %s", channel, exc)

    def normalize(self, channel: str, message: dict, now) -> RawEvent | None:
        text = message.get("text") or ""
        if not text.strip():
            return None
        sections = split_sections(text)
        start_at = parse_ru_datetime(sections.get("date", text), now)
        title = first_meaningful_line(text, f"Telegram @{channel}")
        venue = _venue_value(clean_text(sections.get("place"))) or scan_venue(text, title)
        price_text = sections.get("price") or scan_price(text)
        price_min, price_max = parse_price(price_text)
        category = detect_category(channel, text)
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
            image_url=message.get("image"),
            raw={"channel": channel, "message_id": message["id"],
                 "image": message.get("image"),
                 "posted_at": message.get("posted_at")},
        )


def channel_rules(channel: str) -> ChannelRules:
    """Per-channel policy from `COLLECTOR_TELEGRAM_CHANNEL_RULES` + undated_ok."""
    flags = settings.telegram_rule_flags(channel)
    return ChannelRules(
        no_housing="no_housing" in flags,
        no_jobs="no_jobs" in flags,
        no_ad="no_ad" in flags,
        strict_event="strict_event" in flags,
        no_companion_search="no_companion_search" in flags,
        undated_ok=channel.casefold() in settings.telegram_undated_ok_set(),
    )


def detect_category(channel: str, text: str) -> str:
    """Hashtag > keyword > per-channel default; keyword detection overrides."""
    lowered = text.casefold()
    for hashtag, mapped in HASHTAG_CATEGORIES.items():
        if hashtag in lowered:
            return mapped
    for keyword, mapped in CATEGORY_KEYWORDS.items():
        if keyword in lowered:
            return mapped
    return settings.telegram_category_for(channel) or "other"


def _venue_value(value: str | None) -> str | None:
    """Keep only the venue line: no description, phones, hashtags or links.

    Telegram «📍» sections sometimes carry the whole post below the marker;
    the first line is the venue, the rest is an announcement.
    """
    if not value:
        return None
    cleaned = clean_text(value)
    if not cleaned:
        return None
    line = cleaned.splitlines()[0]
    line = re.split(r"\s*(?:\||#|https?://|телефон|вход\b|билет)", line,
                    maxsplit=1, flags=re.I)[0].strip(" ,.-")
    return line[:120] or None


def scan_venue(text: str, title: str | None = None) -> str | None:
    """Conservative venue fallback when no 📍 section exists."""
    for line in text.splitlines():
        cleaned = clean_text(line)
        if not cleaned or cleaned == title or len(cleaned) > 120:
            continue
        if "#" in cleaned or "http" in cleaned.casefold():
            continue
        if VENUE_RE.search(cleaned):
            return _venue_value(cleaned)
    return None


def scan_price(text: str) -> str | None:
    """Conservative price fallback when no 💵 section exists."""
    for line in text.splitlines():
        cleaned = clean_text(line)
        if cleaned and PRICE_LINE_RE.search(cleaned):
            low, high = parse_price(cleaned)
            if low is not None or high is not None:
                return cleaned
    return None


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


def _background_image(node) -> str | None:
    if node is None:
        return None
    style = node.attributes.get("style") or ""
    match = re.search(r"background-image\s*:\s*url\(\s*['\"]?([^'\")]+)",
                      style, re.IGNORECASE)
    return unescape(match.group(1).strip()) if match else None


def _image_src(node) -> str | None:
    """`src`/`data-src`/first `srcset` candidate of an <img>."""
    if node is None:
        return None
    for attr in ("src", "data-src"):
        value = node.attributes.get(attr)
        if isinstance(value, str) and value.strip():
            return unescape(value.strip())
    srcset = node.attributes.get("srcset")
    if isinstance(srcset, str) and srcset.strip():
        first = srcset.split(",")[0].strip().split(" ")[0]
        return unescape(first) if first else None
    return None


def _link_preview_image(wrap) -> str | None:
    """Image of a link preview / «text not supported» post.

    Telegram renders posts that only carry an external link (or that the
    preview widget cannot render) with `text_not_supported_wrap` and a
    `tgme_widget_message_link_preview` image. The catalog showed a
    placeholder for those while the post page had a picture.
    """
    for selector in (
            ".tgme_widget_message_link_preview img",
            ".tgme_widget_message_link_preview_image",
            ".tgme_widget_message_link_preview"):
        node = wrap.css_first(selector)
        if node is None:
            continue
        image = _image_src(node) or _background_image(node)
        if image:
            return image
    node = wrap.css_first(".text_not_supported_wrap img")
    image = _image_src(node) or _background_image(node)
    if image:
        return image
    video = wrap.css_first("video[poster]")
    if video is not None:
        poster = video.attributes.get("poster")
        if isinstance(poster, str) and poster.strip():
            return unescape(poster.strip())
    return None


def extract_messages(html: str) -> list[dict]:
    """Preview messages newest-first: id, utc post time, text, image, url."""
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
        image = _background_image(
            wrap.css_first("a.tgme_widget_message_photo_wrap"))
        if image is None:
            image = _background_image(
                wrap.css_first(".tgme_widget_message_video_thumb"))
        if image is None:
            image = _link_preview_image(wrap)
        messages.append({
            "id": message_id,
            "posted_at": posted_at,
            "text": text,
            "image": image,
            "url": link.attributes.get("href") if link else None,
        })
    return messages
