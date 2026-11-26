"""Embedding backfill use case (events + venues collections).

Each point carries dense + sparse vectors and a filterable payload, so the
assistant can run hybrid search fully inside Qdrant.
"""
from __future__ import annotations

import json
import logging
import re
from contextlib import contextmanager

import psycopg

from ..core import db
from ..core.config import Settings
from ..clients.embeddings import EmbeddingProvider, embeddable_text
from ..parsing.atmosphere import atmosphere_text
from ..parsing.schedule import normalize_schedule
from ..repositories import queries
from ..core.sparse import encode_sparse
from ..clients.vector import VectorPoint, VectorStore

log = logging.getLogger(__name__)

# Bump when the Qdrant payload contract changes in a way that needs a
# `/embed/reindex-hybrid` pass (payload keys only; dense vectors are kept).
PAYLOAD_VERSION = 4
PAYLOAD_VERSION_KEY = "embed:payload_version"


def applied_payload_version(db_url: str) -> int | None:
    """Version stored in `collector_kv`; None when absent or unreadable."""
    with db.get_conn(db_url) as conn:
        row = conn.execute(
            "SELECT value FROM collector_kv WHERE key = %s",
            (PAYLOAD_VERSION_KEY,)).fetchone()
    if row is None or row["value"] is None:
        return None
    try:
        return int(row["value"])
    except (TypeError, ValueError):
        return None


def store_payload_version(db_url: str,
                          version: int = PAYLOAD_VERSION) -> None:
    with db.get_conn(db_url) as conn:
        conn.execute(
            """INSERT INTO collector_kv (key, value) VALUES (%s, %s)
               ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value,
                                               updated_at = now()""",
            (PAYLOAD_VERSION_KEY, str(version)))
        conn.commit()


@contextmanager
def payload_version_lock(db_url: str, key: str = PAYLOAD_VERSION_KEY):
    """Yields True when this process won the reindex lock."""
    with psycopg.connect(db_url) as conn:
        locked = bool(conn.execute(
            "SELECT pg_try_advisory_lock(hashtext(%s))", (key,)).fetchone()[0])
        try:
            yield locked
        finally:
            if locked:
                conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (key,))
                conn.commit()


def payload_version_info(db_url: str) -> dict:
    """Applied/expected payload contract version for health + startup."""
    applied = applied_payload_version(db_url)
    return {"applied": applied, "expected": PAYLOAD_VERSION,
            "mismatch": applied != PAYLOAD_VERSION}


def _iso(value) -> str:
    return value.isoformat() if value else ""


def _float(value) -> float | None:
    return float(value) if value is not None else None


def _int(value) -> int | None:
    return int(value) if value is not None else None


def _batches(rows: list, size: int):
    for offset in range(0, len(rows), size):
        yield rows[offset:offset + size]


def _event_text(row) -> str:
    return embeddable_text(row["title"], row["venue_name"], row["description"])


def _atmosphere_list(value) -> list[str]:
    if isinstance(value, (list, tuple)):
        return [str(item) for item in value if item]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return []
        return _atmosphere_list(parsed)
    return []


def _venue_text(row) -> str:
    # Atmosphere words are Russian on purpose: the tag vocabulary stays ASCII
    # in the payload, while dense/sparse/BM25 match «уютно, живая музыка».
    return "\n".join(part for part in
                     [row["name"], row["rubric"], row["address"],
                      atmosphere_text(_atmosphere_list(row["atmosphere"]))]
                     if part)


def _film_payload(row) -> tuple[list[str], int | None]:
    """Bycard film metadata -> (genres, duration minutes)."""
    try:
        raw = row["film_meta"]
    except (KeyError, IndexError):
        raw = None
    if not isinstance(raw, dict):
        return [], None
    genres = [str(item) for item in (raw.get("genre") or []) if item]
    minutes = _int(raw.get("duration_minutes"))
    if minutes is None:
        match = re.match(r"^PT(?:(\d+)H)?(?:(\d+)M)?$",
                         str(raw.get("duration") or ""))
        if match:
            hours = int(match.group(1) or 0)
            mins = int(match.group(2) or 0)
            minutes = hours * 60 + mins or None
    return genres, minutes


def _event_payload(row) -> dict:
    try:
        end_at = row["end_at"]
    except (KeyError, IndexError):
        end_at = None
    try:
        availability_at = _iso(row["fetched_at"])
    except (KeyError, IndexError):
        availability_at = ""
    start_at = row["start_at"]
    # Single-day events have no end; store the start as the interval end so
    # the assistant can filter by overlap without special-casing the payload.
    interval_end = end_at or start_at
    film_genres, film_minutes = _film_payload(row)
    return {
        "title": row["title"],
        "source": row["source"],
        "city": row["city"],
        "category": row["category"],
        "venue": row["venue_name"] or "",
        "address": row["address"] or "",
        "start_at": start_at.isoformat() if start_at else "",
        "end_at": interval_end.isoformat() if interval_end else "",
        "price_min": _float(row["price_min"]),
        "price_max": _float(row["price_max"]),
        "booking_event_id": _int(row["booking_event_id"]),
        # Availability/capacity and the linked 2GIS venue (map + ranking).
        "status": row["status"] or "scheduled",
        "age_limit": _int(row["age_limit"]),
        "currency": row["currency"] or "",
        "capacity": _int(row["capacity"]),
        "seats_left": _int(row["seats_left"]),
        "venue_id": str(row["venue_id"]) if row["venue_id"] is not None else None,
        "lat": _float(row["venue_lat"]),
        "lon": _float(row["venue_lon"]),
        "venue_rating": _float(row["venue_rating"]),
        "venue_review_count": _int(row["venue_review_count"]),
        # Bycard film metadata (genre/duration) when the title matched.
        "film_genre": film_genres or None,
        "film_duration_min": film_minutes,
        # When the source row was last fetched. The assistant applies a TTL to
        # seats_left/status using this stamp; "" means "unknown freshness".
        "availability_at": availability_at,
        # Same string as the dense embedding, so BM25 and dense rank the
        # same text (title + venue + description, no category/rubric leaks).
        "search_text": _event_text(row),
    }


def _amenity_list(value) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return []


def _venue_payload(row) -> dict:
    # hours/is_24_7 are derived from the raw 2GIS schedule at embed time; the
    # parsed shape is part of the shared payload contract.
    hours, is_24_7 = normalize_schedule(row["schedule"])
    return {
        "name": row["name"],
        "source": row["source"],
        "city": row["city"],
        "rubric": row["rubric"] or "",
        "address": row["address"] or "",
        "lat": _float(row["latitude"]),
        "lon": _float(row["longitude"]),
        "rating": _float(row["rating"]),
        "review_count": _int(row["review_count"]),
        "hours": hours,
        "is_24_7": is_24_7,
        "amenities": _amenity_list(row["amenities"]),
        "avg_check": _float(row["avg_check"]),
        "price_level": row["price_level"] or None,
        "district": row["district"] or None,
        "atmosphere": _atmosphere_list(row["atmosphere"]),
        "search_text": _venue_text(row),
    }


def _to_points(rows, vectors: list[list[float]], texts: list[str],
               payload_of) -> list[VectorPoint]:
    return [
        VectorPoint(id=str(row["id"]), vector=vector,
                    payload=payload_of(row), sparse=encode_sparse(text))
        for row, vector, text in zip(rows, vectors, texts)
    ]


class EmbedService:
    def __init__(self, db_url: str, embedder: EmbeddingProvider,
                 vector: VectorStore, vector_venues: VectorStore,
                 settings: Settings, lock_db_url: str | None = None) -> None:
        self._db_url = db_url
        # Advisory locks need a direct Postgres session (pgbouncer reuses
        # backends); the catalog itself may go through the pooler.
        self._lock_db_url = lock_db_url or db_url
        self._embedder = embedder
        self._vector = vector
        self._vector_venues = vector_venues
        self._batch_size = max(1, settings.embed_batch_size)
        self._payload_sync_started = False

    def payload_version_state(self) -> dict:
        """Applied/expected version; never raises (health endpoint safety)."""
        try:
            return payload_version_info(self._db_url)
        except Exception as exc:  # noqa: BLE001 — DB may be briefly unavailable
            return {"applied": None, "expected": PAYLOAD_VERSION,
                    "mismatch": True, "error": str(exc)}

    def record_payload_version(self) -> None:
        """Stamp the current payload contract; a write failure only logs."""
        try:
            store_payload_version(self._db_url)
        except Exception as exc:  # noqa: BLE001 — reindex already succeeded
            log.warning("payload version write failed: %s", exc)

    async def ensure_payload_version(self) -> dict:
        """Reindex once when the stored payload contract version changed.

        Runs as a non-blocking startup task: matching version is a no-op,
        concurrent processes are serialised by an advisory lock, failures keep
        the old version and are logged instead of crashing startup.
        """
        if self._payload_sync_started:
            return {"checked": False, "reason": "already_checked",
                    **self.payload_version_state()}
        self._payload_sync_started = True
        state = self.payload_version_state()
        if not state["mismatch"]:
            return {"checked": True, "reindexed": False, **state}
        try:
            with payload_version_lock(self._lock_db_url) as locked:
                if not locked:
                    log.info("payload version reindex skipped: locked elsewhere")
                    return {"checked": True, "reindexed": False,
                            "reason": "locked", **state}
                # A peer may have applied it while we were waiting for the lock.
                state = payload_version_info(self._db_url)
                if not state["mismatch"]:
                    return {"checked": True, "reindexed": False,
                            "reason": "updated_by_peer", **state}
                log.info("payload version %s -> %s: hybrid reindex",
                         state["applied"], PAYLOAD_VERSION)
                result = await self.reindex_hybrid()
                self.record_payload_version()
                return {"checked": True, "reindexed": True, "result": result,
                        **self.payload_version_state()}
        except Exception as exc:  # noqa: BLE001 — startup must survive
            log.warning("payload version ensure failed: %s", exc)
            return {"checked": True, "reindexed": False, "error": str(exc),
                    "applied": state.get("applied"),
                    "expected": PAYLOAD_VERSION, "mismatch": True}

    async def _embed_batch(self, rows, store: VectorStore, texts: list[str],
                           payload_of, marker) -> int:
        """Embed one batch, upsert, mark; returns embedded count (0 on error)."""
        try:
            vectors = await self._embedder.embed(texts)
        except Exception as exc:  # noqa: BLE001 — split oversized batches
            if len(texts) > 1:
                middle = len(texts) // 2
                left = await self._embed_batch(
                    rows[:middle], store, texts[:middle], payload_of, marker)
                right = await self._embed_batch(
                    rows[middle:], store, texts[middle:], payload_of, marker)
                return left + right
            log.warning("embed text failed: %s", exc)
            return 0
        try:
            await store.upsert(_to_points(rows, vectors, texts, payload_of))
        except Exception as exc:  # noqa: BLE001 — keep stored batches
            log.warning("embed batch failed: %s", exc)
            return 0
        with db.get_conn(self._db_url) as conn:
            marker(conn, [row["id"] for row in rows])
        return len(rows)

    async def embed_events(self, source: str = "all",
                           limit: int | None = None,
                           cap: int | None = None) -> tuple[int, int]:
        """Embed unembedded event rows; returns (embedded, pending)."""
        fetch_limit = limit
        if cap is not None:
            fetch_limit = min(limit or cap, cap)
        with db.get_conn(self._db_url) as conn:
            rows = queries.unembedded_events(conn, source, fetch_limit)
        embedded = 0
        for batch in _batches(rows, self._batch_size):
            texts = [_event_text(row) for row in batch]
            try:
                done = await self._embed_batch(
                    batch, self._vector, texts, _event_payload,
                    queries.mark_events_embedded)
            except Exception as exc:  # noqa: BLE001 — embedder down, stop
                log.warning("event embed batch failed: %s", exc)
                break
            if not done:
                break
            embedded += done
        return embedded, len(rows) - embedded

    async def embed_venues(self, limit: int | None = None) -> tuple[int, int]:
        with db.get_conn(self._db_url) as conn:
            rows = queries.unembedded_venues(conn, limit)
        embedded = 0
        for batch in _batches(rows, self._batch_size):
            texts = [_venue_text(row) for row in batch]
            try:
                done = await self._embed_batch(
                    batch, self._vector_venues, texts, _venue_payload,
                    queries.mark_venues_embedded)
            except Exception as exc:  # noqa: BLE001 — embedder down, stop
                log.warning("venue embed batch failed: %s", exc)
                break
            if not done:
                break
            embedded += done
        return embedded, len(rows) - embedded

    async def delete_events(self, ids: list[str]) -> int:
        """Drop Qdrant event points after a Postgres-side deletion."""
        if ids:
            await self._vector.delete(ids)
        return len(ids)

    async def reindex_hybrid(self) -> dict:
        """Backfill sparse vectors + payload into existing Qdrant points.

        Dense vectors are preserved (no LLM re-embed): sparse/payload are
        merged from Postgres rows. Qdrant-only orphans keep dense-only.
        """
        events = await self._reindex_collection(
            self._vector, "events", queries.all_events_for_reindex,
            _event_text, _event_payload)
        venues = await self._reindex_collection(
            self._vector_venues, "venues", queries.all_venues_for_reindex,
            _venue_text, _venue_payload)
        # Reindexing is what applies the payload contract: `POST
        # /embed/reindex-hybrid` and the startup check both stamp it here.
        self.record_payload_version()
        return {"events": events, "venues": venues}

    async def _reindex_collection(self, store: VectorStore, name: str,
                                  fetch_rows, text_of, payload_of) -> dict:
        with db.get_conn(self._db_url) as conn:
            rows = fetch_rows(conn)
        stored = {point.id: point for point in await store.scroll_all()}
        patched = 0
        patches = []
        for row in rows:
            row_id = str(row["id"])
            if row_id not in stored:
                continue  # gap rows are healed by the next /embed run
            patches.append(VectorPoint(id=row_id, sparse=encode_sparse(text_of(row)),
                                       payload=payload_of(row)))
            if len(patches) >= self._batch_size:
                await store.patch_points(patches)
                patched += len(patches)
                patches = []
        if patches:
            await store.patch_points(patches)
            patched += len(patches)
        log.info("hybrid reindex %s: %d patched, %d stored, %d rows",
                 name, patched, len(stored), len(rows))
        return {"patched": patched, "stored": len(stored), "rows": len(rows)}
