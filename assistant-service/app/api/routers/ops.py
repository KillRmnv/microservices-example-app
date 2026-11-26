"""Operational endpoints: health and Prometheus metrics."""
from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse

from ..deps import get_components

router = APIRouter(tags=["ops"])


@router.get("/actuator/health")
def health() -> dict:
    return {"status": "UP"}


@router.get("/metrics")
def metrics() -> PlainTextResponse:
    return PlainTextResponse(get_components().metrics.render())
