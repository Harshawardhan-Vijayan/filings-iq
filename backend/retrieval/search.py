"""Vector similarity search over filing chunks with metadata filtering."""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from backend.models.filing_chunk import FilingChunk
from backend.retrieval.embeddings import embed_query


@dataclass
class RetrievedChunk:
    chunk_id: int
    filing_id: int
    ticker: str
    form_type: str
    filing_date: str
    fiscal_year: int | None
    fiscal_quarter: int | None
    section_key: str
    section_title: str
    content: str
    score: float  # cosine similarity in [0, 1], higher is closer


def vector_search(
    db: Session,
    query: str,
    ticker: str | None = None,
    section_key: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """Embed the query and return the top-k most similar chunks, with filters applied."""
    query_embedding = embed_query(query)

    # cosine_distance is in [0, 2]; similarity = 1 - distance
    distance = FilingChunk.embedding.cosine_distance(query_embedding)

    q = db.query(FilingChunk, distance.label("distance"))
    if ticker:
        q = q.filter(FilingChunk.ticker == ticker.upper())
    if section_key:
        q = q.filter(FilingChunk.section_key == section_key)
    if form_type:
        q = q.filter(FilingChunk.form_type == form_type)
    if fiscal_year is not None:
        q = q.filter(FilingChunk.fiscal_year == fiscal_year)

    rows = q.order_by(distance).limit(top_k).all()

    return [
        RetrievedChunk(
            chunk_id=chunk.id,
            filing_id=chunk.filing_id,
            ticker=chunk.ticker,
            form_type=chunk.form_type,
            filing_date=chunk.filing_date.isoformat(),
            fiscal_year=chunk.fiscal_year,
            fiscal_quarter=chunk.fiscal_quarter,
            section_key=chunk.section_key,
            section_title=chunk.section_title,
            content=chunk.content,
            score=round(1.0 - float(dist), 4),
        )
        for chunk, dist in rows
    ]
