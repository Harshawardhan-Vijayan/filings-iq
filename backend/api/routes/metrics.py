"""Financial metrics API — exposes XBRL facts and deterministic calculations."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.company import Company
from backend.models.financial_fact import FinancialFact
from backend.schemas.calculation import CalculationResult, MetricValue, PeriodComparison
from backend.tools.calculations import (
    CalculationError,
    calculate_debt_to_assets,
    calculate_free_cash_flow,
    calculate_net_margin,
    calculate_operating_margin,
)
from backend.tools.metrics import (
    MetricNotFoundError,
    compare_metric_periods,
    get_financial_metric,
)

router = APIRouter(prefix="/companies", tags=["metrics"])

# Ratio name → (function, [required metric names])
_RATIOS = {
    "operating_margin": (calculate_operating_margin, ["operating_income", "revenue"]),
    "net_margin": (calculate_net_margin, ["net_income", "revenue"]),
    "free_cash_flow": (calculate_free_cash_flow, ["operating_cash_flow", "capex"]),
    "debt_to_assets": (calculate_debt_to_assets, ["long_term_debt", "assets"]),
}


def _fact_to_value(ticker: str, f: FinancialFact) -> MetricValue:
    return MetricValue(
        ticker=ticker,
        metric_name=f.metric_name,
        value=float(f.value),
        unit=f.unit,
        period_end=f.period_end.isoformat(),
        fiscal_year=f.fiscal_year,
        fiscal_quarter=f.fiscal_quarter,
        fiscal_period=f.fiscal_period,
        form_type=f.form_type,
    )


@router.get("/{ticker}/metrics")
def list_metrics(ticker: str, db: Session = Depends(get_db)) -> list[MetricValue]:
    """Latest available value for every metric we track for this company."""
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker} not found")

    facts = (
        db.query(FinancialFact)
        .filter_by(company_id=company.id)
        .order_by(FinancialFact.metric_name, FinancialFact.period_end.desc())
        .all()
    )
    latest: list[MetricValue] = []
    seen: set[str] = set()
    for f in facts:
        if f.metric_name in seen:
            continue
        seen.add(f.metric_name)
        latest.append(_fact_to_value(ticker.upper(), f))
    return latest


@router.get("/{ticker}/metrics/{metric}")
def get_metric(
    ticker: str,
    metric: str,
    fiscal_year: int | None = Query(None),
    fiscal_quarter: int | None = Query(None),
    history: bool = Query(False, description="Return all periods instead of the latest"),
    db: Session = Depends(get_db),
) -> list[MetricValue]:
    """A metric's value(s). Latest by default; full time series when history=true."""
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise HTTPException(status_code=404, detail=f"Company {ticker} not found")

    if history:
        q = db.query(FinancialFact).filter_by(company_id=company.id, metric_name=metric)
        if fiscal_year is not None:
            q = q.filter_by(fiscal_year=fiscal_year)
        facts = q.order_by(FinancialFact.period_end.desc()).all()
        if not facts:
            raise HTTPException(status_code=404, detail=f"No '{metric}' facts for {ticker}")
        return [_fact_to_value(ticker.upper(), f) for f in facts]

    try:
        value = get_financial_metric(db, ticker, metric, fiscal_year, fiscal_quarter)
    except MetricNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return [value]


@router.get("/{ticker}/ratios/{ratio}")
def get_ratio(
    ticker: str,
    ratio: str,
    fiscal_year: int | None = Query(None),
    fiscal_quarter: int | None = Query(None),
    db: Session = Depends(get_db),
) -> CalculationResult:
    """Compute a deterministic financial ratio from the underlying metrics."""
    if ratio not in _RATIOS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown ratio '{ratio}'. Supported: {sorted(_RATIOS)}",
        )
    func, required = _RATIOS[ratio]
    try:
        values = [
            get_financial_metric(db, ticker, m, fiscal_year, fiscal_quarter).value for m in required
        ]
        return func(*values)
    except MetricNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CalculationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/{ticker}/comparisons")
def compare_periods(
    ticker: str,
    metric: str = Query(..., description="Metric name, e.g. 'revenue'"),
    current_year: int = Query(...),
    prior_year: int = Query(...),
    current_quarter: int | None = Query(None),
    prior_quarter: int | None = Query(None),
    db: Session = Depends(get_db),
) -> PeriodComparison:
    """Compare a metric across two periods and report the growth between them."""
    try:
        return compare_metric_periods(
            db,
            ticker,
            metric,
            current_year,
            current_quarter,
            prior_year,
            prior_quarter,
        )
    except MetricNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except CalculationError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
