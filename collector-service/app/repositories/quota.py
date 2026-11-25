"""Monthly API quota guard (2GIS demo key: 1000 req/month).

Every billable request consumes one unit BEFORE firing; the caller raises
``QuotaExhausted`` when the returned bool is False.
"""
from __future__ import annotations

from datetime import datetime, timezone


def current_month(now=None) -> str:
    moment = now or datetime.now(timezone.utc)
    return moment.strftime("%Y-%m")


def used(conn, provider: str, month: str) -> int:
    row = conn.execute(
        "SELECT used FROM api_quota WHERE provider = %s AND month = %s",
        (provider, month),
    ).fetchone()
    return int(row["used"]) if row else 0


def try_consume(conn, provider: str, month: str, cap: int, reserve: int) -> bool:
    """Consume one unit atomically; False (no consume) at cap - reserve."""
    conn.execute(
        """INSERT INTO api_quota (provider, month, used) VALUES (%s, %s, 0)
           ON CONFLICT (provider, month) DO NOTHING""",
        (provider, month),
    )
    # Single conditional UPDATE: concurrent consumers cannot both pass the
    # cap check after reading the same stale counter.
    row = conn.execute(
        """UPDATE api_quota SET used = used + 1
           WHERE provider = %s AND month = %s AND used < %s
           RETURNING used""",
        (provider, month, cap - reserve),
    ).fetchone()
    return row is not None
