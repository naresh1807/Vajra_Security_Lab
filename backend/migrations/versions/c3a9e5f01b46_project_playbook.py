"""per-project hunt playbook

Revision ID: c3a9e5f01b46
Revises: b7f2d1a4c8e3
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c3a9e5f01b46"
down_revision: Union[str, Sequence[str], None] = "b7f2d1a4c8e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("playbook", sa.JSON(), nullable=False, server_default="[]"))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("playbook")
