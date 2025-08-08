"""add metrics columns to transcripts and translations

Revision ID: d2e3f4a5b6c7
Revises: c7d8e9f0a1b2
Create Date: 2025-08-09 10:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, Sequence[str], None] = "c7d8e9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.add_column(
            sa.Column("audio_duration_seconds", sa.Float(), nullable=True)
        )
        batch_op.add_column(sa.Column("processing_seconds", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("text_chars", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("real_time_factor", sa.Float(), nullable=True))
    with op.batch_alter_table("translations") as batch_op:
        batch_op.add_column(sa.Column("processing_seconds", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("text_chars", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("translations") as batch_op:
        batch_op.drop_column("text_chars")
        batch_op.drop_column("processing_seconds")
    with op.batch_alter_table("transcripts") as batch_op:
        batch_op.drop_column("real_time_factor")
        batch_op.drop_column("text_chars")
        batch_op.drop_column("processing_seconds")
        batch_op.drop_column("audio_duration_seconds")
