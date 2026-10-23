"""Shared test postgres (skips when unreachable)."""
import os

import pytest

from app import db


def pg_url() -> str:
    base = os.environ.get(
        "COLLECTOR_TEST_DATABASE_URL",
        "postgresql://postgres:1234@localhost:5432/postgres",
    )
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}connect_timeout=5"


@pytest.fixture()
def conn():
    try:
        db.run_migrations(pg_url())
    except Exception as exc:  # noqa: BLE001 — no postgres here, skip
        pytest.skip(f"no test postgres: {exc}")
    with db.get_conn(pg_url()) as connection:
        yield connection
        connection.rollback()  # clear a possibly aborted test transaction
        connection.execute("TRUNCATE event_sources, screenings, collected_events, source_runs")
        connection.commit()
