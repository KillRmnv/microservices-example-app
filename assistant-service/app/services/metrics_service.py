"""Prometheus text exposition built from repository counters."""
from __future__ import annotations

from ..core import db
from ..repositories import dialogue_runs, holds


class MetricsService:
    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    def render(self) -> str:
        with db.get_conn(self._db_url) as conn:
            dialogue = dialogue_runs.action_metrics(conn)
            hold_rows = holds.status_metrics(conn)
        lines = [
            f'assistant_dialogue_runs_total{{action="{action}"}} {count}'
            for action, count in dialogue
        ]
        lines += [
            f'assistant_holds{{status="{status}"}} {count}'
            for status, count in hold_rows
        ]
        return "\n".join(lines) + "\n"
