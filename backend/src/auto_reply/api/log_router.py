"""
log_router.py — REST API for querying MatchLogs.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.tools.log_query_tool import LogQueryTool
from src.database import get_db

router = APIRouter(prefix="/api/v1/auto-reply/logs", tags=["logs"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class MatchLogResponse(BaseModel):
    id: int
    gmail_message_id: str
    sender_email: str
    subject: str | None
    whitelist_entry_id: int | None
    matched_rule: str | None
    status: str
    error_detail: str | None
    processing_ms: int | None
    received_at: str
    processed_at: str | None

    @classmethod
    def from_orm(cls, obj: Any) -> MatchLogResponse:
        return cls(
            id=obj.id,
            gmail_message_id=obj.gmail_message_id,
            sender_email=obj.sender_email,
            subject=obj.subject,
            whitelist_entry_id=obj.whitelist_entry_id,
            matched_rule=obj.matched_rule,
            status=obj.status.value,
            error_detail=obj.error_detail,
            processing_ms=obj.processing_ms,
            received_at=obj.received_at.isoformat(),
            processed_at=obj.processed_at.isoformat() if obj.processed_at else None,
        )


class PaginatedLogResponse(BaseModel):
    items: list[MatchLogResponse]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=PaginatedLogResponse)
async def query_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    sender_filter: str | None = None,
    status_filter: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db),
):
    tool = LogQueryTool(db)
    items, total = await tool.query_logs(
        page=page,
        page_size=page_size,
        sender_filter=sender_filter,
        status_filter=status_filter,
        date_from=date_from,
        date_to=date_to,
    )
    return PaginatedLogResponse(
        items=[MatchLogResponse.from_orm(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )
