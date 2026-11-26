"""Composition root: services are built once in the lifespan and stored on
``app.state``; routers only ask for them through these dependencies."""
from __future__ import annotations

from fastapi import Request

from ..services.atmosphere_service import AtmosphereService
from ..services.catalog_service import CatalogService
from ..services.collect_service import CollectService
from ..services.embed_service import EmbedService
from ..services.film_metadata_service import FilmMetadataService
from ..services.ops_service import OpsService
from ..services.telegram_service import TelegramService
from ..services.ticketpro_details_service import TicketproDetailsService


def get_catalog_service(request: Request) -> CatalogService:
    return request.app.state.catalog


def get_collect_service(request: Request) -> CollectService:
    return request.app.state.collect


def get_embed_service(request: Request) -> EmbedService:
    return request.app.state.embed


def get_ops_service(request: Request) -> OpsService:
    return request.app.state.ops


def get_atmosphere_service(request: Request) -> AtmosphereService:
    return request.app.state.atmosphere


def get_ticketpro_details_service(request: Request) -> TicketproDetailsService:
    return request.app.state.ticketpro_details


def get_telegram_service(request: Request) -> TelegramService:
    return request.app.state.telegram


def get_film_metadata_service(request: Request) -> FilmMetadataService:
    return request.app.state.film_metadata
