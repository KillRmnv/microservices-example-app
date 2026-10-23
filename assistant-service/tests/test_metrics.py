from app.main import assistant_metrics


def test_assistant_metrics_format(conn):
    conn.execute(
        """INSERT INTO dialogue_runs (session_id, turn, action, needs_clarification)
           VALUES ('s1', 1, 'search', false), ('s1', 2, 'search', false)""")
    conn.execute(
        """INSERT INTO booking_holds (session_id, event_id, zone, price, status)
           VALUES ('s1', 1, 'BASIC', 10, 'PENDING'),
                  ('s1', 2, 'BASIC', 10, 'CONFIRMED')""")
    conn.commit()
    text = assistant_metrics(conn)
    assert 'assistant_dialogue_runs_total{action="search"} 2' in text
    assert 'assistant_holds{status="PENDING"} 1' in text
    assert 'assistant_holds{status="CONFIRMED"} 1' in text
