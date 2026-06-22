"""Vector, full-text, and hybrid search over filing chunks."""

import re
from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.filing_chunk import FilingChunk
from backend.retrieval.embeddings import embed_query

# Minimal stopword set — Postgres also drops these, but removing them up front
# keeps the OR-query small and avoids empty-token noise.
_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "did", "do", "does", "for",
    "from", "had", "has", "have", "in", "is", "it", "its", "of", "on", "or",
    "that", "the", "their", "to", "was", "were", "what", "which", "with",
}


def _build_or_tsquery(query: str) -> str | None:
    """Turn a natural-language query into an OR tsquery string.

    'What risks ... artificial intelligence?' -> 'risks | artificial | intelligence'
    Returns None if no usable terms remain.
    """
    tokens = re.findall(r"[a-z0-9]+", query.lower())
    terms = [t for t in tokens if t not in _STOPWORDS and len(t) > 1]
    return " | ".join(dict.fromkeys(terms)) or None  # dedup, preserve order


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
    score: float  # meaning depends on method: cosine sim, ts_rank, or fused RRF score


def _apply_filters(
    q,
    ticker: str | None,
    section_key: str | None,
    form_type: str | None,
    fiscal_year: int | None,
):
    if ticker:
        q = q.filter(FilingChunk.ticker == ticker.upper())
    if section_key:
        q = q.filter(FilingChunk.section_key == section_key)
    if form_type:
        q = q.filter(FilingChunk.form_type == form_type)
    if fiscal_year is not None:
        q = q.filter(FilingChunk.fiscal_year == fiscal_year)
    return q


def _to_retrieved(chunk: FilingChunk, score: float) -> RetrievedChunk:
    return RetrievedChunk(
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
        score=round(score, 4),
    )


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
    q = _apply_filters(q, ticker, section_key, form_type, fiscal_year)
    rows = q.order_by(distance).limit(top_k).all()

    return [_to_retrieved(chunk, 1.0 - float(dist)) for chunk, dist in rows]


def fulltext_search(
    db: Session,
    query: str,
    ticker: str | None = None,
    section_key: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
) -> list[RetrievedChunk]:
    """PostgreSQL full-text search over chunk content, ranked by ts_rank.

    Uses an OR query so chunks matching any significant term are candidates,
    ranked by how many/how important the matching terms are.
    """
    or_query = _build_or_tsquery(query)
    if not or_query:
        return []
    tsquery = func.to_tsquery("english", or_query)
    rank = func.ts_rank(FilingChunk.content_tsv, tsquery)

    q = db.query(FilingChunk, rank.label("rank")).filter(
        FilingChunk.content_tsv.op("@@")(tsquery)
    )
    q = _apply_filters(q, ticker, section_key, form_type, fiscal_year)
    rows = q.order_by(rank.desc()).limit(top_k).all()

    return [_to_retrieved(chunk, float(r)) for chunk, r in rows]


def hybrid_search(
    db: Session,
    query: str,
    ticker: str | None = None,
    section_key: str | None = None,
    form_type: str | None = None,
    fiscal_year: int | None = None,
    top_k: int = 5,
    candidate_k: int = 20,
    rrf_k: int = 60,
) -> list[RetrievedChunk]:
    """Combine vector and full-text results via Reciprocal Rank Fusion.

    RRF score for a chunk = sum over result lists of 1 / (rrf_k + rank).
    This blends semantic matches (vector) with exact keyword matches (full-text)
    without needing the two scores to be on the same scale.
    """
    vec = vector_search(db, query, ticker, section_key, form_type, fiscal_year, candidate_k)
    fts = fulltext_search(db, query, ticker, section_key, form_type, fiscal_year, candidate_k)

    scores: dict[int, float] = {}
    chunks: dict[int, RetrievedChunk] = {}
    for results in (vec, fts):
        for rank, rc in enumerate(results, start=1):
            scores[rc.chunk_id] = scores.get(rc.chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            chunks[rc.chunk_id] = rc

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)[:top_k]
    out: list[RetrievedChunk] = []
    for chunk_id, fused in ranked:
        rc = chunks[chunk_id]
        out.append(_to_retrieved_from(rc, round(fused, 6)))
    return out


def _to_retrieved_from(rc: RetrievedChunk, score: float) -> RetrievedChunk:
    """Copy a RetrievedChunk with a new score."""
    return RetrievedChunk(
        chunk_id=rc.chunk_id, filing_id=rc.filing_id, ticker=rc.ticker,
        form_type=rc.form_type, filing_date=rc.filing_date,
        fiscal_year=rc.fiscal_year, fiscal_quarter=rc.fiscal_quarter,
        section_key=rc.section_key, section_title=rc.section_title,
        content=rc.content, score=score,
    )
