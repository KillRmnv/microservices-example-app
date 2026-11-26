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
import os
import re
import sys
import time
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
    "reseturl", "reset_url", "recipient", "phone",
})

SENSITIVE_QUERY_PARAMS = frozenset({
    "key", "token", "api_key", "apikey", "apiKey", "secret", "password",
    "reset_token", "access_token", "refresh_token", "jwt", "code",
})

EMAIL_RE = re.compile(r"(?P<local>[A-Za-z0-9._%+-])[A-Za-z0-9._%+-]*@(?P<domain>[^@\s,;]+)")
BEARER_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._~+/=-]+")
SECRET_KV_RE = re.compile(
    r"(?i)((?:password|passwd|pwd|secret|token|api[_-]?key|"
    r"authorization|reset[_-]?token)\s*[=:]\s*)([^\s,;&\"']+)")

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


def redact_text(value: str) -> str:
    """Mask emails and inline credentials while keeping useful context."""
    cleaned = BEARER_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", value)
    cleaned = SECRET_KV_RE.sub(lambda m: f"{m.group(1)}{REDACTED}", cleaned)
    return mask_email(cleaned)


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
            return redact_text(redact_url(obj))
        return redact_text(obj)
    return obj


_RESERVED = frozenset({
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
})


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str) -> None:
        super().__init__()
        self._service = service
        self._env = os.environ.get("APP_ENV", "local")
        self._version = os.environ.get("APP_VERSION", "dev")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "service": self._service,
            "env": self._env,
            "version": self._version,
            "logger": record.name,
            "message": record.getMessage(),
        }
        request_id = request_id_var.get() or getattr(record, "request_id", "")
        if request_id:
            payload["request_id"] = request_id
        # Structured extra={} fields are part of the public log contract.
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload.setdefault(key, value)
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
    # Uvicorn installs its own plain-text handlers before the app is imported.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True
        if name == "uvicorn.access":
            logger.disabled = True
    for name in ("httpx", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def new_request_id() -> str:
    return uuid.uuid4().hex


class RequestIdMiddleware:
    """Pure-ASGI middleware: request id + one structured access line."""

    _SKIP_PATHS = frozenset({"/metrics", "/health", "/openapi.json"})

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
        started = time.perf_counter()
        status = 0

        async def send_with_id(message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message.get("status", 0))
                message = dict(message)
                raw = [(k, v) for k, v in message.get("headers", [])
                       if k.lower() != b"x-request-id"]
                raw.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = raw
            await send(message)

        try:
            await self._app(scope, receive, send_with_id)
        finally:
            path = str(scope.get("path") or "")
            if path not in self._SKIP_PATHS:
                logging.getLogger("access").info(
                    "http request",
                    extra={
                        "event": "http.request",
                        "method": scope.get("method", ""),
                        "path": path,
                        "status": status,
                        "duration_ms": round(
                            (time.perf_counter() - started) * 1000, 2),
                    },
                )
            request_id_var.reset(token)
