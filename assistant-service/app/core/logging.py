"""Structured logging with secret redaction.

- JSON lines to stdout: timestamp, level, service, logger, message,
  request_id, plus any ``extra={}`` fields;
- ``RequestIdMiddleware`` reads/sets ``X-Request-ID`` (also used as the
  RFC 9457 ``trace_id``);
- ``redact``/``redact_url``/``mask_email`` scrub secrets before logging.
  Log data, never credentials.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

request_id_var: ContextVar[str] = ContextVar("request_id", default="")

SENSITIVE_KEYS = frozenset({
    "password", "passwd", "pwd", "secret", "token", "authorization",
    "cookie", "set-cookie", "api_key", "apikey", "key", "jwt",
    "reset_token", "refresh_token", "client_secret", "access_token",
})

SENSITIVE_QUERY_PARAMS = frozenset({"key", "token", "api_key", "apiKey", "secret"})

EMAIL_RE = re.compile(r"(?P<local>[A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@(?P<domain>[^@\s,;]+)")

REDACTED = "***"


def mask_email(value: str) -> str:
    return EMAIL_RE.sub(lambda m: f"{m.group('local')}{REDACTED}@{m.group('domain')}", value)


def redact_url(url: str) -> str:
    """Scrub sensitive query params (e.g. the 2GIS ``key``) from a URL."""
    try:
        parts = urlsplit(url)
        if not parts.query:
            return url
        params = [(k, REDACTED if k in SENSITIVE_QUERY_PARAMS else v)
                  for k, v in parse_qsl(parts.query, keep_blank_values=True)]
        return urlunsplit(parts._replace(query=urlencode(params)))
    except Exception:  # noqa: BLE001 — never break logging
        return REDACTED


def redact(obj: Any) -> Any:
    """Recursively scrub secrets from dicts/lists/strings."""
    if isinstance(obj, dict):
        return {key: (REDACTED if str(key).lower() in SENSITIVE_KEYS
                      else redact(value))
                for key, value in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact(item) for item in obj]
    if isinstance(obj, str):
        if "://" in obj and ("@" in obj or "?" in obj):
            return mask_email(redact_url(obj))
        return mask_email(obj)
    return obj


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self._service,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get() or getattr(record, "request_id", "")
        if request_id:
            payload["request_id"] = request_id
        if record.exc_info and record.exc_info[0] is not None:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(redact(payload), ensure_ascii=False, default=str)


def setup_logging(service: str, level: str = "INFO",
                  fmt: str = "json") -> None:
    """Configure root logging once. ``fmt`` is ``json`` or ``text``."""
    root = logging.getLogger()
    root.handlers.clear()
    handler = logging.StreamHandler(sys.stdout)
    if fmt == "json":
        handler.setFormatter(JsonFormatter(service))
    else:
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))


def new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Pure-ASGI middleware: no FastAPI/Starlette import needed at module level."""

    def __init__(self, app) -> None:
        self._app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        request_id = headers.get(b"x-request-id", b"").decode("latin-1").strip()
        if not request_id:
            request_id = new_request_id()
        token = request_id_var.set(request_id)

        async def send_with_id(message) -> None:
            if message["type"] == "http.response.start":
                message = dict(message)
                raw = [(k, v) for k, v in message.get("headers", [])
                       if k.lower() != b"x-request-id"]
                raw.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = raw
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        finally:
            request_id_var.reset(token)
