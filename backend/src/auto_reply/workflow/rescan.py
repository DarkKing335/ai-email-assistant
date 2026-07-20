"""
rescan.py — Re-examine skipped mail after the whitelist changes.

The whitelist is consulted once, at the moment an email is processed. Mail that
arrives before its rule exists is filed SKIPPED and nothing ever revisits it, so
adding a rule leaves the sender's recent mail sitting in Unmatched on the
dashboard. This module closes that gap.

**A rescan only ever starts because someone asked for it** — `POST
/api/v1/whitelist/rescan`. Whitelist writes deliberately do not trigger one. A
sweep re-fetches messages from Gmail, spends LLM calls and files real drafts in
the mailbox; that is too much to happen as a side effect of typing an address
into a form, and a bulk import of a few hundred rules would fire it off against
the entire lookback window at once.

The request is a flag rather than a queue of ids, so repeated clicks collapse
into one sweep. The sweep re-reads the whitelist when it actually runs, so it
always works from current rules rather than a snapshot taken at request time.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.auto_reply.infrastructure.repositories import MatchLogRepository
from src.auto_reply.workflow.auto_reply_workflow import AutoReplyWorkflow
from src.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Request signal
# ---------------------------------------------------------------------------

_rescan_requested = False


def request_rescan() -> None:
    """Ask the background worker to sweep skipped mail on its next iteration.

    Called only from the `/rescan` endpoint — see the module docstring for why
    whitelist writes do not call it.
    """
    global _rescan_requested
    _rescan_requested = True


def take_rescan_request() -> bool:
    """Consume a pending request. True if one was outstanding."""
    global _rescan_requested
    if not _rescan_requested:
        return False
    _rescan_requested = False
    return True


# ---------------------------------------------------------------------------
# Sweep
# ---------------------------------------------------------------------------


@dataclass
class RescanReport:
    examined: int = 0
    matched: int = 0
    failed: int = 0


async def rescan_skipped(session: AsyncSession, *, lookback_hours: int | None = None) -> RescanReport:
    """Re-run recent skipped logs against the current whitelist.

    Each log is processed independently: one that fails — Gmail no longer has
    the message, the LLM errors — is counted and stepped over, so a single bad
    message cannot abort the sweep.
    """
    if lookback_hours is None:
        lookback_hours = get_settings().whitelist_rescan_lookback_hours
    if lookback_hours <= 0:
        return RescanReport()

    since = datetime.now(UTC) - timedelta(hours=lookback_hours)
    candidates = await MatchLogRepository(session).list_skipped_since(since)

    report = RescanReport(examined=len(candidates))
    if not candidates:
        return report

    workflow = AutoReplyWorkflow(session)
    for log in candidates:
        try:
            if await workflow.process_rescan(log.id):
                report.matched += 1
        except Exception as exc:
            # Includes the retryable errors `_execute_core` re-raises for the
            # retry queue. A rescan has no queue behind it, so the log keeps its
            # PROCESSING status and the next sweep will not re-pick it (only
            # SKIPPED is eligible) — it is left for the retry path or a human.
            report.failed += 1
            logger.warning("rescan_log_failed log=%d error=%s", log.id, exc)

    logger.info(
        "rescan_complete examined=%d matched=%d failed=%d lookback_hours=%d",
        report.examined,
        report.matched,
        report.failed,
        lookback_hours,
    )
    return report
