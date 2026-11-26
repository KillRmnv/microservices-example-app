from app.models.hold import CONFIRMED, EXPIRED
from app.repositories import holds


def test_hold_lifecycle(conn):
    hold = holds.create(conn, "s1", 7, "VIP", 120.0, party_size=2)
    assert hold.status == "PENDING"
    assert hold.party_size == 2
    confirmed = holds.confirm(conn, hold.id)
    assert confirmed is not None and confirmed.status == CONFIRMED
    assert holds.confirm(conn, hold.id) is None  # already confirmed
    assert holds.confirm(conn, "00000000-0000-0000-0000-000000000000") is None


def test_expired_hold_cannot_confirm(conn):
    hold = holds.create(conn, "s1", 7, "BASIC", 50.0, party_size=1)
    # Age the row in place: backdate both timestamps so the CHECK
    # (expires_at > created_at) still holds while the hold is past due.
    conn.execute(
        "UPDATE booking_holds SET created_at = now() - make_interval(mins => 20),"
        " expires_at = now() - make_interval(mins => 10)"
        " WHERE id = %s",
        (hold.id,),
    )
    conn.commit()
    assert holds.confirm(conn, hold.id) is None
    row = conn.execute(
        "SELECT status FROM booking_holds WHERE id = %s", (hold.id,)).fetchone()
    assert row["status"] == EXPIRED


def test_sweep_expires_only_pending_past_due(conn):
    live = holds.create(conn, "s1", 1, "BASIC", 10.0, party_size=1)
    old = holds.create(conn, "s1", 2, "BASIC", 10.0, party_size=1)
    conn.execute(
        "UPDATE booking_holds SET created_at = now() - make_interval(mins => 20),"
        " expires_at = now() - make_interval(mins => 10)"
        " WHERE id = %s",
        (old.id,),
    )
    conn.commit()
    assert holds.expire(conn) == 1
    statuses = {
        str(row["id"]): row["status"]
        for row in conn.execute("SELECT id, status FROM booking_holds").fetchall()
    }
    assert statuses[str(live.id)] == "PENDING"
    assert statuses[str(old.id)] == EXPIRED


def test_pending_hold_is_unique_per_session_and_event(conn):
    import psycopg
    import pytest

    holds.create(conn, "s1", 5, "BASIC", 10.0, party_size=1)
    with pytest.raises(psycopg.errors.UniqueViolation):
        holds.create(conn, "s1", 5, "BASIC", 10.0, party_size=1)
    conn.rollback()


def test_find_pending_ignores_expired_row(conn):
    stale = holds.create(conn, "s1", 3, "BASIC", 10.0, party_size=1)
    conn.execute(
        "UPDATE booking_holds SET created_at = now() - make_interval(mins => 20),"
        " expires_at = now() - make_interval(mins => 10)"
        " WHERE id = %s",
        (stale.id,),
    )
    conn.commit()
    assert holds.find_pending(conn, "s1", 3) is None


def test_expire_stale_frees_the_pending_slot(conn):
    stale = holds.create(conn, "renew", 9, "BASIC", 10.0, party_size=1)
    conn.execute(
        "UPDATE booking_holds SET created_at = now() - make_interval(mins => 20),"
        " expires_at = now() - make_interval(mins => 10)"
        " WHERE id = %s",
        (stale.id,),
    )
    conn.commit()
    # No commit inside expire_stale: the following INSERT commits both.
    assert holds.expire_stale(conn, "renew", 9) == 1
    fresh = holds.create(conn, "renew", 9, "BASIC", 10.0, party_size=1)
    assert fresh.id != stale.id
    statuses = {
        str(row["id"]): row["status"]
        for row in conn.execute(
            "SELECT id, status FROM booking_holds WHERE session_id = 'renew'"
        ).fetchall()
    }
    assert statuses[str(stale.id)] == EXPIRED
    assert statuses[str(fresh.id)] == "PENDING"
    assert list(statuses.values()).count("PENDING") == 1
    found = holds.find_pending(conn, "renew", 9)
    assert found is not None and found.id == fresh.id
    # A live PENDING row is untouched by expire_stale.
    assert holds.expire_stale(conn, "renew", 9) == 0
    conn.rollback()
