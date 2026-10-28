"""Exception handlers: the FastAPI analogue of Spring's @RestControllerAdvice.

All errors are RFC 9457 Problem Details (``application/problem+json``).
5xx responses never leak internals — only the ``trace_id``.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from .base import DomainError
from .problem import problem_response

log = logging.getLogger(__name__)


def _validation_errors(exc: RequestValidationError) -> list[dict]:
    items = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"][1:])
        items.append({
            "field": location or "body",
            "code": str(error["type"]),
            "message": str(error["msg"]),
        })
    return items


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> object:
        if exc.status_code >= 500:
            log.error("domain error on %s: %s", request.url.path, exc,
                      exc_info=True)
        else:
            log.info("domain error on %s: %s", request.url.path, exc)
        return problem_response(request, status=exc.status_code, code=exc.code,
                                detail=exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request,
                                       exc: RequestValidationError) -> object:
        log.info("validation error on %s: %s", request.url.path, exc.errors())
        return problem_response(
            request, status=422, code="validation_error",
            detail="Request validation failed",
            errors=_validation_errors(exc))

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request,
                                 exc: StarletteHTTPException) -> object:
        status = exc.status_code or 500
        detail = exc.detail if isinstance(exc.detail, str) else "HTTP error"
        if status >= 500:
            log.error("http error on %s: %s", request.url.path, detail,
                      exc_info=True)
        else:
            log.info("http error on %s: %s", request.url.path, detail)
        return problem_response(request, status=status,
                                code=f"http_{status}", detail=detail)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> object:
        log.error("unexpected error on %s", request.url.path, exc_info=True)
        return problem_response(request, status=500, code="internal_error",
                                detail="Internal server error")
