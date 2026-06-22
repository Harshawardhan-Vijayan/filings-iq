"""add filing_chunks with pgvector

Revision ID: b6fecdc0beee
Revises: 49a7bdcbee21
Create Date: 2026-06-21 22:15:57.436378

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'b6fecdc0beee'
down_revision: Union[str, Sequence[str], None] = '49a7bdcbee21'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table('filing_chunks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('filing_id', sa.Integer(), nullable=False),
    sa.Column('section_id', sa.Integer(), nullable=False),
    sa.Column('ticker', sa.String(length=10), nullable=False),
    sa.Column('form_type', sa.String(length=20), nullable=False),
    sa.Column('filing_date', sa.Date(), nullable=False),
    sa.Column('fiscal_year', sa.Integer(), nullable=True),
    sa.Column('fiscal_quarter', sa.Integer(), nullable=True),
    sa.Column('section_key', sa.String(length=50), nullable=False),
    sa.Column('section_title', sa.String(length=255), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('token_count', sa.Integer(), nullable=False),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=False),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['filing_id'], ['filings.id'], ),
    sa.ForeignKeyConstraint(['section_id'], ['filing_sections.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_filing_chunks_filing_id'), 'filing_chunks', ['filing_id'], unique=False)
    op.create_index(op.f('ix_filing_chunks_section_key'), 'filing_chunks', ['section_key'], unique=False)
    op.create_index(op.f('ix_filing_chunks_ticker'), 'filing_chunks', ['ticker'], unique=False)
    # HNSW index for fast approximate cosine-similarity search
    op.execute(
        "CREATE INDEX ix_filing_chunks_embedding_hnsw "
        "ON filing_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_filing_chunks_embedding_hnsw")
    op.drop_index(op.f('ix_filing_chunks_ticker'), table_name='filing_chunks')
    op.drop_index(op.f('ix_filing_chunks_section_key'), table_name='filing_chunks')
    op.drop_index(op.f('ix_filing_chunks_filing_id'), table_name='filing_chunks')
    op.drop_table('filing_chunks')
    # ### end Alembic commands ###
