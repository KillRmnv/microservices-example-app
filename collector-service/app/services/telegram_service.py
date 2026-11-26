"""Telegram dry-run preview and historical relevance rescore."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from ..core import db
from ..core.config import settings
from ..parsing.relevance import classify
from ..sources.telegram import (BASE, channel_rules, extract_messages,
                                first_meaningful_line)

log = logging.getLogger(__name__)

DEFAULT_PREVIEW_PAGES = 2
DEFAULT_PREVIEW_LIMIT = 50
HARD_JUNK = {"housing", "jobs", "ad", "resale"}
AUDIT_KEY = "telegram:rescore:audit"


class TelegramService:
    def __init__(self, http, db_url: str) -> None:
        self._http = http
        self._db_url = db_url

    async def preview(self, channel: str, pages: int = DEFAULT_PREVIEW_PAGES,
                      limit: int = DEFAULT_PREVIEW_LIMIT) -> dict:
        """Fetch public preview pages and classify only; writes nothing."""
        pages = max(1, min(10, int(pages or DEFAULT_PREVIEW_PAGES)))
        limit = max(1, min(200, int(limit or DEFAULT_PREVIEW_LIMIT)))
        rules = channel_rules(channel)
        observe = channel.casefold() in settings.telegram_observe_set()
        messages, before = [], None
        for _ in range(pages):
            url = f"{BASE}/{channel}" + (f"?before={before}" if before else "")
            response = await self._http.get("telegram", url)
            if response.status_code != 200:
                break
            page = extract_messages(response.text)
            if not page:
                break
            messages.extend(page)
            before = min(item["id"] for item in page) - 1
            if len(messages) >= limit:
                break

        results, reasons = [], {}
        kept = 0
        for message in messages[:limit]:
            text = (message.get("text") or "").strip()
            if not text:
                continue
            decision = classify(text, channel, rules)
            kept += int(decision.keep)
            if not decision.keep:
                reasons[decision.reason] = reasons.get(decision.reason, 0) + 1
            results.append({
                "id": message.get("id"),
                "title": first_meaningful_line(
                    text, f"Telegram @{channel}")[:200],
                **decision.as_dict(),
            })
        total = len(results)
        return {"channel": channel, "pages": pages, "observe": observe,
                "messages": results,
                "summary": {"total": total, "kept": kept,
                            "dropped_by_reason": reasons,
                            "keep_ratio": round(kept / total, 3) if total else 0.0}}

    def rescore(self, dry_run: bool = True) -> dict:
        """Re-classify existing telegram rows; delete only hard junk."""
        with db.get_conn(self._db_url) as conn:
            rows = conn.execute(
                """SELECT id, source_id, title, description,
                          raw->>'channel' AS channel
                     FROM collected_events
                    WHERE source = 'telegram'
                    ORDER BY start_at NULLS LAST, fetched_at""").fetchall()
            would_delete, other = [], {}
            for row in rows:
                channel = row["channel"] or ""
                decision = classify(
                    f"{row['title'] or ''}\n{row['description'] or ''}",
                    channel, channel_rules(channel))
                if decision.keep:
                    continue
                if decision.reason not in HARD_JUNK:
                    other[decision.reason] = other.get(decision.reason, 0) + 1
                    continue
                would_delete.append({"id": str(row["id"]),
                                     "title": row["title"],
                                     "reason": decision.reason})
            by_reason = {}
            for entry in would_delete:
                by_reason[entry["reason"]] = by_reason.get(entry["reason"], 0) + 1
            deleted, deleted_ids = 0, []
            if not dry_run and would_delete:
                deleted_ids = [entry["id"] for entry in would_delete]
                deleted = conn.execute(
                    """DELETE FROM collected_events
                        WHERE source = 'telegram' AND id = ANY(%s::uuid[])""",
                    (deleted_ids,)).rowcount
                self._write_audit(conn, would_delete)
                conn.commit()
                log.warning("telegram rescore deleted %d hard-junk posts: %s",
                            deleted, by_reason)
        return {"dry_run": dry_run, "scanned": len(rows),
                "would_delete": len(would_delete), "deleted": deleted,
                "by_reason": by_reason, "samples": would_delete[:20],
                "other_dropped": other, "deleted_ids": deleted_ids}

    @staticmethod
    def _write_audit(conn, entries: list[dict]) -> None:
        payload = json.dumps(
            {"deleted_at": datetime.now(timezone.utc).isoformat(),
             "entries": entries}, ensure_ascii=False)
        conn.execute(
            """INSERT INTO collector_kv (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
                                               updated_at = now()""",
            (AUDIT_KEY, payload))
