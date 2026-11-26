"""source_runs persistence and health rollups.

Statuses: ok | partial | error | skipped | quota_exhausted.
Degraded = hard failure in the window, or a full window with zero
inserted rows (dry source). Per-card noise (parse/fetch errors inside an
otherwise fine run) does not flap health by itself.
"""
from __future__ import annotations

from ..sources.base import RunStats

BAD_STATUSES = ("error", "quota_exhausted")


def record(conn, source: str, status: str, stats: RunStats,
           error: str | None, duration_s: float,
           error_code: str | None = None) -> None:
    conn.execute(
        """INSERT INTO source_runs
           (source, status, started_at, finished_at, duration_s,
            fetched, parsed, parse_errors, fetch_errors, duplicates,
            rows_inserted, rows_updated, quota_stopped, error_code, error)
           VALUES (%s, %s, now() - make_interval(secs => %s), now(), %s,
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
        (source, status, duration_s, duration_s,
         stats.fetched, stats.parsed, stats.parse_errors, stats.fetch_errors,
         stats.duplicates, stats.rows_inserted, stats.rows_updated,
         stats.quota_stopped, error_code, error),
    )
    conn.commit()


def health(conn, window: int) -> list[dict]:
    """Last `window` runs per source for /collect/health and alerting."""
    sources = conn.execute(
        "SELECT DISTINCT ON (source) source FROM source_runs ORDER BY source"
    ).fetchall()
    result = []
    for row in sources:
        runs = conn.execute(
            """SELECT status, rows_inserted, parse_errors, fetch_errors,
                      started_at, error_code, error
               FROM source_runs WHERE source = %s
               ORDER BY started_at DESC LIMIT %s""",
            (row["source"], window),
        ).fetchall()
        runs = [dict(run) for run in runs]
        degraded = (
            len(runs) == 0
            or any(run["status"] in BAD_STATUSES for run in runs)
            or (len(runs) == window and all(run["rows_inserted"] == 0 for run in runs))
        )
        result.append({"source": row["source"], "runs": runs,
                       "degraded": degraded})
    return result


def metrics(conn) -> dict[str, list]:
    return {
        "totals": conn.execute(
            "SELECT source, count(*) AS count FROM collected_events GROUP BY source"
        ).fetchall(),
        "runs": conn.execute(
            "SELECT source, status, count(*) AS count FROM source_runs"
            " GROUP BY source, status").fetchall(),
        "errors": conn.execute(
            "SELECT source, sum(parse_errors) AS errors,"
            " sum(fetch_errors) AS fetch_errors FROM source_runs"
            " GROUP BY source").fetchall(),
        "last": conn.execute(
            "SELECT source, extract(epoch FROM max(started_at)) AS ts"
            " FROM source_runs GROUP BY source").fetchall(),
    }
