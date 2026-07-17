import re

from bs4 import BeautifulSoup

from app.summarization.errors import InvalidEmailContentError, InputTooLargeError
from app.summarization.models import (
    EmailMessageInput,
    NormalizedAttachment,
    NormalizedMessage,
    NormalizedThread,
    SummarizationRequest,
)

_WROTE_LINE = re.compile(r"^On .{1,500} wrote:\s*$", re.IGNORECASE)
_HEADER_QUOTE = re.compile(r"^-{2,}\s*Original Message\s*-{2,}$", re.IGNORECASE)
_MOBILE_SIGNATURE = re.compile(r"^Sent from my (?:iPhone|iPad|Android).*$", re.IGNORECASE)
_DISCLAIMER = re.compile(
    r"^(?:confidentiality notice|this email and any attachments (?:are|may be))",
    re.IGNORECASE,
)


def _participant(participant: object) -> str:
    name = getattr(participant, "name", None)
    address = str(getattr(participant, "address"))
    return f"{name} <{address}>" if name else address


def html_to_visible_text(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    for element in soup(["script", "style", "noscript", "template", "head"]):
        element.decompose()

    for element in soup.find_all(True):
        style = str(element.get("style", "")).replace(" ", "").lower()
        if (
            element.has_attr("hidden")
            or str(element.get("aria-hidden", "")).lower() == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        ):
            element.decompose()
    return soup.get_text("\n")


def conservative_cleanup(value: str) -> str:
    lines = value.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cleaned: list[str] = []
    for raw_line in lines:
        line = raw_line.strip()
        if _WROTE_LINE.match(line) or _HEADER_QUOTE.match(line):
            break
        if line.startswith(">"):
            continue
        if line == "--" or _MOBILE_SIGNATURE.match(line) or _DISCLAIMER.match(line):
            break
        cleaned.append(line)

    result: list[str] = []
    previous_blank = True
    for line in cleaned:
        blank = not line
        if blank and previous_blank:
            continue
        result.append(line)
        previous_blank = blank
    return "\n".join(result).strip()


def normalize_body(message: EmailMessageInput) -> str:
    source = message.body_text if message.body_text and message.body_text.strip() else None
    if source is None and message.body_html:
        source = html_to_visible_text(message.body_html)
    return conservative_cleanup(source or "")


def normalize_request(
    request: SummarizationRequest,
    *,
    max_messages: int,
    max_normalized_chars: int,
) -> NormalizedThread:
    ordered = sorted(request.messages, key=lambda message: message.sent_at)
    omitted = ordered[:-max_messages] if len(ordered) > max_messages else []
    retained = ordered[-max_messages:]

    messages: list[NormalizedMessage] = []
    for message in retained:
        body = normalize_body(message)
        if not body:
            raise InvalidEmailContentError()
        recipients = [
            _participant(participant)
            for participant in (*message.to_recipients, *message.cc_recipients)
        ]
        messages.append(
            NormalizedMessage(
                message_id=message.message_id,
                thread_id=message.thread_id,
                subject=message.subject,
                sender=_participant(message.sender),
                recipients=recipients,
                sent_at=message.sent_at,
                body=body,
                attachments=[
                    NormalizedAttachment(
                        filename=attachment.filename,
                        media_type=attachment.media_type,
                        size_bytes=attachment.size_bytes,
                    )
                    for attachment in message.attachments
                ],
            )
        )

    normalized_chars = sum(len(message.subject) + len(message.body) for message in messages)
    if normalized_chars > max_normalized_chars:
        raise InputTooLargeError()

    return NormalizedThread(
        messages=messages,
        omitted_message_ids=[message.message_id for message in omitted],
    )
