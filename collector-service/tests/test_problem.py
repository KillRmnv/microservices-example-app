"""RFC 9457 error shape + logging redaction."""
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.core.logging import mask_email, redact, redact_url


def make_client():
    from app.main import create_app

    app = create_app()
    app.state.embed = SimpleNamespace()
    app.state.collect = SimpleNamespace()
    return TestClient(app, raise_server_exceptions=False)


def test_domain_error_is_problem_json():
    client = make_client()
    response = client.post(
        "/embed/reindex-hybrid",
        headers={"X-Request-ID": "req-123"},
    )
    assert response.status_code == 400
    assert response.headers["Content-Type"] == "application/problem+json"
    body = response.json()
    assert body["type"] == "https://dosug.example/problems/validation_error"
    assert body["title"] == "Bad Request"
    assert body["status"] == 400
    assert body["code"] == "validation_error"
    assert body["instance"] == "/embed/reindex-hybrid"
    assert body["trace_id"] == "req-123"
    assert response.headers["X-Request-ID"] == "req-123"


def test_unknown_route_is_problem_json():
    client = make_client()
    response = client.get("/nope")
    assert response.status_code == 404
    body = response.json()
    assert body["code"] == "http_404"
    assert body["trace_id"]
    assert response.headers["X-Request-ID"] == body["trace_id"]


def test_validation_error_lists_fields():
    client = make_client()
    response = client.post("/collect/probe", json={"source": "x"})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "validation_error"
    assert body["errors"]
    assert body["errors"][0]["field"]


def test_redact_scrubs_secrets():
    assert redact({"password": "hunter2", "user": "u"}) == {
        "password": "***", "user": "u"}
    assert redact({"Authorization": "Bearer abc"}) == {"Authorization": "***"}
    assert redact({"nested": [{"api_key": "k"}]}) == {
        "nested": [{"api_key": "***"}]}


def test_redact_url_scrubs_api_key():
    url = "https://catalog.api.2gis.com/3.0/items?key=SECRET&q=1"
    cleaned = redact_url(url)
    assert "SECRET" not in cleaned
    assert "key=%2A%2A%2A" in cleaned or "key=***" in cleaned
    assert "q=1" in cleaned


def test_mask_email():
    assert mask_email("user@example.com") == "u***@example.com"
    assert mask_email("no-email here") == "no-email here"
