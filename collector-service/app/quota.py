"""Monthly API quota guard (2GIS demo key: 1000 req/month).

Every billable request consumes one unit BEFORE firing; when
used >= cap - reserve the run stops with QuotaExhausted instead of
burning the key into errors.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


class QuotaExhausted(RuntimeError):
    pass


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
    """Consume one unit; False (no consume) when at cap - reserve."""
    conn.execute(
        """INSERT INTO api_quota (provider, month, used) VALUES (%s, %s, 0)
           ON CONFLICT (provider, month) DO NOTHING""",
        (provider, month),
    )
    row = conn.execute(
        "SELECT used FROM api_quota WHERE provider = %s AND month = %s",
        (provider, month),
    ).fetchone()
    current = int(row["used"])
    if current >= cap - reserve:
        return False
    conn.execute(
        "UPDATE api_quota SET used = used + 1 WHERE provider = %s AND month = %s",
        (provider, month),
    )
    return True
