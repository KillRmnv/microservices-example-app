"""RFC 9457 Problem Details for HTTP APIs.

Every error response has ``type``/``title``/``status``/``detail``/
``instance``, plus our stable ``code`` and the ``trace_id`` (which is the
``X-Request-ID``). Served as ``application/problem+json``.
"""
from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from ..core.logging import new_request_id, request_id_var

PROBLEM_BASE = "https://dosug.example/problems"
MEDIA_TYPE = "application/problem+json"


def trace_id() -> str:
    current = request_id_var.get()
    if current:
        return current
    fresh = new_request_id()
    request_id_var.set(fresh)
    return fresh


def problem_response(request: Request, *, status: int, code: str,
                     detail: str, title: str | None = None,
                     errors: list[dict[str, Any]] | None = None) -> JSONResponse:
    resolved_title = title
    if not resolved_title:
        try:
            resolved_title = HTTPStatus(status).phrase
        except ValueError:
            resolved_title = code
    body: dict[str, Any] = {
        "type": f"{PROBLEM_BASE}/{code}",
        "title": resolved_title,
        "status": status,
        "detail": detail,
        "instance": request.url.path,
        "code": code,
        "trace_id": trace_id(),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(status_code=status, content=body,
                        headers={"Content-Type": MEDIA_TYPE},
                        media_type=MEDIA_TYPE)
