"""Postgres access + SQL migration runner.

Runner semantics:
- ``V<n>__name.sql`` files are applied in **numeric** order (V2 before V10),
  tracked in ``schema_migrations``;
- each file is executed as a single multi-statement script inside the batch
  transaction, so a failure rolls everything back;
- an advisory lock serialises concurrent service replicas at startup;
- a SHA-256 checksum is stored so editing an already-applied migration is
  detected on the next start instead of being silently ignored.
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

log = logging.getLogger(__name__)

MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"
_LOCK_KEY = "schema_migrations"
_VERSION_RE = re.compile(r"^V(\d+)__")


class MigrationChanged(RuntimeError):
    pass


def _version_key(path: Path) -> tuple[int, str]:
    match = _VERSION_RE.match(path.name)
    if not match:
        raise ValueError(f"migration name must look like V<n>__name.sql: {path.name}")
    return int(match.group(1)), path.name


def migration_files() -> list[Path]:
    return sorted(MIGRATIONS_DIR.glob("*.sql"), key=_version_key)


def _checksum(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run_migrations(database_url: str) -> list[str]:
    if not database_url:
        raise RuntimeError("database_url is required to run migrations")
    applied: list[str] = []
    with psycopg.connect(database_url) as conn:
        conn.execute("SELECT pg_advisory_lock(hashtext(%s))", (_LOCK_KEY,))
        try:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(name TEXT PRIMARY KEY, applied_at TIMESTAMPTZ DEFAULT now())")
            conn.execute(
                "ALTER TABLE schema_migrations ADD COLUMN IF NOT EXISTS checksum TEXT")
            done = {
                row[0]: row[1]
                for row in conn.execute(
                    "SELECT name, checksum FROM schema_migrations")
            }
            for path in migration_files():
                text = path.read_text()
                checksum = _checksum(text)
                if path.name in done:
                    if done[path.name] and done[path.name] != checksum:
                        raise MigrationChanged(
                            f"migration {path.name} changed after being applied")
                    continue
                log.info("applying migration %s", path.name)
                conn.execute(text)
                conn.execute(
                    "INSERT INTO schema_migrations (name, checksum) VALUES (%s, %s)",
                    (path.name, checksum))
                applied.append(path.name)
            conn.commit()
        finally:
            conn.execute("SELECT pg_advisory_unlock(hashtext(%s))", (_LOCK_KEY,))
            conn.commit()
    return applied


def get_conn(database_url: str):
    return psycopg.connect(database_url, row_factory=dict_row)
