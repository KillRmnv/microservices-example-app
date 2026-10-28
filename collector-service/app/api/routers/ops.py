"""Operational controllers."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ..deps import get_ops_service
from ...services.ops_service import OpsService

router = APIRouter(tags=["ops"])


@router.get("/actuator/health")
def health() -> dict:
    return {"status": "UP"}


@router.get("/metrics")
def metrics(service: OpsService = Depends(get_ops_service)) -> PlainTextResponse:
    return PlainTextResponse(service.metrics())
