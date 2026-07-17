"""
log_query_tool.py — Paginated search and retrieval of MatchLog records.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.infrastructure.models import ExecutionStatus, MatchLog
from src.auto_reply.infrastructure.repositories import MatchLogRepository


class LogQueryTool:
    """Query interface for :class:`MatchLog` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = MatchLogRepository(session)

    async def get_log(self, log_id: int) -> MatchLog | None:
        return await self._repo.get_by_id(log_id)

    async def query_logs(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        sender_filter: str | None = None,
        status_filter: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[MatchLog], int]:
        """Search match logs with optional filtering.

        Returns ``(items, total_count)``.
        """
        status = ExecutionStatus(status_filter) if status_filter else None
        return await self._repo.query(
            page=page,
            page_size=page_size,
            sender_filter=sender_filter,
            status_filter=status,
            date_from=date_from,
            date_to=date_to,
        )
