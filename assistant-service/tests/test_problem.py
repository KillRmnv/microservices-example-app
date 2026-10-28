"""RFC 9457 error shape + logging redaction."""
from fastapi.testclient import TestClient

from app.core.logging import mask_email, redact, redact_url


def test_domain_error_is_problem_json(monkeypatch):
    from types import SimpleNamespace

    import app.api.routers.holds as holds_router
    from app.errors import HoldGone
    from app.main import create_app

    class FakeHolds:
        def confirm(self, hold_id: str):
            raise HoldGone("hold missing, taken or expired")

    monkeypatch.setattr(holds_router, "get_components",
                        lambda: SimpleNamespace(holds=FakeHolds()))
    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post(
        "/assistant/holds/00000000-0000-0000-0000-000000000000/confirm",
        headers={"X-Request-ID": "req-456"},
    )
    assert response.status_code == 410
    assert response.headers["Content-Type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://dosug.example/problems/hold_gone"
    assert body["title"] == "Gone"
    assert body["status"] == 410
    assert body["code"] == "hold_gone"
    assert body["trace_id"] == "req-456"
    assert response.headers["X-Request-ID"] == "req-456"


def test_unknown_dialogue_action_is_problem_json():
    from app.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.post("/assistant/dialogue", json={
        "dialogue_action": "drop_tables"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"]
    assert body["trace_id"]


def test_unknown_route_is_problem_json():
    from app.main import create_app

    client = TestClient(create_app(), raise_server_exceptions=False)
    response = client.get("/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "http_404"
    assert body["trace_id"]


def test_redact_scrubs_secrets():
    assert redact({"password": "hunter2", "user": "u"}) == {
        "password": "***", "user": "u"}
    assert redact({"Authorization": "Bearer abc"}) == {"Authorization": "***"}
    assert redact({"nested": [{"token": "t"}]}) == {
        "nested": [{"token": "***"}]}


def test_redact_url_keeps_safe_params():
    url = "https://api.open-meteo.com/v1/forecast?latitude=53.9&token=SECRET"
    cleaned = redact_url(url)
    assert "SECRET" not in cleaned
    assert "latitude=53.9" in cleaned


def test_mask_email():
    assert mask_email("user@example.com") == "u***@example.com"
