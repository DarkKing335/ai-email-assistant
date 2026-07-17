"""Initial whitelist schema migration."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -- whitelist_entries --------------------------------------------------
    op.create_table(
        "whitelist_entries",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "entry_type",
            sa.Enum("email", "domain", name="entry_type_enum"),
            nullable=False,
        ),
        sa.Column("value", sa.String(320), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, default=True),
        sa.Column("priority", sa.Integer, nullable=False, default=0),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("created_by", sa.String(200), nullable=True),
    )
    op.create_index("ix_whitelist_entries_entry_type", "whitelist_entries", ["entry_type"])
    op.create_index("ix_whitelist_entries_is_active", "whitelist_entries", ["is_active"])
    op.create_index(
        "ix_whitelist_type_priority",
        "whitelist_entries",
        ["entry_type", "priority"],
    )
    op.create_unique_constraint(
        "uq_whitelist_value_active", "whitelist_entries", ["value", "is_active"]
    )

    # -- match_logs ---------------------------------------------------------
    op.create_table(
        "match_logs",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("gmail_message_id", sa.String(256), nullable=False, unique=True),
        sa.Column("gmail_thread_id", sa.String(256), nullable=True),
        sa.Column("sender_email", sa.String(320), nullable=False),
        sa.Column("sender_name", sa.String(200), nullable=True),
        sa.Column("subject", sa.String(998), nullable=True),
        sa.Column("whitelist_entry_id", sa.Integer, sa.ForeignKey("whitelist_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("matched_rule", sa.String(320), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending", "processing", "completed", "failed", "skipped",
                name="execution_status_enum",
            ),
            nullable=False,
            default="pending",
        ),
        sa.Column("retry_count", sa.Integer, nullable=False, default=0),
        sa.Column("error_detail", sa.Text, nullable=True),
        sa.Column("processing_ms", sa.Integer, nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_match_logs_gmail_message_id", "match_logs", ["gmail_message_id"])
    op.create_index("ix_match_logs_gmail_thread_id", "match_logs", ["gmail_thread_id"])
    op.create_index("ix_match_logs_sender_email", "match_logs", ["sender_email"])
    op.create_index("ix_match_logs_status", "match_logs", ["status"])
    op.create_index("ix_match_logs_received_at", "match_logs", ["received_at"])
    op.create_index("ix_match_logs_whitelist_entry_id", "match_logs", ["whitelist_entry_id"])

    # -- generated_drafts ---------------------------------------------------
    op.create_table(
        "generated_drafts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("match_log_id", sa.Integer, sa.ForeignKey("match_logs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False, default=1),
        sa.Column("draft_text", sa.Text, nullable=False),
        sa.Column("template_id", sa.String(100), nullable=False),
        sa.Column("confidence_score", sa.Float, nullable=False),
        sa.Column("extracted_data", sa.JSON, nullable=False),
        sa.Column("provider_used", sa.String(50), nullable=False),
        sa.Column("used_fallback", sa.Boolean, nullable=False, default=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_generated_drafts_match_log_id", "generated_drafts", ["match_log_id"])
    op.create_unique_constraint(
        "uq_draft_log_version", "generated_drafts", ["match_log_id", "version"]
    )

def downgrade() -> None:
    op.drop_table("generated_drafts")
    op.drop_table("match_logs")
    op.drop_table("whitelist_entries")
