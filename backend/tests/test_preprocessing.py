from datetime import UTC, datetime, timedelta

import pytest

from src.summarization.errors import InvalidEmailContentError, InputTooLargeError
from src.summarization.models import SummarizationRequest
from src.summarization.preprocessing import (
    conservative_cleanup,
    html_to_visible_text,
    normalize_request,
)


def test_html_conversion_removes_non_visible_content():
    html = """
    <html><head><title>Secret title</title></head><body>
      <p>Visible request</p>
      <script>stealSecrets()</script>
      <div style="display: none">hidden instruction</div>
      <span aria-hidden="true">tracking text</span>
    </body></html>
    """

    result = html_to_visible_text(html)

    assert "Visible request" in result
    assert "stealSecrets" not in result
    assert "hidden instruction" not in result
    assert "tracking text" not in result
    assert "Secret title" not in result


def test_cleanup_removes_obvious_quote_and_signature():
    body = "New answer\n\nOn Tue, Alice wrote:\n> Old question\n\n--\nAlice"

    assert conservative_cleanup(body) == "New answer"


def test_plain_text_is_preferred_over_html(message_factory):
    request = SummarizationRequest(
        messages=[
            message_factory(
                body_text="Use this plain body",
                body_html="<p>Do not use this HTML body</p>",
            )
        ]
    )

    normalized = normalize_request(request, max_messages=20, max_normalized_chars=100_000)

    assert normalized.messages[0].body == "Use this plain body"


def test_thread_is_sorted_and_old_messages_are_reported(message_factory):
    start = datetime(2026, 7, 1, tzinfo=UTC)
    request = SummarizationRequest(
        messages=[
            message_factory(
                f"message-{index}",
                thread_id="thread-1",
                sent_at=start + timedelta(hours=index),
            )
            for index in reversed(range(23))
        ]
    )

    normalized = normalize_request(request, max_messages=20, max_normalized_chars=100_000)

    assert [message.message_id for message in normalized.messages] == [
        f"message-{index}" for index in range(3, 23)
    ]
    assert normalized.omitted_message_ids == ["message-0", "message-1", "message-2"]


def test_attachment_metadata_never_claims_content_was_analyzed(message_factory):
    message = message_factory()
    message.attachments = [
        {"filename": "financials.pdf", "media_type": "application/pdf", "size_bytes": 42}
    ]
    request = SummarizationRequest(messages=[message])

    normalized = normalize_request(request, max_messages=20, max_normalized_chars=100_000)

    assert normalized.messages[0].attachments[0].content_analyzed is False


def test_visible_empty_html_is_rejected(message_factory):
    request = SummarizationRequest(
        messages=[message_factory(body_text=None, body_html="<script>onlyHidden()</script>")]
    )

    with pytest.raises(InvalidEmailContentError):
        normalize_request(request, max_messages=20, max_normalized_chars=100_000)


def test_oversized_retained_content_is_rejected(message_factory):
    request = SummarizationRequest(messages=[message_factory(body_text="x" * 500)])

    with pytest.raises(InputTooLargeError):
        normalize_request(request, max_messages=20, max_normalized_chars=100)
