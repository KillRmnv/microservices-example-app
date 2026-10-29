"""LLM structure endpoint: raw RU query -> dialogue contract."""
from __future__ import annotations

from fastapi import APIRouter

from ..deps import get_components
from ..schemas.contract import StateContract
from ..schemas.query import QueryRequest

router = APIRouter(prefix="/assistant", tags=["dialogue"])


@router.post("/query", response_model=StateContract)
async def parse_query(request: QueryRequest) -> StateContract:
    return await get_components().structure.parse(
        request.query, language=request.language,
        session_id=request.session_id)
