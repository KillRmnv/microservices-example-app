"""Atmosphere lexicon, migration and enrichment service tests."""
from __future__ import annotations

import pytest

from app.core import db
from app.parsing.atmosphere import (atmosphere_from_rubric, atmosphere_tags,
                                    atmosphere_text)
from app.services import atmosphere_service as atmosphere_module
from app.services.atmosphere_service import AtmosphereService, review_texts

MIGRATION = "V4__venue_atmosphere.sql"


def test_lexicon_maps_russian_review_phrases():
    tags = atmosphere_tags(
        "Очень уютное и тихое место, играет живая музыка")
    assert tags == ["quiet", "cozy", "live_music"]

    assert atmosphere_tags(
        "Шумно, много людей, не протолкнуться") == ["loud", "crowded"]
    assert atmosphere_tags(
        "Кальян, веранда, можно с детьми") == [
        "hookah", "outdoor", "kids_friendly"]
    assert atmosphere_tags(
        "Романтический ужин при свечах") == ["romantic"]
    assert atmosphere_tags(
        "Идеально для деловой встречи с ноутбуком") == ["business"]
    assert atmosphere_tags(
        "Крафтовый бар с винилом, модное место") == ["hipster", "trendy"]


def test_lexicon_respects_explicit_negation():
    # "не шумно" must not produce `loud`; quiet stems still win.
    assert atmosphere_tags("Не шумно, без музыки, спокойно") == ["quiet"]
    assert atmosphere_tags("Без веранды и без кальяна") == []


def test_lexicon_empty_and_unknown_text():
    assert atmosphere_tags(None) == []
    assert atmosphere_tags("") == []
    assert atmosphere_tags("Просто описание без маркеров") == []


def test_tag_text_round_trip():
    assert atmosphere_text(["cozy", "live_music"]) == "уютно, живая музыка"
    # Canonical tag order, unknown tags ignored.
    assert atmosphere_text(["live_music", "unknown", "quiet"]) == \
        "тихо, живая музыка"
    assert atmosphere_text([]) == ""


def test_rubric_heuristics_are_conservative():
    assert atmosphere_from_rubric("Бар 7", "Бары") == ["loud", "trendy"]
    assert atmosphere_from_rubric("Библиотека им. Пушкина", "Библиотеки") == \
        ["quiet"]
    assert atmosphere_from_rubric("Кофейня", "Кафе") == ["cozy"]
    assert atmosphere_from_rubric("Караоке-клуб", "Караоке") == [
        "live_music", "loud"]
    assert atmosphere_from_rubric("Книги", "Книги") == ["quiet"]
    assert atmosphere_from_rubric(
        "Выставка", "Художественные выставки") == ["atmospheric"]
    assert atmosphere_from_rubric("Аптека", "Аптеки") == []


def test_review_texts_tolerates_missing_and_string_raw():
    assert review_texts({}) == ""
    assert review_texts(None) == ""
    assert review_texts({"reviews": {"items": [{"tag": "2gis_reviews"}]}}) == ""
    assert review_texts(
        '{"reviews": {"items": [{"text": "Тихо и уютно"}]}}') == "Тихо и уютно"


def test_migration_is_ordered_and_idempotent():
    names = [path.name for path in db.migration_files()]
    assert MIGRATION in names
    assert names.index(MIGRATION) > names.index(
        "V3__availability_and_venue_enrichment.sql")
    text = (db.MIGRATIONS_DIR / MIGRATION).read_text()
    assert "ADD COLUMN IF NOT EXISTS atmosphere JSONB" in text


def test_migration_adds_nullable_jsonb_column(conn):
    row = conn.execute(
        """SELECT data_type, is_nullable
             FROM information_schema.columns
            WHERE table_name = 'collected_venues'
              AND column_name = 'atmosphere'""").fetchone()
    assert row is not None
    assert row["data_type"] == "jsonb"
    assert row["is_nullable"] == "YES"


class _Result:
    def __init__(self, rows=None, row=None, rowcount=0):
        self._rows = rows or []
        self._row = row
        self.rowcount = rowcount

    def fetchall(self):
        return self._rows

    def fetchone(self):
        return self._row


class FakeConn:
    """Minimal DB-API stand-in: candidate SELECT + atmosphere UPDATE."""

    def __init__(self, rows, rowcount: int = 1):
        self.rows = rows
        self.updates: list[tuple] = []
        self.commits = 0
        self._rowcount = rowcount

    def execute(self, sql, params=None):
        normalized = " ".join(sql.split())
        if normalized.startswith("SELECT v.id"):
            return _Result(rows=self.rows)
        if normalized.startswith("UPDATE collected_venues"):
            self.updates.append(params)
            return _Result(rowcount=self._rowcount)
        raise AssertionError(f"unexpected SQL: {normalized[:80]}")

    def commit(self):
        self.commits += 1

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _service(monkeypatch, fake: FakeConn) -> AtmosphereService:
    monkeypatch.setattr(atmosphere_module.db, "get_conn",
                        lambda url: fake)
    return AtmosphereService("postgresql://unused")


def test_enrichment_writes_and_is_idempotent(monkeypatch):
    row = {
        "id": "00000000-0000-0000-0000-000000000001",
        "name": "Кофейня",
        "rubric": "Кафе",
        "atmosphere": None,
        "raw": {},
        "event_text": "Тихо, уютно, играет живая музыка",
    }
    fake = FakeConn([row])
    service = _service(monkeypatch, fake)

    first = service.enrich(limit=10)
    assert first == {"venues": 1, "tagged": 1, "updated": 1,
                     "unchanged": 0, "limit": 10, "force": False}
    assert fake.updates == [(('["quiet", "cozy", "live_music"]'),
                             row["id"], '["quiet", "cozy", "live_music"]')]

    # Simulate the stored value: an identical recomputation is a no-op.
    row["atmosphere"] = ["quiet", "cozy", "live_music"]
    fake.updates.clear()
    second = service.enrich(limit=10)
    assert second["updated"] == 0 and second["unchanged"] == 1
    assert fake.updates == []

    forced = service.enrich(limit=10, force=True)
    assert forced["updated"] == 1
    assert len(fake.updates) == 1


def test_enrichment_falls_back_when_text_is_empty(monkeypatch):
    row = {
        "id": "00000000-0000-0000-0000-000000000002",
        "name": "Библиотека",
        "rubric": "Библиотеки",
        "atmosphere": None,
        "raw": {},
        "event_text": None,
    }
    fake = FakeConn([row])
    service = _service(monkeypatch, fake)

    result = service.enrich(limit=2000)
    assert result["limit"] == 1000  # clamped
    assert fake.updates[0][0] == '["quiet"]'


def test_enrichment_prefers_review_text_over_event_text(monkeypatch):
    row = {
        "id": "00000000-0000-0000-0000-000000000003",
        "name": "Кафе",
        "rubric": "Кафе",
        "atmosphere": None,
        "raw": {"reviews": {"items": [{"text": "Очень шумно и многолюдно"}]}},
        "event_text": "Тихое место",
    }
    fake = FakeConn([row])
    service = _service(monkeypatch, fake)

    service.enrich(limit=1)
    assert fake.updates[0][0] == '["loud", "crowded"]'


def test_enrichment_database_round_trip(conn, database_url):
    venue_id = conn.execute(
        """INSERT INTO collected_venues
               (source, source_id, name, rubric, city)
           VALUES ('twogis', 'atmo-1', 'Кофейня', 'Кафе', 'Минск')
           RETURNING id""").fetchone()["id"]
    conn.execute(
        """INSERT INTO collected_events
               (source, source_id, source_url, title, venue_id, description,
                city)
           VALUES ('telegram', 'atmo-e1', 'http://x/atmo', 'Вечер', %s,
                   'Тихо, уютно, играет живая музыка', 'Минск')""",
        (venue_id,))
    conn.execute("UPDATE collected_venues SET embedded_at = now()"
                 " WHERE id = %s", (venue_id,))
    conn.commit()

    service = AtmosphereService(database_url)
    first = service.enrich(limit=10)
    assert first["updated"] == 1 and first["tagged"] == 1
    stored = conn.execute(
        "SELECT atmosphere, embedded_at FROM collected_venues WHERE id = %s",
        (venue_id,)).fetchone()
    assert stored["atmosphere"] == ["quiet", "cozy", "live_music"]
    assert stored["embedded_at"] is None

    second = service.enrich(limit=10)
    assert second["updated"] == 0 and second["unchanged"] == 1


def test_enrichment_counts_untagged_rows(monkeypatch):
    row = {
        "id": "00000000-0000-0000-0000-000000000004",
        "name": "Аптека",
        "rubric": "Аптеки",
        "atmosphere": None,
        "raw": {},
        "event_text": "",
    }
    fake = FakeConn([row], rowcount=0)
    result = _service(monkeypatch, fake).enrich(limit=1)
    # An empty array still marks the row as processed, but the DB guard says
    # "no change" on a fake row that already reported a match.
    assert result["tagged"] == 0 and result["updated"] == 0
