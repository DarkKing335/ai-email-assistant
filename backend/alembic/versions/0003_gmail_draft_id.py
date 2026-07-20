"""Record the Gmail draft a generated reply was filed as.

Until now the pipeline generated reply *text* and stored it, but never created
anything in Gmail — the panel could only offer "Copy". With `drafts.create`
wired up, this column links the stored text to the real draft.

Nullable: rows written before this existed have no draft, Gmail can be
unreachable at the moment of writing, and the text is worth keeping regardless.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "generated_drafts",
        sa.Column("gmail_draft_id", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("generated_drafts", "gmail_draft_id")
