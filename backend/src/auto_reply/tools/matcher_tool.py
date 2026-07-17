"""
matcher_tool.py — Whitelist match engine with in-memory TTL cache.

Match precedence (highest → lowest):
  1. Exact email match (e.g. ``alice@company.com``)
  2. Domain match (e.g. ``@company.com``)

Within each tier, the entry with the highest ``priority`` wins.
Tie-broken by lowest ``id`` (insertion order).

The cache is invalidated on any write operation.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import NamedTuple

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.infrastructure.models import EntryType, WhitelistEntry
from src.auto_reply.infrastructure.repositories import WhitelistRepository
from src.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


class _Cache(NamedTuple):
    entries: list[WhitelistEntry]
    loaded_at: float  # monotonic time


_cache: _Cache | None = None
_cache_lock = asyncio.Lock()


def invalidate_whitelist_cache() -> None:
    """Call this after any write to the whitelist_entries table."""
    global _cache
    _cache = None
    logger.debug("whitelist cache invalidated")


# ---------------------------------------------------------------------------
# MatchResult
# ---------------------------------------------------------------------------


class MatchResult(NamedTuple):
    entry: WhitelistEntry
    matched_rule: str
    match_type: str   # "exact_email" | "domain"


# ---------------------------------------------------------------------------
# MatcherTool
# ---------------------------------------------------------------------------


class MatcherTool:
    """Determine whether an inbound sender is on the whitelist."""

    def __init__(self, session: AsyncSession) -> None:
        self._repo = WhitelistRepository(session)

    async def _load_entries(self) -> list[WhitelistEntry]:
        """Return cached entries, refreshing if TTL expired."""
        global _cache

        settings = get_settings()
        ttl = settings.whitelist_cache_ttl_seconds

        async with _cache_lock:
            if _cache is not None and ttl > 0 and (time.monotonic() - _cache.loaded_at) < ttl:
                return _cache.entries

            entries = await self._repo.list_all_active_ordered()
            _cache = _Cache(entries=entries, loaded_at=time.monotonic())
            logger.debug("whitelist cache refreshed entries=%d", len(entries))
            return entries

    async def match(self, sender_email: str) -> MatchResult | None:
        """Check ``sender_email`` against the whitelist.

        Returns a :class:`MatchResult` for the best matching entry, or
        ``None`` if the sender is not whitelisted.
        """
        email = sender_email.strip().lower()
        domain = f"@{email.split('@', 1)[1]}" if "@" in email else None

        entries = await self._load_entries()

        best_exact: WhitelistEntry | None = None
        best_domain: WhitelistEntry | None = None

        for entry in entries:
            if entry.entry_type == EntryType.EMAIL and entry.value == email:
                # Entries are pre-sorted by priority desc; first hit = best
                if best_exact is None:
                    best_exact = entry
            elif entry.entry_type == EntryType.DOMAIN and entry.value == domain:
                if best_domain is None:
                    best_domain = entry

        # Exact email always beats domain
        if best_exact:
            logger.debug("whitelist_match exact email=%s entry_id=%d", email, best_exact.id)
            return MatchResult(
                entry=best_exact,
                matched_rule=best_exact.value,
                match_type="exact_email",
            )
        if best_domain:
            logger.debug("whitelist_match domain email=%s entry_id=%d", email, best_domain.id)
            return MatchResult(
                entry=best_domain,
                matched_rule=best_domain.value,
                match_type="domain",
            )

        logger.debug("whitelist_no_match email=%s", email)
        return None
