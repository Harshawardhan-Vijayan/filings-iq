"""Index filing sections into embedded, retrievable chunks."""

from sqlalchemy.orm import Session

from backend.models.filing import Filing
from backend.models.filing_chunk import FilingChunk
from backend.models.filing_section import FilingSection
from backend.retrieval.chunker import chunk_text
from backend.retrieval.embeddings import embed_texts


def index_filing(db: Session, filing_id: int) -> int:
    """Chunk every section of a filing, embed the chunks, and store them.

    Idempotent: deletes existing chunks for the filing before re-indexing.
    Returns the number of chunks created.
    """
    filing = db.query(Filing).filter_by(id=filing_id).first()
    if not filing:
        raise ValueError(f"Filing {filing_id} not found")

    sections = db.query(FilingSection).filter_by(filing_id=filing_id).all()
    if not sections:
        return 0

    db.query(FilingChunk).filter_by(filing_id=filing_id).delete()

    # Build all chunks first so we can embed them in batches
    pending: list[tuple[FilingSection, object]] = []
    for section in sections:
        for chunk in chunk_text(section.content):
            pending.append((section, chunk))

    if not pending:
        db.commit()
        return 0

    embeddings = embed_texts([c.content for _, c in pending])

    ticker = filing.company.ticker
    for (section, chunk), embedding in zip(pending, embeddings, strict=True):
        db.add(FilingChunk(
            filing_id=filing.id,
            section_id=section.id,
            ticker=ticker,
            form_type=filing.form_type,
            filing_date=filing.filing_date,
            fiscal_year=filing.fiscal_year,
            fiscal_quarter=filing.fiscal_quarter,
            section_key=section.section_key,
            section_title=section.section_title,
            chunk_index=chunk.chunk_index,
            content=chunk.content,
            token_count=chunk.token_count,
            embedding=embedding,
        ))

    db.commit()
    return len(pending)


def index_all_filings(db: Session, ticker: str | None = None) -> int:
    """Index all filings (optionally for one ticker). Returns total chunks created."""
    query = db.query(Filing)
    if ticker:
        query = query.join(Filing.company).filter_by(ticker=ticker.upper())

    total = 0
    for filing in query.all():
        total += index_filing(db, filing.id)
    return total
