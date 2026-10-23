from app.holds import confirm_hold, create_hold, expire_holds


def test_hold_lifecycle(conn):
    hold = create_hold(conn, "s1", 7, "VIP", 120.0, party_size=2)
    assert hold.status == "PENDING"
    assert hold.party_size == 2
    confirmed = confirm_hold(conn, hold.id)
    assert confirmed is not None and confirmed.status == "CONFIRMED"
    assert confirm_hold(conn, hold.id) is None  # already confirmed
    assert confirm_hold(conn, "00000000-0000-0000-0000-000000000000") is None


def test_expired_hold_cannot_confirm(conn):
    hold = create_hold(conn, "s1", 7, "BASIC", 50.0)
    conn.execute(
        "UPDATE booking_holds SET expires_at = now() - make_interval(mins => 1)"
        " WHERE id = %s",
        (hold.id,),
    )
    conn.commit()
    assert confirm_hold(conn, hold.id) is None
    row = conn.execute(
        "SELECT status FROM booking_holds WHERE id = %s", (hold.id,)).fetchone()
    assert row["status"] == "EXPIRED"


def test_sweep_expires_only_pending_past_due(conn):
    live = create_hold(conn, "s1", 1, "BASIC", 10.0)
    old = create_hold(conn, "s1", 2, "BASIC", 10.0)
    conn.execute(
        "UPDATE booking_holds SET expires_at = now() - make_interval(mins => 1)"
        " WHERE id = %s",
        (old.id,),
    )
    conn.commit()
    assert expire_holds(conn) == 1
    statuses = {
        str(row["id"]): row["status"]
        for row in conn.execute("SELECT id, status FROM booking_holds").fetchall()
    }
    assert statuses[str(live.id)] == "PENDING"
    assert statuses[str(old.id)] == "EXPIRED"
