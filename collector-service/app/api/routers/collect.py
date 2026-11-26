"""Collection controllers. Fixed paths must be declared before the
``/{source}`` catch-all, otherwise ``/collect/health`` is parsed as a source."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from ..deps import (get_atmosphere_service, get_collect_service,
                    get_embed_service, get_film_metadata_service,
                    get_ops_service, get_telegram_service,
                    get_ticketpro_details_service)
from ..schemas import (
    AlertResponse,
    CollectResponse,
    ProbeRequest,
    ProbeResponse,
)
from ...scheduler import cleanup_job
from ...services.atmosphere_service import AtmosphereService
from ...services.collect_service import CollectService
from ...services.embed_service import EmbedService
from ...services.film_metadata_service import FilmMetadataService
from ...services.ops_service import OpsService
from ...services.telegram_service import TelegramService
from ...services.ticketpro_details_service import TicketproDetailsService

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


@router.post("/collect/cleanup")
async def cleanup_expired(request: Request) -> dict:
    return await cleanup_job(request.app)


@router.post("/collect/atmosphere")
def enrich_atmosphere(
    limit: int = 200,
    force: bool = False,
    service: AtmosphereService = Depends(get_atmosphere_service),
) -> dict:
    """Bounded venue atmosphere enrichment (never runs at startup)."""
    return service.enrich(limit=limit, force=force)


@router.post("/collect/ticketpro_details")
async def ticketpro_details(
    limit: int = 10,
    service: TicketproDetailsService = Depends(get_ticketpro_details_service),
) -> dict:
    """Fetch missing Ticketpro descriptions; manual/bounded by design."""
    return await service.enrich(limit=limit)


@router.post("/collect/film_metadata")
async def film_metadata(
    limit: int = 10,
    dry_run: bool = True,
    service: FilmMetadataService = Depends(get_film_metadata_service),
) -> dict:
    """ByCard film metadata enrichment; dry-run unless explicitly applied."""
    return await service.enrich(limit=limit, dry_run=dry_run)


@router.post("/collect/telegram_preview")
async def telegram_preview(
    channel: str,
    pages: int = 2,
    limit: int = 50,
    service: TelegramService = Depends(get_telegram_service),
) -> dict:
    """Dry-run classifier preview for one public Telegram channel."""
    return await service.preview(channel, pages=pages, limit=limit)


@router.post("/collect/telegram_rescore")
async def telegram_rescore(
    dry_run: bool = True,
    service: TelegramService = Depends(get_telegram_service),
    embed: EmbedService = Depends(get_embed_service),
) -> dict:
    """Re-classify stored Telegram rows; deletes only hard junk."""
    result = service.rescore(dry_run=dry_run)
    ids = result.pop("deleted_ids", [])
    if ids:
        result["vectors_deleted"] = await embed.delete_events(ids)
    return result


@router.post("/collect/{source}", response_model=CollectResponse)
async def collect_source(source: str, limit: int | None = None,
                         service: CollectService = Depends(get_collect_service)) -> dict:
    stats = await service.collect(source, limit)
    return {"source": source, "status": service.run_status(stats),
            **stats.__dict__}
