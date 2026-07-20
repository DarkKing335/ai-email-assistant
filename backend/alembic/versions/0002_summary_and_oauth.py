"""Persist email summaries; store Google OAuth credentials.

Two changes that arrived together:

- ``match_logs.summary_json`` — the structured summary was previously computed
  and discarded, leaving the Inbox view with no data source.
- ``oauth_credentials`` — tokens for the connected Google account.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable by design: rows processed before this migration have no summary,
    # and emails that are skipped or fail early never produce one.
    op.add_column("match_logs", sa.Column("summary_json", sa.JSON, nullable=True))

    op.create_table(
        "oauth_credentials",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("provider", sa.String(50), nullable=False),
        sa.Column("email_address", sa.String(320), nullable=False),
        sa.Column("access_token", sa.Text, nullable=False),
        sa.Column("refresh_token", sa.Text, nullable=False),
        sa.Column("token_expiry", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scopes", sa.Text, nullable=False),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
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
        # One connected account per provider: re-connecting replaces rather
        # than accumulates.
        sa.UniqueConstraint("provider", name="uq_oauth_provider"),
    )


def downgrade() -> None:
    op.drop_table("oauth_credentials")
    op.drop_column("match_logs", "summary_json")
