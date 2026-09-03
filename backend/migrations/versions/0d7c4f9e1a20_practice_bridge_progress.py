"""practice bridge progress

Revision ID: 0d7c4f9e1a20
Revises: c50a6285ba21
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0d7c4f9e1a20"
down_revision: Union[str, Sequence[str], None] = "c50a6285ba21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("investigations") as batch_op:
        batch_op.add_column(sa.Column("practice_progress", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("investigations") as batch_op:
        batch_op.drop_column("practice_progress")
