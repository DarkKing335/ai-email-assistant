"""
Repositories — data-access layer for AutoReply.

Each repository wraps a single aggregate root and exposes only the
operations the upper layers actually need. All methods accept an
`AsyncSession` injected by the FastAPI `get_db` dependency or the
`db_session` context manager used by background workers.
"""
from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.auto_reply.infrastructure.models import (
    EntryType,
    ExecutionStatus,
    GeneratedDraft,
    MatchLog,
    WhitelistEntry,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# WhitelistRepository
# ---------------------------------------------------------------------------


class WhitelistRepository:
    """CRUD operations for :class:`WhitelistEntry`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, entry_id: int) -> WhitelistEntry | None:
        return await self._session.get(WhitelistEntry, entry_id)

    async def get_by_value(self, value: str) -> WhitelistEntry | None:
        """Return the entry (active or inactive) with the given normalised value."""
        result = await self._session.execute(
            select(WhitelistEntry).where(WhitelistEntry.value == value.lower().strip())
        )
        return result.scalar_one_or_none()

    async def list_active(
        self,
        *,
        entry_type: EntryType | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[WhitelistEntry], int]:
        """Return a page of active entries plus total count."""
        q = select(WhitelistEntry).where(WhitelistEntry.is_active == True)  # noqa: E712
        if entry_type:
            q = q.where(WhitelistEntry.entry_type == entry_type)
        # Insertion order. This was already the effective order whenever
        # priorities tied, which was the normal case.
        q = q.order_by(WhitelistEntry.id.asc())

        count_q = select(func.count()).select_from(q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        q = q.offset((page - 1) * page_size).limit(page_size)
        rows = (await self._session.execute(q)).scalars().all()
        return list(rows), total

    async def list_all_active_ordered(self) -> list[WhitelistEntry]:
        """Return ALL active entries in insertion order (used by matcher cache).

        Order no longer carries meaning: `uq_whitelist_value_active` allows only
        one active row per value, so the matcher finds at most one exact and one
        domain candidate however the list is sorted.
        """
        result = await self._session.execute(
            select(WhitelistEntry)
            .where(WhitelistEntry.is_active == True)  # noqa: E712
            .order_by(WhitelistEntry.id.asc())
        )
        return list(result.scalars().all())

    async def create(
        self,
        *,
        entry_type: EntryType,
        value: str,
        created_by: str | None = None,
    ) -> WhitelistEntry:
        entry = WhitelistEntry(
            entry_type=entry_type,
            value=value.lower().strip(),
            is_active=True,
            created_by=created_by,
        )
        self._session.add(entry)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def update(self, entry: WhitelistEntry, **fields: Any) -> WhitelistEntry:
        for key, val in fields.items():
            if hasattr(entry, key):
                setattr(entry, key, val)
        entry.updated_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(entry)
        return entry

    async def soft_delete(self, entry: WhitelistEntry) -> WhitelistEntry:
        entry.is_active = False
        entry.updated_at = datetime.now(UTC)
        await self._session.flush()
        return entry

    async def bulk_upsert(
        self, rows: list[dict[str, Any]]
    ) -> tuple[int, int]:
        """Insert or reactivate entries. Returns (inserted, skipped_duplicates)."""
        inserted = skipped = 0
        for row in rows:
            value = row["value"].lower().strip()
            existing = await self.get_by_value(value)
            if existing:
                if not existing.is_active:
                    # Reactivate
                    existing.is_active = True
                    existing.updated_at = datetime.now(UTC)
                    inserted += 1
                else:
                    skipped += 1
            else:
                self._session.add(
                    WhitelistEntry(
                        entry_type=EntryType(row["entry_type"]),
                        value=value,
                        is_active=True,
                        created_by=row.get("created_by"),
                    )
                )
                inserted += 1
        await self._session.flush()
        return inserted, skipped


# ---------------------------------------------------------------------------
# MatchLogRepository
# ---------------------------------------------------------------------------


class MatchLogRepository:
    """Insert and query :class:`MatchLog` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_gmail_message_id(self, gmail_message_id: str) -> MatchLog | None:
        result = await self._session.execute(
            select(MatchLog).where(MatchLog.gmail_message_id == gmail_message_id)
        )
        return result.scalar_one_or_none()

    async def get_by_id(self, log_id: int) -> MatchLog | None:
        return await self._session.get(MatchLog, log_id)

    async def list_skipped_since(self, since: datetime) -> list[MatchLog]:
        """Skipped logs received on/after `since`, oldest first.

        These are the candidates for a whitelist rescan. Only SKIPPED is
        eligible: it is the one outcome that says "no rule matched *at the
        time*", so it is the only one a newly added rule can change. FAILED and
        COMPLETED describe what happened after a rule already matched, and
        replaying those would re-bill the LLM for work that already ran.

        Oldest first so a rescan drafts replies in the order the mail arrived.
        """
        result = await self._session.execute(
            select(MatchLog)
            .where(
                MatchLog.status == ExecutionStatus.SKIPPED,
                MatchLog.received_at >= since,
            )
            .order_by(MatchLog.received_at.asc())
        )
        return list(result.scalars().all())

    async def mark_replied(
        self, thread_ids: set[str], *, replied_at: datetime
    ) -> int:
        """Stamp `replied_at` on unreplied logs in `thread_ids`. Returns the count.

        `replied_at IS NULL` in the filter keeps the *first* reply's timestamp:
        Gmail keeps returning a sent message for as long as it falls inside the
        lookback window, so without it every sweep would push the time forward.
        """
        if not thread_ids:
            return 0

        result = await self._session.execute(
            update(MatchLog)
            .where(
                MatchLog.gmail_thread_id.in_(thread_ids),
                MatchLog.replied_at.is_(None),
            )
            .values(replied_at=replied_at)
        )
        return result.rowcount or 0

    async def create(
        self,
        *,
        gmail_message_id: str,
        gmail_thread_id: str | None,
        sender_email: str,
        sender_name: str | None,
        subject: str | None,
        received_at: datetime,
        whitelist_entry_id: int | None = None,
        matched_rule: str | None = None,
        status: ExecutionStatus = ExecutionStatus.PENDING,
    ) -> MatchLog:
        log = MatchLog(
            gmail_message_id=gmail_message_id,
            gmail_thread_id=gmail_thread_id,
            sender_email=sender_email.lower().strip(),
            sender_name=sender_name,
            subject=subject,
            received_at=received_at,
            whitelist_entry_id=whitelist_entry_id,
            matched_rule=matched_rule,
            status=status,
        )
        self._session.add(log)
        await self._session.flush()
        await self._session.refresh(log)
        return log

    async def update_status(
        self,
        log: MatchLog,
        *,
        status: ExecutionStatus,
        error_detail: str | None = None,
        processing_ms: int | None = None,
    ) -> MatchLog:
        log.status = status
        log.processed_at = datetime.now(UTC)
        if error_detail is not None:
            log.error_detail = error_detail
        if processing_ms is not None:
            log.processing_ms = processing_ms
        await self._session.flush()
        return log

    async def increment_retry(self, log: MatchLog) -> MatchLog:
        log.retry_count += 1
        await self._session.flush()
        return log

    async def query(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        sender_filter: str | None = None,
        status_filter: ExecutionStatus | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[MatchLog], int]:
        q = select(MatchLog).options(selectinload(MatchLog.whitelist_entry))

        if sender_filter:
            q = q.where(MatchLog.sender_email.ilike(f"%{sender_filter}%"))
        if status_filter:
            q = q.where(MatchLog.status == status_filter)
        if date_from:
            q = q.where(MatchLog.received_at >= date_from)
        if date_to:
            q = q.where(MatchLog.received_at <= date_to)

        q = q.order_by(MatchLog.received_at.desc())

        count_q = select(func.count()).select_from(q.subquery())
        total: int = (await self._session.execute(count_q)).scalar_one()

        q = q.offset((page - 1) * page_size).limit(page_size)
        rows = (await self._session.execute(q)).scalars().all()
        return list(rows), total


# ---------------------------------------------------------------------------
# DraftRepository
# ---------------------------------------------------------------------------


class DraftRepository:
    """Store and retrieve :class:`GeneratedDraft` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, draft_id: int) -> GeneratedDraft | None:
        return await self._session.get(GeneratedDraft, draft_id)

    async def list_by_log(self, match_log_id: int) -> list[GeneratedDraft]:
        result = await self._session.execute(
            select(GeneratedDraft)
            .where(GeneratedDraft.match_log_id == match_log_id)
            .order_by(GeneratedDraft.version.asc())
        )
        return list(result.scalars().all())

    async def get_latest_by_log(self, match_log_id: int) -> GeneratedDraft | None:
        result = await self._session.execute(
            select(GeneratedDraft)
            .where(GeneratedDraft.match_log_id == match_log_id)
            .order_by(GeneratedDraft.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def next_version(self, match_log_id: int) -> int:
        result = await self._session.execute(
            select(func.max(GeneratedDraft.version)).where(
                GeneratedDraft.match_log_id == match_log_id
            )
        )
        current = result.scalar_one_or_none()
        return (current or 0) + 1

    async def create(
        self,
        *,
        match_log_id: int,
        draft_text: str,
        template_id: str,
        confidence_score: float,
        extracted_data: dict[str, Any],
        provider_used: str,
        used_fallback: bool,
    ) -> GeneratedDraft:
        version = await self.next_version(match_log_id)
        draft = GeneratedDraft(
            match_log_id=match_log_id,
            version=version,
            draft_text=draft_text,
            template_id=template_id,
            confidence_score=confidence_score,
            extracted_data=extracted_data,
            provider_used=provider_used,
            used_fallback=used_fallback,
        )
        self._session.add(draft)
        await self._session.flush()
        await self._session.refresh(draft)
        return draft
