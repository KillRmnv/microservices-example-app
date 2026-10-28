"""Domain exceptions; the API layer maps them to HTTP once."""
from __future__ import annotations


class DomainError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class UpstreamError(DomainError):
    status_code = 502
    code = "upstream_error"


class UnknownSource(NotFoundError):
    code = "unknown_source"
