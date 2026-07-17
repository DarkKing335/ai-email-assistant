"""
ORM models for the AutoReply Whitelist feature.

Tables
------
whitelist_entries  — email/domain rules with priority
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
    Index,
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
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Higher value = evaluated first. Tie-broken by id.",
    )

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
        UniqueConstraint("value", "is_active", name="uq_whitelist_value_active"),
        Index("ix_whitelist_type_priority", "entry_type", "priority"),
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

    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
