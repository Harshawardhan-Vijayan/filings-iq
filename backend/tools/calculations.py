"""Deterministic financial calculations.

These are pure functions. The LLM must call these instead of computing ratios
itself — they return a CalculationResult carrying the formula and inputs so every
number is auditable.
"""

from backend.schemas.calculation import CalculationResult


class CalculationError(ValueError):
    """Raised when a calculation cannot be performed (e.g. division by zero)."""


def _round(x: float, places: int = 4) -> float:
    return round(x, places)


def calculate_growth_rate(
    current: float, prior: float, label: str = "growth rate"
) -> CalculationResult:
    """Period-over-period growth: (current - prior) / |prior|."""
    if prior == 0:
        raise CalculationError("Cannot compute growth rate from a prior value of zero")
    growth = (current - prior) / abs(prior)
    return CalculationResult(
        label=label,
        formula="(current - prior) / abs(prior)",
        inputs={"current": current, "prior": prior},
        result=_round(growth),
        unit="ratio",
    )


def calculate_operating_margin(operating_income: float, revenue: float) -> CalculationResult:
    """Operating margin: operating_income / revenue."""
    if revenue == 0:
        raise CalculationError("Cannot compute operating margin with revenue of zero")
    margin = operating_income / revenue
    return CalculationResult(
        label="operating margin",
        formula="operating_income / revenue",
        inputs={"operating_income": operating_income, "revenue": revenue},
        result=_round(margin),
        unit="ratio",
    )


def calculate_net_margin(net_income: float, revenue: float) -> CalculationResult:
    """Net profit margin: net_income / revenue."""
    if revenue == 0:
        raise CalculationError("Cannot compute net margin with revenue of zero")
    margin = net_income / revenue
    return CalculationResult(
        label="net margin",
        formula="net_income / revenue",
        inputs={"net_income": net_income, "revenue": revenue},
        result=_round(margin),
        unit="ratio",
    )


def calculate_free_cash_flow(operating_cash_flow: float, capex: float) -> CalculationResult:
    """Free cash flow: operating_cash_flow - capex.

    capex (PaymentsToAcquirePropertyPlantAndEquipment) is reported as a positive
    outflow in XBRL, so we subtract it directly.
    """
    fcf = operating_cash_flow - capex
    return CalculationResult(
        label="free cash flow",
        formula="operating_cash_flow - capex",
        inputs={"operating_cash_flow": operating_cash_flow, "capex": capex},
        result=_round(fcf, 2),
        unit="USD",
    )


def calculate_debt_to_assets(long_term_debt: float, assets: float) -> CalculationResult:
    """Debt-to-assets ratio: long_term_debt / assets."""
    if assets == 0:
        raise CalculationError("Cannot compute debt-to-assets with assets of zero")
    ratio = long_term_debt / assets
    return CalculationResult(
        label="debt-to-assets",
        formula="long_term_debt / assets",
        inputs={"long_term_debt": long_term_debt, "assets": assets},
        result=_round(ratio),
        unit="ratio",
    )
