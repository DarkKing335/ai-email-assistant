"""
draft_store_tool.py — Persist and retrieve AI-generated draft replies.

Handles versioning (each regeneration bumps the version number)
and draft history queries.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.infrastructure.models import GeneratedDraft
from src.auto_reply.infrastructure.repositories import DraftRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class DraftNotFound(Exception):
    def __init__(self, draft_id: int) -> None:
        super().__init__(f"Draft {draft_id} not found.")
        self.draft_id = draft_id


# ---------------------------------------------------------------------------
# DraftStoreTool
# ---------------------------------------------------------------------------


class DraftStoreTool:
    """Business-logic wrapper around :class:`DraftRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = DraftRepository(session)

    async def store_draft(
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
        """Persist a new draft version for the given match log."""
        draft = await self._repo.create(
            match_log_id=match_log_id,
            draft_text=draft_text,
            template_id=template_id,
            confidence_score=confidence_score,
            extracted_data=extracted_data,
            provider_used=provider_used,
            used_fallback=used_fallback,
        )
        logger.info(
            "draft_stored id=%d log=%d version=%d provider=%s",
            draft.id,
            match_log_id,
            draft.version,
            provider_used,
        )
        return draft

    async def get_draft(self, draft_id: int) -> GeneratedDraft:
        draft = await self._repo.get_by_id(draft_id)
        if not draft:
            raise DraftNotFound(draft_id)
        return draft

    async def get_latest_for_log(self, match_log_id: int) -> GeneratedDraft | None:
        return await self._repo.get_latest_by_log(match_log_id)

    async def list_history(self, match_log_id: int) -> list[GeneratedDraft]:
        """Return all draft versions for a match log, oldest first."""
        return await self._repo.list_by_log(match_log_id)
