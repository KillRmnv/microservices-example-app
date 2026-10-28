"""booking_holds persistence. Pure SQL, no business rules."""
from __future__ import annotations

from ..models.hold import EXPIRED, Hold


def _to_hold(row) -> Hold:
    return Hold(
        id=str(row["id"]), session_id=row["session_id"], event_id=row["event_id"],
        zone=row["zone"], price=float(row["price"]), party_size=row["party_size"],
        status=row["status"],
    )


_HOLD_COLUMNS = "id, session_id, event_id, zone, price, party_size, status"


def create(conn, session_id: str, event_id: int, zone: str,
           price: float, party_size: int) -> Hold:
    row = conn.execute(
        f"""INSERT INTO booking_holds (session_id, event_id, zone, price, party_size)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING {_HOLD_COLUMNS}""",
        (session_id, event_id, zone, price, party_size),
    ).fetchone()
    conn.commit()
    return _to_hold(row)


def find_pending(conn, session_id: str, event_id: int) -> Hold | None:
    row = conn.execute(
        f"""SELECT {_HOLD_COLUMNS} FROM booking_holds
            WHERE session_id = %s AND event_id = %s AND status = 'PENDING'
            ORDER BY created_at DESC LIMIT 1""",
        (session_id, event_id),
    ).fetchone()
    return _to_hold(row) if row else None


def confirm(conn, hold_id: str) -> Hold | None:
    """Confirm a live hold; expired ones flip to EXPIRED and return None."""
    row = conn.execute(
        f"""SELECT {_HOLD_COLUMNS}, expires_at < now() AS past_due
            FROM booking_holds WHERE id = %s""",
        (hold_id,),
    ).fetchone()
    if row is None or row["status"] != "PENDING":
        return None
    if row["past_due"]:
        conn.execute("UPDATE booking_holds SET status = %s WHERE id = %s",
                     (EXPIRED, hold_id))
        conn.commit()
        return None
    row = conn.execute(
        f"""UPDATE booking_holds SET status = 'CONFIRMED', confirmed_at = now()
            WHERE id = %s RETURNING {_HOLD_COLUMNS}""",
        (hold_id,),
    ).fetchone()
    conn.commit()
    return _to_hold(row)


def expire(conn) -> int:
    rows = conn.execute(
        """UPDATE booking_holds SET status = %s
           WHERE status = 'PENDING' AND expires_at < now()
           RETURNING id""",
        (EXPIRED,),
    ).fetchall()
    conn.commit()
    return len(rows)


def status_metrics(conn) -> list[tuple[str, int]]:
    rows = conn.execute(
        "SELECT status, count(*) AS count FROM booking_holds GROUP BY status"
    ).fetchall()
    return [(row["status"], int(row["count"])) for row in rows]
