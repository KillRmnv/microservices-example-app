"""Operational use cases: source health, alerting, Prometheus metrics."""
from __future__ import annotations

import logging

import httpx

from ..core import db
from ..core.config import Settings
from ..repositories import runs

log = logging.getLogger(__name__)


def degraded_sources(health: list[dict]) -> list[str]:
    return [entry["source"] for entry in health if entry["degraded"]]


async def post_alert(webhook_url: str, degraded: list[str],
                     transport: httpx.BaseTransport | None = None) -> bool:
    if not webhook_url or not degraded:
        return False
    text = ("dosug collector degraded: "
            + ", ".join(sorted(degraded))
            + " (0 new events twice in a row or run errors)")
    try:
        async with httpx.AsyncClient(timeout=15.0, transport=transport) as client:
            response = await client.post(webhook_url, json={"text": text})
            response.raise_for_status()
        log.warning("ops alert sent: %s", text)
        return True
    except Exception as exc:  # noqa: BLE001 — alerting must not break collection
        log.warning("ops alert failed: %s", exc)
        return False


def render_metrics(data: dict[str, list]) -> str:
    lines = []
    for row in data["totals"]:
        lines.append(
            f'collector_events_total{{source="{row["source"]}"}} {row["count"]}')
    for row in data["runs"]:
        lines.append(
            f'collector_runs_total{{source="{row["source"]}",'
            f'status="{row["status"]}"}} {row["count"]}')
    for row in data["errors"]:
        lines.append(
            f'collector_parse_errors_total{{source="{row["source"]}"}}'
            f' {row["errors"] or 0}')
        lines.append(
            f'collector_fetch_errors_total{{source="{row["source"]}"}}'
            f' {row["fetch_errors"] or 0}')
    for row in data["last"]:
        lines.append(
            f'collector_last_run_unixtime{{source="{row["source"]}"}}'
            f' {int(row["ts"] or 0)}')
    return "\n".join(lines) + "\n"


class OpsService:
    def __init__(self, db_url: str, settings: Settings) -> None:
        self._db_url = db_url
        self._settings = settings

    def collect_health(self) -> dict:
        with db.get_conn(self._db_url) as conn:
            health = runs.health(conn, self._settings.ops_alert_window)
        return {"sources": health, "degraded": degraded_sources(health)}

    async def alert_check(self) -> dict:
        health = self.collect_health()
        sent = await post_alert(self._settings.ops_webhook_url, health["degraded"])
        return {"degraded": health["degraded"], "alert_sent": sent}

    def metrics(self) -> str:
        with db.get_conn(self._db_url) as conn:
            return render_metrics(runs.metrics(conn))
