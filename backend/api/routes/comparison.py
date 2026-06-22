"""Comparison API — diff a filing section across two filings."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.workflows.comparison import compare_sections

router = APIRouter(prefix="/research", tags=["comparison"])


class StatementChangeOut(BaseModel):
    old: str
    new: str
    similarity: float


class ComparisonResponse(BaseModel):
    section_key: str
    section_title: str
    current_label: str
    prior_label: str
    added: list[str]
    removed: list[str]
    modified: list[StatementChangeOut]
    summary: str
    counts: dict[str, int]
    tokens_used: int


@router.get("/compare")
def compare(
    current_filing_id: int = Query(...),
    prior_filing_id: int = Query(...),
    section_key: str = Query("risk_factors"),
    summarize: bool = Query(True),
    db: Session = Depends(get_db),
) -> ComparisonResponse:
    try:
        comp = compare_sections(
            db, current_filing_id, prior_filing_id, section_key, summarize=summarize
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    return ComparisonResponse(
        section_key=comp.section_key,
        section_title=comp.section_title,
        current_label=comp.current_label,
        prior_label=comp.prior_label,
        added=comp.added,
        removed=comp.removed,
        modified=[StatementChangeOut(**vars(m)) for m in comp.modified],
        summary=comp.summary,
        counts={
            "added": len(comp.added),
            "removed": len(comp.removed),
            "modified": len(comp.modified),
        },
        tokens_used=comp.tokens_used,
    )
