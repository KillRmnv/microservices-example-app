"""Domain exceptions. The API layer translates them to HTTP once."""
from __future__ import annotations


class DomainError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code


class ValidationError(DomainError):
    status_code = 400
    code = "validation_error"


class NotFoundError(DomainError):
    status_code = 404
    code = "not_found"


class ConflictError(DomainError):
    status_code = 409
    code = "conflict"


class RateLimited(DomainError):
    status_code = 429
    code = "rate_limited"

    def __init__(self, message: str | None = None, *,
                 retry_after_s: int | None = None) -> None:
        super().__init__(message or "Too many requests; retry later")
        # Seconds until the fixed window resets (sent as Retry-After).
        self.retry_after_s = retry_after_s


class GoneError(DomainError):
    status_code = 410
    code = "gone"


class UpstreamError(DomainError):
    status_code = 502
    code = "upstream_error"


class EventNotFound(NotFoundError):
    code = "event_not_found"


class HoldGone(GoneError):
    code = "hold_gone"


class PriceMismatch(ValidationError):
    code = "price_mismatch"


class NotEnoughSeats(ConflictError):
    code = "not_enough_seats"


class BackendUnavailable(UpstreamError):
    code = "backend_unavailable"
