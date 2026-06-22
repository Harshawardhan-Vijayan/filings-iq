"""Database-backed financial metric lookups.

These resolve raw FinancialFact rows into typed values and feed the deterministic
calculations in calculations.py.
"""

from sqlalchemy.orm import Session

from backend.models.company import Company
from backend.models.financial_fact import FinancialFact
from backend.schemas.calculation import MetricValue, PeriodComparison
from backend.tools.calculations import calculate_growth_rate


class MetricNotFoundError(ValueError):
    """Raised when no financial fact matches the requested metric/period."""


def _fact_to_value(ticker: str, fact: FinancialFact) -> MetricValue:
    return MetricValue(
        ticker=ticker,
        metric_name=fact.metric_name,
        value=float(fact.value),
        unit=fact.unit,
        period_end=fact.period_end.isoformat(),
        fiscal_year=fact.fiscal_year,
        fiscal_quarter=fact.fiscal_quarter,
        fiscal_period=fact.fiscal_period,
        form_type=fact.form_type,
    )


def _resolve_company(db: Session, ticker: str) -> Company:
    company = db.query(Company).filter_by(ticker=ticker.upper()).first()
    if not company:
        raise MetricNotFoundError(f"Company {ticker} not found")
    return company


def get_financial_metric(
    db: Session,
    ticker: str,
    metric_name: str,
    fiscal_year: int | None = None,
    fiscal_quarter: int | None = None,
) -> MetricValue:
    """Resolve a single metric for a company.

    If fiscal_year/quarter are omitted, returns the most recent period available.
    """
    company = _resolve_company(db, ticker)

    query = db.query(FinancialFact).filter_by(company_id=company.id, metric_name=metric_name)
    if fiscal_year is not None:
        query = query.filter_by(fiscal_year=fiscal_year)
    if fiscal_quarter is not None:
        query = query.filter_by(fiscal_quarter=fiscal_quarter)

    fact = query.order_by(FinancialFact.period_end.desc()).first()
    if not fact:
        raise MetricNotFoundError(
            f"No '{metric_name}' fact for {ticker} (fy={fiscal_year}, q={fiscal_quarter})"
        )
    return _fact_to_value(ticker.upper(), fact)


def compare_metric_periods(
    db: Session,
    ticker: str,
    metric_name: str,
    current_year: int,
    current_quarter: int | None,
    prior_year: int,
    prior_quarter: int | None,
) -> PeriodComparison:
    """Compare a metric across two periods and compute the growth between them."""
    current = get_financial_metric(db, ticker, metric_name, current_year, current_quarter)
    prior = get_financial_metric(db, ticker, metric_name, prior_year, prior_quarter)

    growth = calculate_growth_rate(
        current.value,
        prior.value,
        label=f"{metric_name} growth ({prior.period_end} → {current.period_end})",
    )
    return PeriodComparison(
        ticker=ticker.upper(),
        metric_name=metric_name,
        current=current,
        prior=prior,
        growth=growth,
    )
