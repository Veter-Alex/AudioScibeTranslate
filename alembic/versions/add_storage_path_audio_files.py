"""add storage_path to audio_files

Revision ID: 9d7b0f2e2b11
Revises: f118b9b596f9
Create Date: 2025-08-08 15:40:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9d7b0f2e2b11"
down_revision: Union[str, Sequence[str], None] = "f118b9b596f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("audio_files", sa.Column("storage_path", sa.String(), nullable=True))
    # Optionally fill storage_path for existing rows (left NULL here)
    # op.execute("UPDATE audio_files SET storage_path = filename")
    op.create_index("ix_audio_files_storage_path", "audio_files", ["storage_path"])


def downgrade() -> None:
    op.drop_index("ix_audio_files_storage_path", table_name="audio_files")
    op.drop_column("audio_files", "storage_path")
