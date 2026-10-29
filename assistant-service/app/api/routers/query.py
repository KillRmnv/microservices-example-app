"""LLM structure endpoint: raw RU query -> dialogue contract."""
from __future__ import annotations

from fastapi import APIRouter

from ..deps import get_components
from ..schemas.plan import QueryResponse
from ..schemas.query import QueryRequest

router = APIRouter(prefix="/assistant", tags=["dialogue"])


@router.post("/query", response_model=QueryResponse)
async def parse_query(request: QueryRequest) -> QueryResponse:
    contract, reasoning_used, complex = await get_components().structure.parse_meta(
        request.query, language=request.language,
        session_id=request.session_id,
        force_reasoning=request.force_reasoning)
    return QueryResponse(contract=contract, reasoning_used=reasoning_used,
                         complex=complex)
