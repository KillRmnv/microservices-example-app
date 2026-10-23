"""Booking holds: PENDING (10 min TTL) -> CONFIRMED | EXPIRED.

Real ticket issuance against booking-service needs user auth passthrough
and lands in stage 3b; holds already prevent double intent and feed the
confirm-booking dialogue step.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Hold:
    id: str
    session_id: str
    event_id: int
    zone: str
    price: float
    party_size: int
    status: str


def _to_hold(row) -> Hold:
    return Hold(
        id=str(row["id"]), session_id=row["session_id"], event_id=row["event_id"],
        zone=row["zone"], price=float(row["price"]), party_size=row["party_size"],
        status=row["status"],
    )


def create_hold(conn, session_id: str, event_id: int, zone: str,
                price: float, party_size: int = 1) -> Hold:
    row = conn.execute(
        """INSERT INTO booking_holds (session_id, event_id, zone, price, party_size)
           VALUES (%s, %s, %s, %s, %s)
           RETURNING id, session_id, event_id, zone, price, party_size, status""",
        (session_id, event_id, zone, price, max(1, party_size)),
    ).fetchone()
    conn.commit()
    return _to_hold(row)


def confirm_hold(conn, hold_id: str) -> Hold | None:
    """Confirm a live hold; expired ones flip to EXPIRED and return None."""
    row = conn.execute(
        "SELECT id, session_id, event_id, zone, price, party_size, status,"
        " expires_at < now() AS past_due FROM booking_holds WHERE id = %s",
        (hold_id,),
    ).fetchone()
    if row is None or row["status"] != "PENDING":
        return None
    if row["past_due"]:
        conn.execute("UPDATE booking_holds SET status = 'EXPIRED' WHERE id = %s",
                     (hold_id,))
        conn.commit()
        return None
    row = conn.execute(
        """UPDATE booking_holds SET status = 'CONFIRMED', confirmed_at = now()
           WHERE id = %s
           RETURNING id, session_id, event_id, zone, price, party_size, status""",
        (hold_id,),
    ).fetchone()
    conn.commit()
    return _to_hold(row)


def expire_holds(conn) -> int:
    """Sweep for cron (stage 5 calls this on schedule)."""
    rows = conn.execute(
        """UPDATE booking_holds SET status = 'EXPIRED'
           WHERE status = 'PENDING' AND expires_at < now()
           RETURNING id""",
    ).fetchall()
    conn.commit()
    return len(rows)
