"""source_runs persistence and health rollups."""
from __future__ import annotations

from ..sources.base import RunStats


def record(conn, source: str, status: str, stats: RunStats,
           error: str | None, duration_s: float) -> None:
    conn.execute(
        """INSERT INTO source_runs
           (source, status, started_at, finished_at, duration_s,
            fetched, parsed, parse_errors, duplicates, new_events, error)
           VALUES (%s, %s, now() - make_interval(secs => %s), now(), %s,
                   %s, %s, %s, %s, %s, %s)""",
        (source, status, duration_s, duration_s,
         stats.fetched, stats.parsed, stats.parse_errors,
         stats.duplicates, stats.new_events, error),
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
            """SELECT status, new_events, parse_errors, started_at, error
               FROM source_runs WHERE source = %s
               ORDER BY started_at DESC LIMIT %s""",
            (row["source"], window),
        ).fetchall()
        runs = [dict(run) for run in runs]
        degraded = (
            len(runs) == 0
            or any(run["status"] == "error" for run in runs)
            or (len(runs) == window and all(run["new_events"] == 0 for run in runs))
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
            "SELECT source, sum(parse_errors) AS errors FROM source_runs"
            " GROUP BY source").fetchall(),
        "last": conn.execute(
            "SELECT source, extract(epoch FROM max(started_at)) AS ts"
            " FROM source_runs GROUP BY source").fetchall(),
    }
