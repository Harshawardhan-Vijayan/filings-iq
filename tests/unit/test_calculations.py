import pytest

from backend.tools.calculations import (
    CalculationError,
    calculate_debt_to_assets,
    calculate_free_cash_flow,
    calculate_growth_rate,
    calculate_net_margin,
    calculate_operating_margin,
)


def test_growth_rate_positive() -> None:
    r = calculate_growth_rate(110, 100)
    assert r.result == 0.1
    assert r.inputs == {"current": 110, "prior": 100}


def test_growth_rate_negative() -> None:
    r = calculate_growth_rate(90, 100)
    assert r.result == -0.1


def test_growth_rate_zero_prior_raises() -> None:
    with pytest.raises(CalculationError):
        calculate_growth_rate(100, 0)


def test_operating_margin_known_value() -> None:
    # MSFT-like Q: operating income 30649 / revenue 69632 = 0.44018 → 0.4402
    r = calculate_operating_margin(30649, 69632)
    assert r.result == 0.4402
    assert r.formula == "operating_income / revenue"


def test_operating_margin_zero_revenue_raises() -> None:
    with pytest.raises(CalculationError):
        calculate_operating_margin(100, 0)


def test_net_margin_known_value() -> None:
    r = calculate_net_margin(25, 100)
    assert r.result == 0.25


def test_free_cash_flow() -> None:
    r = calculate_free_cash_flow(operating_cash_flow=46679, capex=16979)
    assert r.result == 29700.0
    assert r.unit == "USD"


def test_free_cash_flow_can_be_negative() -> None:
    r = calculate_free_cash_flow(operating_cash_flow=100, capex=150)
    assert r.result == -50.0


def test_debt_to_assets_known_value() -> None:
    r = calculate_debt_to_assets(long_term_debt=40262, assets=523013)
    assert r.result == 0.077
    assert r.unit == "ratio"


def test_debt_to_assets_zero_assets_raises() -> None:
    with pytest.raises(CalculationError):
        calculate_debt_to_assets(100, 0)


def test_calculation_result_is_auditable() -> None:
    """Every result must carry formula + inputs so a reviewer can verify the math."""
    r = calculate_operating_margin(30649, 69632)
    # reproduce the math from the recorded inputs/formula
    assert round(r.inputs["operating_income"] / r.inputs["revenue"], 4) == r.result
