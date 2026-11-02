"""One-shot cleanup of already-stored event descriptions.

Run from ``collector-service/``:

    python -m app.clean_descriptions              # apply
    python -m app.clean_descriptions --dry-run    # report only

Uses the regular ``COLLECTOR_DATABASE_URL`` config.  Rows are processed in
keyset batches ordered by ``id``; an UPDATE only fires when the cleaned text
differs, so repeated runs are idempotent.  Changed descriptions also reset
``embedded_at`` so the embed catch-up re-indexes their vectors.
"""
from __future__ import annotations

import argparse
import logging

from .core import db
from .core.config import settings
from .text import clean_text

log = logging.getLogger(__name__)

DEFAULT_BATCH_SIZE = 500
ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def clean_batch(conn, after: str, batch_size: int, dry_run: bool) -> tuple[int, int, str]:
    """Clean one keyset page; returns (scanned, changed, last_id)."""
    rows = conn.execute(
        """SELECT id::text AS id, description
             FROM collected_events
            WHERE description IS NOT NULL
              AND id > %s::uuid
            ORDER BY id
            LIMIT %s""",
        (after, batch_size),
    ).fetchall()

    changed = 0
    last_id = after
    for row in rows:
        last_id = row["id"]
        cleaned = clean_text(row["description"])
        if cleaned == row["description"]:
            continue
        changed += 1
        if dry_run:
            continue
        conn.execute(
            """UPDATE collected_events
                  SET description = %s, embedded_at = NULL
                WHERE id = %s::uuid
                  AND description IS DISTINCT FROM %s""",
            (cleaned, row["id"], cleaned),
        )
    return len(rows), changed, last_id


def clean_all(database_url: str, batch_size: int = DEFAULT_BATCH_SIZE,
              dry_run: bool = False) -> tuple[int, int]:
    """Clean every non-null description; returns (scanned, changed)."""
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")

    total_scanned = total_changed = 0
    after = ZERO_UUID
    with db.get_conn(database_url) as conn:
        while True:
            scanned, changed, last_id = clean_batch(
                conn, after, batch_size, dry_run)
            if not dry_run:
                conn.commit()
            total_scanned += scanned
            total_changed += changed
            log.info("batch: scanned=%d changed=%d", scanned, changed)
            if scanned < batch_size:
                break
            after = last_id
    return total_scanned, total_changed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Strip emoji/Telegram decoration from collected descriptions.")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                        help=f"rows per transaction (default: {DEFAULT_BATCH_SIZE})")
    parser.add_argument("--dry-run", action="store_true",
                        help="report what would change without writing")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    url = settings.require_database_url()
    scanned, changed = clean_all(url, args.batch_size, args.dry_run)
    verb = "would clean" if args.dry_run else "cleaned"
    log.info("done: scanned=%d %s=%d", scanned, verb, changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
