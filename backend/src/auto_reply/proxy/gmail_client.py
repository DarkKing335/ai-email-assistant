"""
gmail_client.py — Gmail REST calls and message parsing.

Three jobs: ask Gmail which messages are new, turn one into the
`InboundEmailEvent` the workflow already understands, and create a reply draft.

Reads use `gmail.readonly`; `create_draft` needs `gmail.compose`. Both are
requested at consent (see `google_oauth_scopes`), so an account connected
before drafts existed already granted it — no re-consent needed.

Reference: https://developers.google.com/gmail/api/reference/rest
"""
from __future__ import annotations

import base64
import binascii
import logging
from datetime import UTC, datetime
from email.message import EmailMessage
from email.utils import parsedate_to_datetime

import httpx

from src.auto_reply.proxy.gmail_adapter import InboundEmailEvent

logger = logging.getLogger(__name__)

API_BASE = "https://gmail.googleapis.com/gmail/v1/users/me"
_HTTP_TIMEOUT = 30.0


class GmailApiError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.retryable = retryable


# ---------------------------------------------------------------------------
# API calls
# ---------------------------------------------------------------------------


async def list_message_ids(
    access_token: str,
    *,
    query: str,
    after: datetime | None,
    max_results: int,
) -> list[str]:
    """Message ids matching `query`, newest first.

    Gmail's `after:` search operator takes epoch seconds. It has a one-second
    granularity, so a message can be returned twice across consecutive polls —
    harmless, because the workflow rejects duplicate `gmail_message_id`s.
    """
    messages = await _list_messages(
        access_token, query=query, after=after, max_results=max_results
    )
    return [item["id"] for item in messages]


async def list_sent_thread_ids(
    access_token: str,
    *,
    after: datetime | None,
    max_results: int,
) -> set[str]:
    """Threads the connected account has sent on since `after`.

    Used to notice that a reply went out. One request covers every thread,
    because `messages.list` already returns each message's `threadId` — asking
    per-thread whether a draft still exists would be one call per open email,
    and could not tell a sent draft from a discarded one anyway.
    """
    messages = await _list_messages(
        access_token, query="in:sent", after=after, max_results=max_results
    )
    return {item["threadId"] for item in messages if item.get("threadId")}


async def _list_messages(
    access_token: str,
    *,
    query: str,
    after: datetime | None,
    max_results: int,
) -> list[dict]:
    """Raw `messages.list` entries — each carries both `id` and `threadId`."""
    full_query = query
    if after is not None:
        full_query = f"{query} after:{int(after.timestamp())}".strip()

    data = await _get(
        access_token,
        "/messages",
        params={"q": full_query, "maxResults": max_results},
    )
    return data.get("messages", [])


async def get_message(access_token: str, message_id: str) -> InboundEmailEvent:
    data = await _get(access_token, f"/messages/{message_id}", params={"format": "full"})
    return parse_message(data)


async def create_draft(
    access_token: str,
    *,
    event: InboundEmailEvent,
    body_text: str,
) -> str:
    """Create a Gmail reply draft on the original thread. Returns the draft id.

    The draft id is returned rather than the message id because only the draft
    id is stable: Gmail replaces the underlying message — and its id — every
    time the draft is edited.
    """
    raw = _build_reply_mime(event, body_text)

    payload: dict = {"message": {"raw": raw}}
    # Without `threadId` Gmail files the draft as a new conversation, so the
    # reply would not appear under the email it answers.
    if event.gmail_thread_id:
        payload["message"]["threadId"] = event.gmail_thread_id

    data = await _post(access_token, "/drafts", json=payload)
    return str(data["id"])


def _build_reply_mime(event: InboundEmailEvent, body_text: str) -> str:
    """An RFC-2822 reply, base64url-encoded as the Gmail API expects."""
    message = EmailMessage()

    # `sender_email` is kept in raw `Name <addr>` form upstream, which is a
    # valid To value as-is.
    message["To"] = event.sender_email

    subject = event.subject or ""
    # Gmail matches the subject when attaching a draft to a thread, so the
    # `Re: ` prefix must not be doubled on a reply to a reply.
    if subject.strip().lower().startswith("re:"):
        message["Subject"] = subject
    else:
        message["Subject"] = f"Re: {subject}" if subject else "Re:"

    # `threadId` alone threads it inside Gmail; these headers are what make
    # every *other* mail client thread it too.
    if event.rfc_message_id:
        message["In-Reply-To"] = event.rfc_message_id
        message["References"] = event.rfc_message_id

    message.set_content(body_text)

    return base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")


async def _post(access_token: str, path: str, *, json: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.post(
                f"{API_BASE}{path}",
                json=json,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        raise GmailApiError(f"Could not reach Gmail: {exc}", retryable=True) from exc

    return _handle_response(response)


async def _get(access_token: str, path: str, *, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            response = await client.get(
                f"{API_BASE}{path}",
                params=params,
                headers={"Authorization": f"Bearer {access_token}"},
            )
    except httpx.HTTPError as exc:
        raise GmailApiError(f"Could not reach Gmail: {exc}", retryable=True) from exc

    return _handle_response(response)


def _handle_response(response: httpx.Response) -> dict:
    """Shared status handling, so reads and writes fail identically."""
    if response.status_code in (200, 201):
        return response.json()

    # 401 means the token is bad despite the expiry check — revoked, or scopes
    # changed. Not retryable with the same token; the caller must re-auth.
    if response.status_code == 401:
        raise GmailApiError(
            "Gmail rejected the access token. Reconnect the account.",
            status=401,
        )
    if response.status_code == 403:
        # Google's own message here is far better than anything we could guess:
        # it distinguishes "API not enabled in the project" (by far the most
        # common cause, and invisible until the first call) from a real quota
        # problem, and includes a link to the exact page that fixes it.
        raise GmailApiError(_google_message(response), status=403, retryable=True)

    if response.status_code == 429 or response.status_code >= 500:
        raise GmailApiError(
            f"Gmail is unavailable (HTTP {response.status_code}).",
            status=response.status_code,
            retryable=True,
        )
    raise GmailApiError(
        _google_message(response), status=response.status_code
    )


def _google_message(response: httpx.Response) -> str:
    """Google's structured error text, falling back to the status code."""
    try:
        error = response.json().get("error", {})
    except ValueError:
        return f"Gmail returned HTTP {response.status_code}."

    message = error.get("message")
    if not message:
        return f"Gmail returned HTTP {response.status_code}."
    return str(message)


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_message(payload: dict) -> InboundEmailEvent:
    """Convert a Gmail `messages.get?format=full` response into a domain event."""
    headers = _header_map(payload.get("payload", {}))
    text_body, html_body = _extract_bodies(payload.get("payload", {}))

    return InboundEmailEvent(
        gmail_message_id=payload["id"],
        gmail_thread_id=payload.get("threadId"),
        # Left in raw `Name <addr>` form: the workflow's `sanitize_sender`
        # guardrail is what splits it, and it should stay the only parser.
        sender_email=headers.get("from", ""),
        sender_name=None,
        subject=headers.get("subject"),
        body_text=text_body,
        body_html=html_body,
        received_at=_received_at(payload, headers),
        to_recipients=_split_addresses(headers.get("to")),
        cc_recipients=_split_addresses(headers.get("cc")),
        rfc_message_id=headers.get("message-id") or None,
    )


def _header_map(part: dict) -> dict[str, str]:
    """Headers keyed lowercase — Gmail preserves the sender's capitalisation."""
    return {
        header.get("name", "").lower(): header.get("value", "")
        for header in part.get("headers", [])
    }


def _extract_bodies(part: dict) -> tuple[str | None, str | None]:
    """Walk the MIME tree for the best text/plain and text/html bodies.

    A message is a tree, not a list: `multipart/mixed` wrapping
    `multipart/alternative` wrapping the actual parts is routine, and
    attachments add further branches. Recursion is the only thing that reliably
    finds the body.
    """
    text: str | None = None
    html: str | None = None

    def walk(node: dict) -> None:
        nonlocal text, html

        mime_type = node.get("mimeType", "")
        body = node.get("body", {})
        data = body.get("data")

        # Attachments carry an attachmentId and must not be mistaken for a body.
        if data and not body.get("attachmentId"):
            decoded = _decode_base64url(data)
            if decoded is not None:
                if mime_type == "text/plain" and text is None:
                    text = decoded
                elif mime_type == "text/html" and html is None:
                    html = decoded

        for child in node.get("parts", []) or []:
            walk(child)

    walk(part)
    return text, html


def _decode_base64url(data: str) -> str | None:
    try:
        raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
    except (binascii.Error, ValueError):
        logger.warning("gmail body part was not valid base64url; skipping")
        return None
    # Encodings vary wildly and a mis-decoded body is better than no body:
    # the summarizer can work with slightly mangled text, not with nothing.
    return raw.decode("utf-8", errors="replace")


def _received_at(payload: dict, headers: dict[str, str]) -> datetime:
    """When the message arrived.

    Prefers Gmail's `internalDate` (epoch milliseconds, set by Gmail on
    receipt) over the `Date` header, which is written by the sender and is
    routinely wrong or absent.
    """
    internal = payload.get("internalDate")
    if internal:
        try:
            return datetime.fromtimestamp(int(internal) / 1000, tz=UTC)
        except (TypeError, ValueError, OSError):
            pass

    raw_date = headers.get("date")
    if raw_date:
        try:
            parsed = parsedate_to_datetime(raw_date)
            return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
        except (TypeError, ValueError):
            pass

    return datetime.now(UTC)


def _split_addresses(value: str | None) -> list[str]:
    if not value:
        return []
    return [address.strip() for address in value.split(",") if address.strip()]
