"""dialogue_runs persistence (observability only)."""
from __future__ import annotations


def record_run(conn, contract, duration_ms: int) -> None:
    conn.execute(
        """INSERT INTO dialogue_runs
           (session_id, turn, action, needs_clarification, duration_ms)
           VALUES (%s, %s, %s, %s, %s)""",
        (contract.context_state.session_id,
         contract.context_state.turn_count,
         contract.dialogue_action,
         contract.needs_clarification,
         duration_ms),
    )
    conn.commit()


def action_metrics(conn) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT action, count(*) AS count FROM dialogue_runs GROUP BY action"
    ).fetchall()
    return [(row["action"], int(row["count"])) for row in rows]
