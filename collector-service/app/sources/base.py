"""Source adapter contract. Stage 1 adds ticketpro/relax/afisha_me/telegram."""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RunStats:
    fetched: int = 0
    parsed: int = 0
    parse_errors: int = 0
    duplicates: int = 0
    new_events: int = 0


@dataclass
class SourceRun:
    source: str
    status: str = "running"
    stats: RunStats = field(default_factory=RunStats)
    error: str | None = None
    started_at: float = field(default_factory=time.monotonic)


class SourceAdapter(ABC):
    """One adapter per source. Must be polite (use PoliteClient) and honest
    (record a source_run row even on failure)."""

    name: str

    @abstractmethod
    async def collect(self, ctx: "CollectContext") -> RunStats:
        """Fetch + parse + store. Returns counters for the source_runs row."""
        raise NotImplementedError


@dataclass
class CollectContext:
    http: object  # PoliteClient (typed loosely to avoid a cycle)
    db_url: str
    # Canary runs: cap card URLs (sitemap adapters) / pages (ticketpro).
    max_urls: int | None = None
