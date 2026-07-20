"""
stats_tool.py — Aggregated dashboard statistics for the AutoReply feature.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.infrastructure.models import (
    ExecutionStatus,
    GeneratedDraft,
    MatchLog,
    WhitelistEntry,
)

logger = logging.getLogger(__name__)


@dataclass
class StatusBreakdown:
    pending: int = 0
    processing: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    rate_limited: int = 0


@dataclass
class DashboardSummary:
    """Aggregated metrics returned to the dashboard endpoint."""

    since: str                         # ISO-8601 start of the window
    until: str                         # ISO-8601 end (now)
    total_inbound_emails: int = 0
    matched_whitelist: int = 0
    unmatched: int = 0
    total_drafts_generated: int = 0
    failed_generation: int = 0
    avg_processing_ms: float | None = None
    status_breakdown: StatusBreakdown = field(default_factory=StatusBreakdown)
    active_whitelist_entries: int = 0
    top_senders: list[dict] = field(default_factory=list)  # [{sender, count}]


class StatsTool:
    """Compute dashboard summary statistics from the DB."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_summary(self, since_hours: int = 24) -> DashboardSummary:
        now = datetime.now(UTC)
        since = now - timedelta(hours=since_hours)

        summary = DashboardSummary(
            since=since.isoformat(),
            until=now.isoformat(),
        )

        # 1. Total inbound emails in window
        result = await self._session.execute(
            select(func.count())
            .select_from(MatchLog)
            .where(MatchLog.received_at >= since)
        )
        summary.total_inbound_emails = result.scalar_one() or 0

        # 2. Matched vs unmatched
        result = await self._session.execute(
            select(func.count())
            .select_from(MatchLog)
            .where(
                MatchLog.received_at >= since,
                MatchLog.whitelist_entry_id.is_not(None),
            )
        )
        summary.matched_whitelist = result.scalar_one() or 0
        summary.unmatched = summary.total_inbound_emails - summary.matched_whitelist

        # 3. Total drafts generated
        result = await self._session.execute(
            select(func.count())
            .select_from(GeneratedDraft)
            .join(MatchLog, GeneratedDraft.match_log_id == MatchLog.id)
            .where(MatchLog.received_at >= since)
        )
        summary.total_drafts_generated = result.scalar_one() or 0

        # 4. Failed generation
        result = await self._session.execute(
            select(func.count())
            .select_from(MatchLog)
            .where(
                MatchLog.received_at >= since,
                MatchLog.status == ExecutionStatus.FAILED,
            )
        )
        summary.failed_generation = result.scalar_one() or 0

        # 5. Avg processing time
        result = await self._session.execute(
            select(func.avg(MatchLog.processing_ms))
            .where(
                MatchLog.received_at >= since,
                MatchLog.processing_ms.is_not(None),
            )
        )
        avg = result.scalar_one_or_none()
        summary.avg_processing_ms = round(float(avg), 1) if avg is not None else None

        # 6. Status breakdown
        result = await self._session.execute(
            select(MatchLog.status, func.count())
            .where(MatchLog.received_at >= since)
            .group_by(MatchLog.status)
        )
        for status, count in result.all():
            attr = status.value.replace("-", "_")
            if hasattr(summary.status_breakdown, attr):
                setattr(summary.status_breakdown, attr, count)

        # 7. Active whitelist entries
        result = await self._session.execute(
            select(func.count()).select_from(WhitelistEntry).where(WhitelistEntry.is_active == True)  # noqa: E712
        )
        summary.active_whitelist_entries = result.scalar_one() or 0

        # 8. Top senders (by match count, within window)
        #
        # Filtered on the FK alone — the same test `matched_whitelist` uses — so
        # the two agree by construction. An earlier version joined
        # `WhitelistEntry` and required `is_active`, meaning to drop removed
        # senders off the chart. That made the panel contradict itself:
        # deactivating a rule erased its sender here while Matched went on
        # counting their mail, and deletion is *soft*, so the counts diverged
        # permanently with nothing on screen explaining the gap.
        #
        # Every figure in this summary answers "what happened in this window",
        # never "what would today's rules do". A rule that has since been
        # removed still processed the mail it processed.
        result = await self._session.execute(
            select(MatchLog.sender_email, func.count().label("count"))
            .where(
                MatchLog.received_at >= since,
                MatchLog.whitelist_entry_id.is_not(None),
            )
            .group_by(MatchLog.sender_email)
            .order_by(func.count().desc())
            .limit(10)
        )
        summary.top_senders = [
            {"sender": row.sender_email, "count": row.count} for row in result.all()
        ]

        return summary
