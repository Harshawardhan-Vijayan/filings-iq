"""Search API — returns ranked filing passages (no answer generation)."""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.retrieval.search import (
    RetrievedChunk,
    fulltext_search,
    hybrid_search,
    vector_search,
)

router = APIRouter(prefix="/search", tags=["search"])

_METHODS = {
    "vector": vector_search,
    "fulltext": fulltext_search,
    "hybrid": hybrid_search,
}


class Passage(BaseModel):
    chunk_id: int
    ticker: str
    form_type: str
    filing_date: str
    fiscal_year: int | None
    fiscal_quarter: int | None
    section_key: str
    section_title: str
    content: str
    score: float


class SearchResponse(BaseModel):
    query: str
    method: str
    passages: list[Passage]


def _to_passage(rc: RetrievedChunk) -> Passage:
    return Passage(**rc.__dict__)


@router.get("")
def search(
    q: str = Query(..., description="Natural-language search query"),
    method: str = Query("hybrid", description="vector | fulltext | hybrid"),
    ticker: str | None = Query(None),
    section_key: str | None = Query(None),
    form_type: str | None = Query(None),
    fiscal_year: int | None = Query(None),
    top_k: int = Query(5, ge=1, le=50),
    db: Session = Depends(get_db),
) -> SearchResponse:
    search_fn = _METHODS.get(method, hybrid_search)
    results = search_fn(
        db, q,
        ticker=ticker, section_key=section_key,
        form_type=form_type, fiscal_year=fiscal_year, top_k=top_k,
    )
    return SearchResponse(
        query=q,
        method=method if method in _METHODS else "hybrid",
        passages=[_to_passage(r) for r in results],
    )
