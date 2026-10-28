"""Collection controllers. Fixed paths must be declared before the
``/{source}`` catch-all, otherwise ``/collect/health`` is parsed as a source."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_collect_service, get_ops_service
from ..schemas import (
    AlertResponse,
    CollectResponse,
    ProbeRequest,
    ProbeResponse,
)
from ...services.collect_service import CollectService
from ...services.ops_service import OpsService

router = APIRouter(tags=["collect"])


@router.get("/sources")
def sources(service: CollectService = Depends(get_collect_service)) -> dict:
    return {"sources": service.sources}


@router.post("/collect/probe", response_model=ProbeResponse)
async def probe(req: ProbeRequest,
                service: CollectService = Depends(get_collect_service)) -> dict:
    return await service.probe(req.source, str(req.url))


@router.get("/collect/health")
def collect_health(
    service: OpsService = Depends(get_ops_service),
) -> dict:
    return service.collect_health()


@router.post("/collect/alert-check", response_model=AlertResponse)
async def alert_check(
    service: OpsService = Depends(get_ops_service),
) -> dict:
    return await service.alert_check()


@router.post("/collect/{source}", response_model=CollectResponse)
async def collect_source(source: str, limit: int | None = None,
                         service: CollectService = Depends(get_collect_service)) -> dict:
    stats = await service.collect(source, limit)
    return {"source": source, "status": "ok", **stats.__dict__}
