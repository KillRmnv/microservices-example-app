"""Composition root: services are built once in the lifespan and stored on
``app.state``; routers only ask for them through these dependencies."""
from __future__ import annotations

from fastapi import Request

from ..services.collect_service import CollectService
from ..services.embed_service import EmbedService
from ..services.ops_service import OpsService


def get_collect_service(request: Request) -> CollectService:
    return request.app.state.collect


def get_embed_service(request: Request) -> EmbedService:
    return request.app.state.embed


def get_ops_service(request: Request) -> OpsService:
    return request.app.state.ops
