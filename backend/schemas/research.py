from pydantic import BaseModel, Field

from backend.schemas.calculation import CalculationResult


class ResearchQuery(BaseModel):
    question: str
    ticker: str | None = None
    section_key: str | None = None
    fiscal_year: int | None = None
    top_k: int = 6


class Evidence(BaseModel):
    chunk_id: int
    filing: str  # form type, e.g. "10-Q"
    filing_date: str
    section: str  # human-readable section title
    excerpt: str
    source_reference: str


class ResearchAnswer(BaseModel):
    answer: str
    supporting_evidence: list[Evidence] = Field(default_factory=list)
    calculations: list[CalculationResult] = Field(default_factory=list)
    confidence: float
    limitations: list[str] = Field(default_factory=list)
    # Observability
    tokens_used: int = 0
    citations_valid: bool = True
