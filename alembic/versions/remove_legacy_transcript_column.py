"""remove legacy transcript column from audio_files

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2025-08-08 18:30:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c7d8e9f0a1b2"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use batch operations for safety if needed (SQLite), though we are on Postgres
    with op.batch_alter_table("audio_files") as batch_op:
        # If column may not exist (in case of partial deployments), guard it
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        cols = [c["name"] for c in inspector.get_columns("audio_files")]
        if "transcript" in cols:
            batch_op.drop_column("transcript")


def downgrade() -> None:
    with op.batch_alter_table("audio_files") as batch_op:
        batch_op.add_column(sa.Column("transcript", sa.Text(), nullable=True))
