from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class FilingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    company_id: int
    form_type: str
    filing_date: date
    period_of_report: date | None
    accession_number: str
    source_url: str
    local_path: str | None
    fiscal_year: int | None
    fiscal_quarter: int | None
    created_at: datetime


class IngestRequest(BaseModel):
    form_types: list[str] = ["10-Q"]
    max_filings: int = 3
