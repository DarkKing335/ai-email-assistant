"""
inbox_router.py — The combined view the extension's Inbox tab renders.

One request returns log + summary + latest draft for each email. Fetching a
list and then N detail calls would be a request per row on a panel that polls
every 30 seconds — slow, and obviously so during a demo.
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auto_reply.infrastructure.models import ExecutionStatus, MatchLog
from src.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auto-reply/inbox", tags=["inbox"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class InboxDraft(BaseModel):
    id: int
    version: int
    draft_text: str
    template_id: str
    confidence_score: float
    provider_used: str
    used_fallback: bool
    created_at: str
    #: Null when the draft predates Gmail draft creation, or Gmail was
    #: unreachable when this row was written.
    gmail_draft_id: str | None


class InboxItem(BaseModel):
    id: int
    gmail_message_id: str
    gmail_thread_id: str | None
    sender_email: str
    sender_name: str | None
    subject: str | None
    matched_rule: str | None
    status: str
    error_detail: str | None
    received_at: str
    processed_at: str | None

    #: `SummarizationResult` as stored. Null when the email was skipped, failed
    #: before summarization, or was processed before summaries were persisted.
    summary: dict[str, Any] | None
    #: Highest version only — the history endpoint serves the rest.
    latest_draft: InboxDraft | None
    draft_count: int


class InboxResponse(BaseModel):
    items: list[InboxItem]
    total: int
    page: int
    page_size: int


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.get("", response_model=InboxResponse)
async def get_inbox(
    since: datetime | None = Query(
        None, description="Only emails received after this instant (ISO-8601)."
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    include_skipped: bool = Query(
        False,
        description=(
            "Skipped emails matched no whitelist rule and have no summary or "
            "draft, so they are excluded by default — the Logs tab shows them."
        ),
    ),
    include_replied: bool = Query(
        False,
        description=(
            "Emails already replied to are dealt with, so they are excluded by "
            "default. The row is retained — Logs still shows them."
        ),
    ),
    db: AsyncSession = Depends(get_db),
):
    statement = select(MatchLog)

    if since is not None:
        statement = statement.where(MatchLog.received_at > since)
    if not include_skipped:
        statement = statement.where(MatchLog.status != ExecutionStatus.SKIPPED)
    if not include_replied:
        statement = statement.where(MatchLog.replied_at.is_(None))

    # Counted before pagination so the client knows the true size.
    total = len((await db.execute(statement)).scalars().all())

    statement = (
        statement
        # `selectinload` issues one extra query for all drafts in the page
        # rather than one per row — the whole point of this endpoint.
        .options(selectinload(MatchLog.drafts))
        .order_by(MatchLog.received_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )

    logs = (await db.execute(statement)).scalars().all()

    return InboxResponse(
        items=[_to_item(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
    )


def _to_item(log: MatchLog) -> InboxItem:
    drafts = sorted(log.drafts, key=lambda d: d.version)
    latest = drafts[-1] if drafts else None

    return InboxItem(
        id=log.id,
        gmail_message_id=log.gmail_message_id,
        gmail_thread_id=log.gmail_thread_id,
        sender_email=log.sender_email,
        sender_name=log.sender_name,
        subject=log.subject,
        matched_rule=log.matched_rule,
        status=log.status.value,
        error_detail=log.error_detail,
        received_at=log.received_at.isoformat(),
        processed_at=log.processed_at.isoformat() if log.processed_at else None,
        summary=log.summary_json,
        latest_draft=(
            InboxDraft(
                id=latest.id,
                version=latest.version,
                draft_text=latest.draft_text,
                template_id=latest.template_id,
                confidence_score=latest.confidence_score,
                provider_used=latest.provider_used,
                used_fallback=latest.used_fallback,
                created_at=latest.created_at.isoformat(),
                gmail_draft_id=latest.gmail_draft_id,
            )
            if latest
            else None
        ),
        draft_count=len(drafts),
    )
