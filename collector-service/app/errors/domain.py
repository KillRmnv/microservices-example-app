"""Concrete domain errors for the collector service.

Infrastructure code raises these; ``errors.handlers`` is the only place
that knows about HTTP status codes.
"""
from __future__ import annotations

from .base import ConflictError, DomainError, NotFoundError, UpstreamError


class EventNotFound(NotFoundError):
    code = "event_not_found"


class VenueNotFound(NotFoundError):
    code = "venue_not_found"


class SourceError(UpstreamError):
    code = "source_error"


class SourceFetchError(SourceError):
    code = "source_fetch_failed"


class SourceParseError(SourceError):
    code = "source_parse_failed"


class SourceConfigError(SourceError):
    code = "source_config_error"


class QuotaExhausted(DomainError):
    status_code = 429
    code = "source_quota_exceeded"


class CollectionInProgress(ConflictError):
    code = "collection_in_progress"


class EmbeddingUnavailable(UpstreamError):
    status_code = 503
    code = "embedding_unavailable"


class VectorStoreUnavailable(UpstreamError):
    status_code = 503
    code = "vector_store_unavailable"


class DatabaseUnavailable(DomainError):
    status_code = 503
    code = "database_unavailable"


class ReindexConfirmationRequired(DomainError):
    status_code = 400
    code = "reindex_confirmation_required"
