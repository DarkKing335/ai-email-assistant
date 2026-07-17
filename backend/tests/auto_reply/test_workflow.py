import pytest
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

from src.auto_reply.infrastructure.models import ExecutionStatus
from src.auto_reply.infrastructure.repositories import MatchLogRepository
from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent
from src.auto_reply.workflow.auto_reply_workflow import AutoReplyWorkflow


def _make_workflow(db_session) -> AutoReplyWorkflow:
    """Build an AutoReplyWorkflow with a mocked LLM adapter (no real API keys needed)."""
    workflow = AutoReplyWorkflow.__new__(AutoReplyWorkflow)
    # Call __init__ manually but provide a fake llm_adapter before it tries to build
    from src.auto_reply.infrastructure.repositories import MatchLogRepository
    from src.auto_reply.tools.matcher_tool import MatcherTool
    from src.auto_reply.tools.draft_store_tool import DraftStoreTool

    workflow._session = db_session
    workflow._log_repo = MatchLogRepository(db_session)
    workflow._matcher = MatcherTool(db_session)
    workflow._draft_store = DraftStoreTool(db_session)
    workflow._llm_adapter = MagicMock()
    workflow._llm_adapter.generate_draft = AsyncMock()
    return workflow


@pytest.mark.asyncio
async def test_workflow_skip_unwhitelisted(db_session):
    event = InboundEmailEvent(
        gmail_message_id="msg-123",
        gmail_thread_id="thread-123",
        sender_email="unknown@random.com",
        sender_name="Random",
        subject="Hello",
        body_text="Hi there",
        body_html=None,
        received_at=datetime.now(UTC),
    )

    workflow = _make_workflow(db_session)
    log_id = await workflow.process_initial(event)

    assert log_id is not None

    repo = MatchLogRepository(db_session)
    log = await repo.get_by_id(log_id)

    assert log is not None
    assert log.status == ExecutionStatus.SKIPPED


@pytest.mark.asyncio
async def test_workflow_idempotency(db_session):
    event = InboundEmailEvent(
        gmail_message_id="msg-dup-2",
        gmail_thread_id="thread-123",
        sender_email="test@test.com",
        sender_name="Test",
        subject="Hello",
        body_text="Hi there",
        body_html=None,
        received_at=datetime.now(UTC),
    )

    workflow = _make_workflow(db_session)
    log_id_1 = await workflow.process_initial(event)
    log_id_2 = await workflow.process_initial(event)  # Duplicate processing

    assert log_id_1 == log_id_2
