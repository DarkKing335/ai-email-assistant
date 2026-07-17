"""
whitelist_tool.py — High-level CRUD operations for whitelist entries.

This tool sits above the repository and applies business rules (guardrails,
dedup) before delegating to the persistence layer.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.agent.guardrails import GuardrailError, validate_whitelist_value
from src.auto_reply.infrastructure.models import EntryType, WhitelistEntry
from src.auto_reply.infrastructure.repositories import WhitelistRepository

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class WhitelistEntryNotFound(Exception):
    def __init__(self, entry_id: int) -> None:
        super().__init__(f"Whitelist entry {entry_id} not found.")
        self.entry_id = entry_id


class WhitelistDuplicateError(Exception):
    def __init__(self, value: str) -> None:
        super().__init__(f"A whitelist entry for '{value}' already exists.")
        self.value = value


class WhitelistValidationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------
# WhitelistTool
# ---------------------------------------------------------------------------


class WhitelistTool:
    """Business-logic wrapper around :class:`WhitelistRepository`."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = WhitelistRepository(session)

    async def list_entries(
        self,
        *,
        entry_type: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[WhitelistEntry], int]:
        """Return a paginated list of active entries."""
        et = EntryType(entry_type) if entry_type else None
        return await self._repo.list_active(entry_type=et, page=page, page_size=page_size)

    async def get_entry(self, entry_id: int) -> WhitelistEntry:
        entry = await self._repo.get_by_id(entry_id)
        if not entry or not entry.is_active:
            raise WhitelistEntryNotFound(entry_id)
        return entry

    async def create_entry(
        self,
        value: str,
        *,
        priority: int = 0,
        created_by: str | None = None,
    ) -> WhitelistEntry:
        """Validate, check for duplicates, then persist a new entry."""
        try:
            normalised, entry_type_str = validate_whitelist_value(value)
        except GuardrailError as exc:
            raise WhitelistValidationError(exc.code, exc.message) from exc

        existing = await self._repo.get_by_value(normalised)
        if existing and existing.is_active:
            raise WhitelistDuplicateError(normalised)

        if existing and not existing.is_active:
            # Reactivate instead of creating a new row
            logger.info("reactivating whitelist entry id=%d value=%s", existing.id, normalised)
            return await self._repo.update(
                existing,
                is_active=True,
                priority=priority,
            )

        entry_type = EntryType(entry_type_str)
        return await self._repo.create(
            entry_type=entry_type,
            value=normalised,
            priority=priority,
            created_by=created_by,
        )

    async def update_entry(
        self,
        entry_id: int,
        **fields: Any,
    ) -> WhitelistEntry:
        """Partially update a whitelist entry."""
        entry = await self._repo.get_by_id(entry_id)
        if not entry or not entry.is_active:
            raise WhitelistEntryNotFound(entry_id)

        # If value is being changed, re-validate and re-check duplicates
        if "value" in fields:
            try:
                normalised, entry_type_str = validate_whitelist_value(fields["value"])
            except GuardrailError as exc:
                raise WhitelistValidationError(exc.code, exc.message) from exc
            fields["value"] = normalised
            fields["entry_type"] = EntryType(entry_type_str)

            if normalised != entry.value:
                existing = await self._repo.get_by_value(normalised)
                if existing and existing.is_active and existing.id != entry_id:
                    raise WhitelistDuplicateError(normalised)

        return await self._repo.update(entry, **fields)

    async def delete_entry(self, entry_id: int) -> None:
        """Soft-delete an entry (sets is_active=False)."""
        entry = await self._repo.get_by_id(entry_id)
        if not entry or not entry.is_active:
            raise WhitelistEntryNotFound(entry_id)
        await self._repo.soft_delete(entry)
        logger.info("soft-deleted whitelist entry id=%d value=%s", entry_id, entry.value)
