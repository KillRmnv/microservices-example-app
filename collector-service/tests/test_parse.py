from pathlib import Path

from app.parse import clean_text, extract_json_ld_events, extract_microdata_event

FIXTURES = Path(__file__).parent / "fixtures"


def test_ticketpro_listing_events():
    html = (FIXTURES / "ticketpro_listing.html").read_text()
    events = extract_json_ld_events(html)
    assert len(events) == 2
    assert events[0]["name"] == "Тестовый концерт"
    assert events[0]["offers"]["lowPrice"] == "45"


def test_json_ld_graph_and_non_event_skipped():
    html = """<script type="application/ld+json">
    {"@graph": [{"@type": "Movie", "name": "Фильм"},
                {"@type": "Event", "name": "Концерт"}]}
    </script>"""
    events = extract_json_ld_events(html)
    assert [e["name"] for e in events] == ["Концерт"]


def test_broken_json_ld_block_skipped():
    html = """<script type="application/ld+json">{not json</script>
    <script type="application/ld+json">{"@type": "Event", "name": "Живой"}</script>"""
    assert [e["name"] for e in extract_json_ld_events(html)] == ["Живой"]


def test_relax_card_event_with_control_chars():
    html = (FIXTURES / "relax_card.html").read_text()
    assert "\x01" in html  # fixture really contains a control char
    events = extract_json_ld_events(html)
    assert len(events) == 1
    assert events[0]["name"] == "Спектакль «Тестовый»"


def test_afisha_me_microdata():
    html = (FIXTURES / "afisha_me_card.html").read_text()
    data = extract_microdata_event(html)
    assert data is not None
    assert data["name"] == "Тестовая группа"
    assert data["startDate"] == "2026-12-05T19:00:00+03:00"
    assert data["venue_name"] == "Тестовый зал"
    assert data["venue_url"] == "https://afisha.me/place/test-hall/"
    assert data["price_text"] == "от 30 руб."
    assert "12+" in data["tags"]


def test_afisha_me_no_scope_returns_none():
    assert extract_microdata_event("<html><body>пусто</body></html>") is None


def test_clean_text():
    assert clean_text("  a   b\nc ") == "a b c"
    assert clean_text("   ") is None
    assert clean_text(None) is None
