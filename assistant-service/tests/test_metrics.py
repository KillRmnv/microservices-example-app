from app.services.metrics_service import MetricsService


def test_metrics_format(database_url):
    from app.core import db

    with db.get_conn(database_url) as conn:
        conn.execute(
            """INSERT INTO dialogue_runs (session_id, turn, action, needs_clarification)
               VALUES ('s1', 1, 'search', false), ('s1', 2, 'search', false)""")
        conn.execute(
            """INSERT INTO booking_holds (session_id, event_id, zone, price, status)
               VALUES ('s1', 1, 'BASIC', 10, 'PENDING'),
                      ('s1', 2, 'BASIC', 10, 'CONFIRMED')""")
        conn.commit()
        text = MetricsService(database_url).render()
        conn.execute("TRUNCATE booking_holds, dialogue_runs")
        conn.commit()
    assert 'assistant_dialogue_runs_total{action="search"} 2' in text
    assert 'assistant_holds{status="PENDING"} 1' in text
    assert 'assistant_holds{status="CONFIRMED"} 1' in text
