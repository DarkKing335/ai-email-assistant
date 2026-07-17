"""
draft_router.py — REST API for draft status and history.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.tools.draft_store_tool import DraftNotFound, DraftStoreTool
from src.auto_reply.tools.log_query_tool import LogQueryTool
from src.database import get_db

router = APIRouter(prefix="/api/v1/auto-reply", tags=["drafts"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class DraftResponse(BaseModel):
    id: int
    match_log_id: int
    version: int
    draft_text: str
    template_id: str
    confidence_score: float
    provider_used: str
    used_fallback: bool
    created_at: str

    @classmethod
    def from_orm(cls, obj: Any) -> DraftResponse:
        return cls(
            id=obj.id,
            match_log_id=obj.match_log_id,
            version=obj.version,
            draft_text=obj.draft_text,
            template_id=obj.template_id,
            confidence_score=obj.confidence_score,
            provider_used=obj.provider_used,
            used_fallback=obj.used_fallback,
            created_at=obj.created_at.isoformat(),
        )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/status/{log_id}")
async def get_processing_status(log_id: int, db: AsyncSession = Depends(get_db)):
    tool = LogQueryTool(db)
    log = await tool.get_log(log_id)
    if not log:
        raise HTTPException(status_code=404, detail="Match log not found")
    
    return {
        "log_id": log.id,
        "status": log.status.value,
        "retry_count": log.retry_count,
        "error_detail": log.error_detail,
        "processing_ms": log.processing_ms,
    }


@router.get("/drafts/{draft_id}", response_model=DraftResponse)
async def get_draft(draft_id: int, db: AsyncSession = Depends(get_db)):
    tool = DraftStoreTool(db)
    try:
        draft = await tool.get_draft(draft_id)
        return DraftResponse.from_orm(draft)
    except DraftNotFound:
        raise HTTPException(status_code=404, detail="Draft not found")


@router.get("/logs/{log_id}/drafts", response_model=list[DraftResponse])
async def list_draft_history(log_id: int, db: AsyncSession = Depends(get_db)):
    tool = DraftStoreTool(db)
    drafts = await tool.list_history(log_id)
    return [DraftResponse.from_orm(d) for d in drafts]
