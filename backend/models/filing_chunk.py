from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Computed, Date, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.config import settings
from backend.database import Base


class FilingChunk(Base):
    """A retrievable chunk of a filing section, with its embedding vector.

    Denormalizes the key filterable filing metadata (ticker, form_type, dates,
    section) onto each chunk so retrieval can apply metadata filters without joins.
    """

    __tablename__ = "filing_chunks"

    id: Mapped[int] = mapped_column(primary_key=True)
    filing_id: Mapped[int] = mapped_column(ForeignKey("filings.id"), nullable=False, index=True)
    section_id: Mapped[int] = mapped_column(ForeignKey("filing_sections.id"), nullable=False)

    # Denormalized metadata for fast filtering
    ticker: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    form_type: Mapped[str] = mapped_column(String(20), nullable=False)
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int | None] = mapped_column()
    fiscal_quarter: Mapped[int | None] = mapped_column()
    section_key: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)

    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)  # order within section
    content: Mapped[str] = mapped_column(Text, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(settings.embedding_dim))

    # Generated full-text search vector over `content` (managed by the database)
    content_tsv: Mapped[str | None] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', content)", persisted=True),
    )

    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    filing: Mapped["Filing"] = relationship()  # type: ignore[name-defined]
