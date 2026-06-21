from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.ingestion.edgar_client import get_company_cik, list_company_filings
from backend.ingestion.ingest import ingest_recent_filings
from backend.models.filing import Filing
from backend.schemas.filing import FilingOut, IngestRequest

router = APIRouter(prefix="/companies", tags=["filings"])


@router.get("/{ticker}/filings")
def get_filings(ticker: str, db: Session = Depends(get_db)) -> list[FilingOut]:
    ticker = ticker.upper()
    filings = db.query(Filing).join(Filing.company).filter_by(ticker=ticker).all()
    return [FilingOut.model_validate(f) for f in filings]


@router.get("/{ticker}/filings/available")
def list_available_filings(
    ticker: str,
    form_type: str = "10-Q",
) -> list[dict]:
    """List filings available on EDGAR (not yet ingested)."""
    ticker = ticker.upper()
    try:
        cik = get_company_cik(ticker)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return list_company_filings(cik, form_types=[form_type], max_results=10)


@router.post("/{ticker}/filings/ingest")
def trigger_ingest(
    ticker: str,
    body: IngestRequest,
    db: Session = Depends(get_db),
) -> list[FilingOut]:
    ticker = ticker.upper()
    try:
        filings = ingest_recent_filings(
            db,
            ticker,
            form_types=body.form_types,
            max_filings=body.max_filings,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return [FilingOut.model_validate(f) for f in filings]
