from datetime import datetime

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


class BoundaryModel(BaseModel):
    """Strict, provider-neutral data accepted by the summarization boundary."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class EmailParticipant(BoundaryModel):
    address: EmailStr
    name: str | None = Field(default=None, max_length=200)


class AttachmentMetadata(BoundaryModel):
    filename: str = Field(min_length=1, max_length=255)
    media_type: str = Field(min_length=1, max_length=255)
    size_bytes: int | None = Field(default=None, ge=0)


class EmailMessageInput(BoundaryModel):
    message_id: str = Field(min_length=1, max_length=256)
    thread_id: str | None = Field(default=None, min_length=1, max_length=256)
    subject: str = Field(default="", max_length=998)
    sender: EmailParticipant
    to_recipients: list[EmailParticipant] = Field(default_factory=list, max_length=500)
    cc_recipients: list[EmailParticipant] = Field(default_factory=list, max_length=500)
    sent_at: AwareDatetime
    body_text: str | None = None
    body_html: str | None = None
    attachments: list[AttachmentMetadata] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def require_a_body(self) -> "EmailMessageInput":
        if not (self.body_text and self.body_text.strip()) and not (
            self.body_html and self.body_html.strip()
        ):
            raise ValueError("at least one non-empty body_text or body_html value is required")
        return self


class SummarizationRequest(BoundaryModel):
    messages: list[EmailMessageInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_thread(self) -> "SummarizationRequest":
        message_ids = [message.message_id for message in self.messages]
        if len(message_ids) != len(set(message_ids)):
            raise ValueError("message_id values must be unique")

        if len(self.messages) > 1:
            thread_ids = {message.thread_id for message in self.messages}
            if None in thread_ids or len(thread_ids) != 1:
                raise ValueError("multiple messages must share one non-empty thread_id")
        return self


class CitedItem(BoundaryModel):
    text: str = Field(min_length=1, max_length=2_000)
    source_message_ids: list[str] = Field(min_length=1, max_length=20)


class ActionItem(BoundaryModel):
    task: str = Field(min_length=1, max_length=2_000)
    owner: str | None = Field(default=None, max_length=300)
    deadline: str | None = Field(default=None, max_length=300)
    source_message_ids: list[str] = Field(min_length=1, max_length=20)


class GeneratedSummary(BoundaryModel):
    """The exact structured payload every model adapter must produce."""

    summary_text: str = Field(min_length=1, max_length=4_000)
    key_points: list[CitedItem] = Field(default_factory=list, max_length=7)
    action_items: list[ActionItem] = Field(default_factory=list, max_length=20)
    language: str = Field(pattern=r"^(?:[a-z]{2,3}|und)$")

    @property
    def overview(self) -> str:
        """Backward-compatible Python alias; API serialization uses summary_text."""
        return self.summary_text


class SummarizationResult(GeneratedSummary):
    # These fields intentionally match src.orchestrator.contracts.EmailSummary.
    sender: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, max_length=998)
    raw_email: None = Field(
        default=None,
        description="Raw email content is intentionally never forwarded to orchestration.",
    )
    request_id: str
    source_message_ids: list[str]
    omitted_message_ids: list[str] = Field(default_factory=list)
    truncated: bool


class ErrorResponse(BoundaryModel):
    request_id: str
    code: str
    message: str
    retryable: bool


class NormalizedAttachment(BoundaryModel):
    filename: str
    media_type: str
    size_bytes: int | None
    content_analyzed: bool = False


class NormalizedMessage(BoundaryModel):
    message_id: str
    thread_id: str | None
    subject: str
    sender: str
    recipients: list[str]
    sent_at: datetime
    body: str
    attachments: list[NormalizedAttachment]


class NormalizedThread(BoundaryModel):
    messages: list[NormalizedMessage]
    omitted_message_ids: list[str]
