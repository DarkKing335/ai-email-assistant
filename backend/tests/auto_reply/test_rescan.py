"""Rescanning skipped mail after the whitelist gains a rule.

Reproduces the case that motivated the feature: an email arrived at 03:01 and
was filed SKIPPED, its whitelist rule was created at 03:10, and the dashboard
went on counting the email as Unmatched forever.
"""
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.auto_reply.infrastructure.models import EntryType, ExecutionStatus
from src.auto_reply.infrastructure.repositories import (
    MatchLogRepository,
    WhitelistRepository,
)
from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent
from src.auto_reply.tools.matcher_tool import invalidate_whitelist_cache
from src.auto_reply.workflow.auto_reply_workflow import AutoReplyWorkflow
from src.auto_reply.workflow.rescan import (
    rescan_skipped,
    request_rescan,
    take_rescan_request,
)

SENDER = "vietman151@gmail.com"


def _make_workflow(db_session) -> AutoReplyWorkflow:
    from src.auto_reply.tools.draft_store_tool import DraftStoreTool
    from src.auto_reply.tools.matcher_tool import MatcherTool

    workflow = AutoReplyWorkflow.__new__(AutoReplyWorkflow)
    workflow._session = db_session
    workflow._log_repo = MatchLogRepository(db_session)
    workflow._matcher = MatcherTool(db_session)
    workflow._draft_store = DraftStoreTool(db_session)
    workflow._llm_adapter = MagicMock()
    workflow._llm_adapter.generate_draft = AsyncMock()
    return workflow


def _event(message_id: str, received_at: datetime) -> InboundEmailEvent:
    return InboundEmailEvent(
        gmail_message_id=message_id,
        gmail_thread_id="thread-rescan",
        sender_email=SENDER,
        sender_name="Nguyen Viet Man",
        subject="Question about the assignment",
        body_text="Could you take a look?",
        body_html=None,
        received_at=received_at,
    )


async def _skip_then_whitelist(db_session, message_id: str) -> int:
    """Process mail with an empty whitelist, then add the rule. Returns log id."""
    invalidate_whitelist_cache()
    workflow = _make_workflow(db_session)
    log_id = await workflow.process_initial(
        _event(message_id, datetime.now(UTC) - timedelta(minutes=9))
    )

    log = await MatchLogRepository(db_session).get_by_id(log_id)
    assert log.status == ExecutionStatus.SKIPPED, "precondition: filed as skipped"

    await WhitelistRepository(db_session).create(
        entry_type=EntryType.EMAIL, value=SENDER
    )
    invalidate_whitelist_cache()
    return log_id


@pytest.mark.asyncio
async def test_rescan_picks_up_mail_that_predates_its_rule(db_session):
    log_id = await _skip_then_whitelist(db_session, "msg-rescan-1")

    with patch.object(
        AutoReplyWorkflow, "_refetch_event", new=AsyncMock(return_value=_event(
            "msg-rescan-1", datetime.now(UTC) - timedelta(minutes=9)
        ))
    ), patch.object(AutoReplyWorkflow, "_execute_core", new=AsyncMock()):
        report = await rescan_skipped(db_session, lookback_hours=24)

    assert report.matched == 1

    log = await MatchLogRepository(db_session).get_by_id(log_id)
    assert log.status == ExecutionStatus.PROCESSING
    assert log.matched_rule == SENDER
    assert log.whitelist_entry_id is not None
    # The skip reason must not outlive the skip.
    assert log.error_detail is None


@pytest.mark.asyncio
async def test_rescan_leaves_mail_no_rule_matches(db_session):
    invalidate_whitelist_cache()
    workflow = _make_workflow(db_session)
    log_id = await workflow.process_initial(
        InboundEmailEvent(
            gmail_message_id="msg-rescan-2",
            gmail_thread_id="t",
            sender_email="noreply@steampowered.com",
            sender_name=None,
            subject="Your receipt",
            body_text="Thanks",
            body_html=None,
            received_at=datetime.now(UTC),
        )
    )

    with patch.object(AutoReplyWorkflow, "_refetch_event", new=AsyncMock()) as refetch:
        report = await rescan_skipped(db_session, lookback_hours=24)

    assert report.matched == 0
    # Gmail is never called for mail that still matches nothing — the match is
    # checked before the fetch, so a sweep over a large backlog costs no quota.
    refetch.assert_not_awaited()

    log = await MatchLogRepository(db_session).get_by_id(log_id)
    assert log.status == ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_rescan_respects_lookback_window(db_session):
    """A new rule reaches back a bounded distance, not over the whole archive."""
    invalidate_whitelist_cache()
    workflow = _make_workflow(db_session)
    old = datetime.now(UTC) - timedelta(days=30)
    log_id = await workflow.process_initial(_event("msg-rescan-old", old))

    await WhitelistRepository(db_session).create(
        entry_type=EntryType.EMAIL, value=SENDER
    )
    invalidate_whitelist_cache()

    report = await rescan_skipped(db_session, lookback_hours=24)

    assert report.examined == 0
    log = await MatchLogRepository(db_session).get_by_id(log_id)
    assert log.status == ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_rescan_disabled_when_lookback_is_zero(db_session):
    await _skip_then_whitelist(db_session, "msg-rescan-3")

    report = await rescan_skipped(db_session, lookback_hours=0)

    assert report == type(report)()  # untouched default report


@pytest.mark.asyncio
async def test_rescan_survives_a_message_gmail_cannot_return(db_session):
    log_id = await _skip_then_whitelist(db_session, "msg-rescan-4")

    with patch.object(
        AutoReplyWorkflow, "_refetch_event", new=AsyncMock(return_value=None)
    ):
        report = await rescan_skipped(db_session, lookback_hours=24)

    assert report.examined == 1
    assert report.matched == 0
    # Left SKIPPED rather than stranded mid-flight, so a later sweep retries it.
    log = await MatchLogRepository(db_session).get_by_id(log_id)
    assert log.status == ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_adding_a_rule_does_not_trigger_a_rescan(db_session, override_get_db):
    """Rescanning is manual. A whitelist write must not start one."""
    from httpx import ASGITransport, AsyncClient

    from src.main import app

    take_rescan_request()  # clear

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        created = await client.post(
            "/api/v1/whitelist", json={"value": "rescan-trigger@example.com"}
        )
        assert created.status_code == 201
        assert take_rescan_request() is False, "create must not request a rescan"

        accepted = await client.post("/api/v1/whitelist/rescan")
        assert accepted.status_code == 202
        assert take_rescan_request() is True, "the endpoint is what requests one"


def test_rescan_request_is_consumed_once():
    take_rescan_request()  # clear anything a previous test left set

    assert take_rescan_request() is False
    request_rescan()
    request_rescan()  # repeated clicks collapse into a single sweep
    assert take_rescan_request() is True
    assert take_rescan_request() is False
