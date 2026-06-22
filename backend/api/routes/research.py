"""Research API — grounded question answering with citations."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.schemas.research import ResearchAnswer, ResearchQuery
from backend.workflows.agent import run_agent
from backend.workflows.qa import answer_question

router = APIRouter(prefix="/research", tags=["research"])


@router.post("/query")
def research_query(query: ResearchQuery, db: Session = Depends(get_db)) -> ResearchAnswer:
    """Single-shot grounded QA over retrieved passages (Day 10)."""
    return answer_question(db, query)


@router.post("/agent")
def research_agent(query: ResearchQuery, db: Session = Depends(get_db)) -> ResearchAnswer:
    """Tool-using orchestrator that routes between financial tools and retrieval (Day 12)."""
    return run_agent(db, query.question, ticker=query.ticker)
