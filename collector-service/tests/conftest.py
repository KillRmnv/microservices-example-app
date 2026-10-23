"""Shared test postgres (skips when unreachable).

Each service migrates its OWN test database: migration filenames collide
across services (V1__init.sql), so sharing one database silently skips
migrations via the common schema_migrations table.
"""
import os
import re

import psycopg
import pytest

from app import db

TEST_DB = "collector_pytest"


def pg_url() -> str:
    base = os.environ.get(
        "COLLECTOR_TEST_DATABASE_URL",
        "postgresql://postgres:1234@localhost:5432/postgres",
    )
    sep = "&" if "?" in base else "?"
    maintenance = f"{base}{sep}connect_timeout=5"
    with psycopg.connect(maintenance, autocommit=True) as conn:
        exists = conn.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{TEST_DB}"')
    return re.sub(r"/[^/]*(\?.*)?$", f"/{TEST_DB}\\1", maintenance)


@pytest.fixture()
def conn():
    try:
        url = pg_url()
        db.run_migrations(url)
    except Exception as exc:  # noqa: BLE001 — no postgres here, skip
        pytest.skip(f"no test postgres: {exc}")
    with db.get_conn(url) as connection:
        yield connection
        connection.rollback()
        connection.execute("TRUNCATE event_sources, screenings, collected_events, source_runs")
        connection.commit()
