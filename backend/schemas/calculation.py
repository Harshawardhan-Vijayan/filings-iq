from pydantic import BaseModel


class CalculationResult(BaseModel):
    """An auditable financial calculation: result plus the formula and inputs that produced it.

    Every ratio in a FilingsIQ answer is one of these, so the LLM never does arithmetic
    and a reviewer can verify the math by hand.
    """

    label: str
    formula: str
    inputs: dict[str, float]
    result: float
    unit: str  # e.g. "ratio", "percent", "USD"


class MetricValue(BaseModel):
    """A single financial fact resolved from the database."""

    ticker: str
    metric_name: str
    value: float
    unit: str
    period_end: str
    fiscal_year: int | None
    fiscal_quarter: int | None
    fiscal_period: str | None
    form_type: str


class PeriodComparison(BaseModel):
    """Two periods of the same metric plus the growth between them."""

    ticker: str
    metric_name: str
    current: MetricValue
    prior: MetricValue
    growth: CalculationResult
