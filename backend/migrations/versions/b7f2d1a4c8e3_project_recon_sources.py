"""per-project recon pipeline switches

Revision ID: b7f2d1a4c8e3
Revises: a1c4e7b902d5
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b7f2d1a4c8e3"
down_revision: Union[str, Sequence[str], None] = "a1c4e7b902d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.add_column(sa.Column("recon_sources", sa.JSON(), nullable=False, server_default="{}"))


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_column("recon_sources")
