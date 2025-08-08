"""add transcript/translation/summary tables

Revision ID: a1b2c3d4e5f6
Revises: 9d7b0f2e2b11
Create Date: 2025-08-08 16:00:00
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "9d7b0f2e2b11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "transcripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "audio_file_id",
            sa.Integer(),
            sa.ForeignKey("audio_files.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )
    # Index creation separated to avoid duplicate creation races; use IF NOT EXISTS pattern with raw SQL
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_transcripts_audio_file_id ON transcripts (audio_file_id)"
    )

    op.create_table(
        "translations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "transcript_id",
            sa.Integer(),
            sa.ForeignKey("transcripts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_language", sa.String(), nullable=True),
        sa.Column("target_language", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )
    op.create_index("ix_translations_transcript_id", "translations", ["transcript_id"])

    op.create_table(
        "summaries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "source_translation_id",
            sa.Integer(),
            sa.ForeignKey("translations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("base_language", sa.String(), nullable=True),
        sa.Column("target_language", sa.String(), nullable=False),
        sa.Column("model_name", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
        sa.Column("text", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()")
        ),
    )
    op.create_index(
        "ix_summaries_source_translation_id", "summaries", ["source_translation_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_summaries_source_translation_id", table_name="summaries")
    op.drop_table("summaries")
    op.drop_index("ix_translations_transcript_id", table_name="translations")
    op.drop_table("translations")
    op.execute("DROP INDEX IF EXISTS ix_transcripts_audio_file_id")
    op.drop_table("transcripts")
    op.drop_table("transcripts")
