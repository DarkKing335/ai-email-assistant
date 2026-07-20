"""Dashboard summary figures.

The panel's figures are read together, so they have to agree with each other.
Every one of them answers "what happened in this window" — none of them
re-evaluates history against today's configuration.
"""
from datetime import UTC, datetime, timedelta

import pytest

from src.auto_reply.infrastructure.models import EntryType, ExecutionStatus
from src.auto_reply.infrastructure.repositories import (
    MatchLogRepository,
    WhitelistRepository,
)
from src.auto_reply.tools.stats_tool import StatsTool


async def _matched_log(db_session, *, message_id: str, sender: str, entry_id: int):
    return await MatchLogRepository(db_session).create(
        gmail_message_id=message_id,
        gmail_thread_id="t",
        sender_email=sender,
        sender_name=None,
        subject="Hi",
        received_at=datetime.now(UTC) - timedelta(minutes=5),
        whitelist_entry_id=entry_id,
        matched_rule=sender,
        status=ExecutionStatus.COMPLETED,
    )


@pytest.mark.asyncio
async def test_top_senders_agrees_with_matched_after_a_rule_is_removed(db_session):
    """A soft-deleted rule must not erase the mail it already matched.

    Regression: Top senders required `is_active`, so deactivating a rule dropped
    its sender from the chart while Matched kept counting them — the same panel
    reporting two different totals for the same mail.
    """
    repo = WhitelistRepository(db_session)
    entry = await repo.create(entry_type=EntryType.EMAIL, value="gone@example.com")
    await _matched_log(
        db_session, message_id="m-stats-1", sender="gone@example.com", entry_id=entry.id
    )

    before = await StatsTool(db_session).get_summary(since_hours=24)
    assert before.matched_whitelist == 1
    assert before.top_senders == [{"sender": "gone@example.com", "count": 1}]

    await repo.soft_delete(entry)

    after = await StatsTool(db_session).get_summary(since_hours=24)
    assert after.matched_whitelist == 1, "history does not change"
    assert after.top_senders == before.top_senders, "and neither does the chart"
    # Only the live-configuration figure moves.
    assert after.active_whitelist_entries == before.active_whitelist_entries - 1


@pytest.mark.asyncio
async def test_top_senders_sum_never_exceeds_matched(db_session):
    repo = WhitelistRepository(db_session)
    a = await repo.create(entry_type=EntryType.EMAIL, value="a@example.com")
    b = await repo.create(entry_type=EntryType.EMAIL, value="b@example.com")

    await _matched_log(db_session, message_id="m-stats-2", sender="a@example.com", entry_id=a.id)
    await _matched_log(db_session, message_id="m-stats-3", sender="a@example.com", entry_id=a.id)
    await _matched_log(db_session, message_id="m-stats-4", sender="b@example.com", entry_id=b.id)
    await repo.soft_delete(b)

    summary = await StatsTool(db_session).get_summary(since_hours=24)

    assert sum(s["count"] for s in summary.top_senders) == summary.matched_whitelist == 3
    assert summary.top_senders[0] == {"sender": "a@example.com", "count": 2}


@pytest.mark.asyncio
async def test_unmatched_excluded_from_top_senders(db_session):
    await MatchLogRepository(db_session).create(
        gmail_message_id="m-stats-5",
        gmail_thread_id="t",
        sender_email="noreply@steampowered.com",
        sender_name=None,
        subject="Receipt",
        received_at=datetime.now(UTC),
        status=ExecutionStatus.SKIPPED,
    )

    summary = await StatsTool(db_session).get_summary(since_hours=24)

    assert summary.top_senders == []
    assert summary.unmatched >= 1
