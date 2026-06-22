"""add full-text search to filing_chunks

Revision ID: 2ec11ee5d0d2
Revises: b6fecdc0beee
Create Date: 2026-06-21 22:33:23.912616

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2ec11ee5d0d2'
down_revision: Union[str, Sequence[str], None] = 'b6fecdc0beee'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add a generated tsvector column over chunk content, with a GIN index."""
    op.execute(
        "ALTER TABLE filing_chunks ADD COLUMN content_tsv tsvector "
        "GENERATED ALWAYS AS (to_tsvector('english', content)) STORED"
    )
    op.execute(
        "CREATE INDEX ix_filing_chunks_content_tsv "
        "ON filing_chunks USING gin (content_tsv)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_filing_chunks_content_tsv")
    op.execute("ALTER TABLE filing_chunks DROP COLUMN IF EXISTS content_tsv")
