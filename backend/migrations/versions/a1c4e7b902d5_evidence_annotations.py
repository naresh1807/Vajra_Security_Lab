"""evidence attachment annotations

Revision ID: a1c4e7b902d5
Revises: 0d7c4f9e1a20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "a1c4e7b902d5"
down_revision: Union[str, Sequence[str], None] = "0d7c4f9e1a20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evidence_attachments") as batch_op:
        batch_op.add_column(sa.Column("annotations", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("evidence_attachments") as batch_op:
        batch_op.drop_column("annotations")
