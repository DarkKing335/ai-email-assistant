"""Record when a reply went out on a thread.

The Inbox lists emails awaiting attention. Once a reply has been sent the email
is dealt with, so it should stop appearing there — but the row itself is still
wanted for Logs and the dashboard, so this retires it rather than deleting it.

Not an `ExecutionStatus` member: status describes how our processing ended and
must keep saying so. A reply is a separate, later fact.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "match_logs",
        sa.Column("replied_at", sa.DateTime(timezone=True), nullable=True),
    )
    # Indexed because the Inbox query filters on it on every page load.
    op.create_index("ix_match_logs_replied_at", "match_logs", ["replied_at"])


def downgrade() -> None:
    op.drop_index("ix_match_logs_replied_at", table_name="match_logs")
    op.drop_column("match_logs", "replied_at")
