"""
ORM models for the AutoReply Whitelist feature.

Tables
------
whitelist_entries  — email/domain rules
match_logs         — every inbound email that was checked against whitelist
generated_drafts   — draft versions produced by the AI workflow
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.database import Base


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class EntryType(str, enum.Enum):
    EMAIL = "email"
    DOMAIN = "domain"


class ExecutionStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"          # sender not on whitelist


# ---------------------------------------------------------------------------
# WhitelistEntry
# ---------------------------------------------------------------------------


class WhitelistEntry(Base):
    """An email address or domain pattern that triggers auto-reply."""

    __tablename__ = "whitelist_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Rule definition
    entry_type: Mapped[EntryType] = mapped_column(
        Enum(EntryType, name="entry_type_enum"), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(
        String(320), nullable=False, comment="Exact email address or @domain.com"
    )

    # Control
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(
        String(200), nullable=True, comment="User/system that created the entry."
    )

    # Relationships
    match_logs: Mapped[list[MatchLog]] = relationship(
        "MatchLog", back_populates="whitelist_entry", lazy="select"
    )

    __table_args__ = (
        # This is also why rule precedence needs no tie-breaker: at most one
        # active row can carry any given value, so a sender can match at most
        # one exact rule and one domain rule.
        UniqueConstraint("value", "is_active", name="uq_whitelist_value_active"),
    )

    def __repr__(self) -> str:
        return f"<WhitelistEntry id={self.id} type={self.entry_type} value={self.value!r}>"


# ---------------------------------------------------------------------------
# MatchLog
# ---------------------------------------------------------------------------


class MatchLog(Base):
    """Records every inbound email that was checked against the whitelist."""

    __tablename__ = "match_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # Idempotency — prevents duplicate processing of the same Gmail message
    gmail_message_id: Mapped[str] = mapped_column(
        String(256), nullable=False, unique=True, index=True
    )
    gmail_thread_id: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)

    # Sender info
    sender_email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    sender_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    subject: Mapped[str | None] = mapped_column(String(998), nullable=True)

    # Match result
    whitelist_entry_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("whitelist_entries.id", ondelete="SET NULL"), nullable=True, index=True
    )
    matched_rule: Mapped[str | None] = mapped_column(
        String(320), nullable=True, comment="The matched whitelist value (denormalised for logs)."
    )

    # Execution tracking
    status: Mapped[ExecutionStatus] = mapped_column(
        Enum(ExecutionStatus, name="execution_status_enum"),
        nullable=False,
        default=ExecutionStatus.PENDING,
        index=True,
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    processing_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Total end-to-end processing time in milliseconds."
    )

    # The structured summary the LLM produced for this email.
    #
    # Stored as JSON rather than normalised into tables: it is read as a whole,
    # never queried by field, and its shape is owned by `SummarizationResult`
    # — which would otherwise need a schema migration every time it gains a
    # field. Null for anything processed before summaries were persisted, and
    # for emails that never reached summarization (skipped, failed early).
    summary_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: When a reply was observed going out on this thread, which retires the
    #: email from the Inbox view — it has been dealt with.
    #:
    #: Deliberately not an `ExecutionStatus` member: status records how *our*
    #: processing ended, and stays meaningful afterwards. A reply is a later,
    #: independent fact, and folding it into the enum would overwrite the
    #: outcome and skew every status breakdown that counts it.
    #:
    #: Set from the sent-mail sweep, so it is also true when the reply was
    #: typed by hand instead of sent from the generated draft.
    replied_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Relationships
    whitelist_entry: Mapped[WhitelistEntry | None] = relationship(
        "WhitelistEntry", back_populates="match_logs"
    )
    drafts: Mapped[list[GeneratedDraft]] = relationship(
        "GeneratedDraft", back_populates="match_log", lazy="select"
    )

    def __repr__(self) -> str:
        return f"<MatchLog id={self.id} sender={self.sender_email!r} status={self.status}>"


# ---------------------------------------------------------------------------
# GeneratedDraft
# ---------------------------------------------------------------------------


class GeneratedDraft(Base):
    """A single version of an AI-generated draft reply."""

    __tablename__ = "generated_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_log_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("match_logs.id", ondelete="CASCADE"), nullable=False, index=True
    )

    # Versioning — version 1 is always the first generation attempt
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Draft content
    draft_text: Mapped[str] = mapped_column(Text, nullable=False)
    template_id: Mapped[str] = mapped_column(String(100), nullable=False)
    confidence_score: Mapped[float] = mapped_column(Float, nullable=False)
    extracted_data: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    provider_used: Mapped[str] = mapped_column(String(50), nullable=False)
    used_fallback: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    #: Gmail's id for the draft this text was filed as, when one was created.
    #: Nullable on purpose: rows predate the feature, Gmail may be unreachable
    #: at the moment of writing, and the draft text is worth keeping either way.
    #: The *draft* id rather than its message id — Gmail replaces the message
    #: and its id on every edit, so only this one stays valid.
    gmail_draft_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Audit
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    match_log: Mapped[MatchLog] = relationship("MatchLog", back_populates="drafts")

    __table_args__ = (
        UniqueConstraint("match_log_id", "version", name="uq_draft_log_version"),
    )

    def __repr__(self) -> str:
        return f"<GeneratedDraft id={self.id} log={self.match_log_id} v={self.version}>"


# ---------------------------------------------------------------------------
# OAuthCredential
# ---------------------------------------------------------------------------


class OAuthCredential(Base):
    """A connected Google account's OAuth tokens.

    Single-user by design for the MVP: `provider` is unique, so connecting a
    second account replaces the first rather than accumulating rows. Making this
    multi-account means dropping that constraint and giving every whitelist
    entry and match log an owner — a much larger change than it looks.

    ⚠️ **Tokens are stored in plaintext.** The refresh token is long-lived and
    grants continuing access to the mailbox, so `email_assistant.db` must be
    treated as a secret: never commit it, never copy it off the machine. Before
    this is deployed anywhere the tokens need encrypting at rest.
    """

    __tablename__ = "oauth_credentials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    provider: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, default="google"
    )
    email_address: Mapped[str] = mapped_column(
        String(320), nullable=False, comment="The connected Google account."
    )

    access_token: Mapped[str] = mapped_column(Text, nullable=False)
    # Google only returns a refresh token on the first consent, so this is
    # preserved across refreshes rather than overwritten with an absent value.
    refresh_token: Mapped[str] = mapped_column(Text, nullable=False)
    token_expiry: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    scopes: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Space-separated scopes actually granted."
    )

    # Polling watermark: only messages after this are considered new.
    last_polled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<OAuthCredential provider={self.provider} email={self.email_address!r}>"
