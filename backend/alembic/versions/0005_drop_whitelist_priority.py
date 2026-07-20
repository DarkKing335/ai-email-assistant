"""Drop the unused whitelist priority column.

`priority` was meant to order rules within a tier, but it never could:
`uq_whitelist_value_active` allows only one active row per value, so a sender
matches at most one exact rule and at most one domain rule. There was never a
tie to break. Exact-beats-domain is decided separately in the matcher and is
unaffected.

The column drop loses whatever numbers were stored. That is the point — they
influenced nothing.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Batch mode so this also runs on SQLite, which cannot ALTER away a column
    # in place — alembic rebuilds the table and copies the rows instead.
    op.drop_index("ix_whitelist_type_priority", table_name="whitelist_entries")
    with op.batch_alter_table("whitelist_entries") as batch:
        batch.drop_column("priority")


def downgrade() -> None:
    # Restored as 0 for every row: the original values are gone, and since
    # nothing read them there is no meaningful reconstruction.
    with op.batch_alter_table("whitelist_entries") as batch:
        batch.add_column(
            sa.Column("priority", sa.Integer, nullable=False, server_default="0")
        )
    op.create_index(
        "ix_whitelist_type_priority",
        "whitelist_entries",
        ["entry_type", "priority"],
    )
