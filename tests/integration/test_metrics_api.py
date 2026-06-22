"""Integration tests for the financial metrics API.

Seeds a throwaway company with known facts, exercises the endpoints, then
cleans up. Requires a running PostgreSQL (skipped automatically if unavailable).
"""

from collections.abc import Generator
from datetime import date

import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.database import SessionLocal, check_db_connection
from backend.models.company import Company
from backend.models.financial_fact import FinancialFact

pytestmark = pytest.mark.skipif(not check_db_connection(), reason="PostgreSQL not available")

client = TestClient(app)
TEST_TICKER = "ZZZ"


def _cleanup(db) -> None:
    """Delete facts before the company to satisfy the FK constraint."""
    existing = db.query(Company).filter_by(ticker=TEST_TICKER).first()
    if existing:
        db.query(FinancialFact).filter_by(company_id=existing.id).delete()
        db.query(Company).filter_by(ticker=TEST_TICKER).delete()
        db.commit()


@pytest.fixture
def seeded_company() -> Generator[int, None, None]:
    db = SessionLocal()
    _cleanup(db)

    company = Company(ticker=TEST_TICKER, name="Test Co", cik="0000000001")
    db.add(company)
    db.flush()
    cid = company.id

    facts = [
        # current period FY2026 Q3
        ("revenue", 100000, 2026, 3, date(2026, 3, 31)),
        ("operating_income", 47000, 2026, 3, date(2026, 3, 31)),
        ("net_income", 30000, 2026, 3, date(2026, 3, 31)),
        ("operating_cash_flow", 50000, 2026, 3, date(2026, 3, 31)),
        ("capex", 12000, 2026, 3, date(2026, 3, 31)),
        ("long_term_debt", 40000, 2026, 3, date(2026, 3, 31)),
        ("assets", 500000, 2026, 3, date(2026, 3, 31)),
        # prior year FY2025 Q3
        ("revenue", 80000, 2025, 3, date(2025, 3, 31)),
    ]
    for name, val, fy, fq, pend in facts:
        db.add(
            FinancialFact(
                company_id=cid,
                metric_name=name,
                xbrl_tag=f"Mock{name}",
                value=val,
                unit="USD",
                period_end=pend,
                fiscal_year=fy,
                fiscal_quarter=fq,
                fiscal_period=f"Q{fq}",
                form_type="10-Q",
            )
        )
    db.commit()
    db.close()

    yield cid

    db = SessionLocal()
    _cleanup(db)
    db.close()


def test_list_metrics(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/metrics")
    assert r.status_code == 200
    names = {m["metric_name"] for m in r.json()}
    assert "revenue" in names
    assert "operating_income" in names


def test_list_metrics_returns_latest_period(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/metrics")
    revenue = next(m for m in r.json() if m["metric_name"] == "revenue")
    assert revenue["value"] == 100000  # FY2026, not the FY2025 80000


def test_get_metric_latest(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/metrics/revenue")
    assert r.status_code == 200
    assert r.json()[0]["value"] == 100000


def test_get_metric_history(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/metrics/revenue", params={"history": True})
    assert r.status_code == 200
    assert len(r.json()) == 2  # two periods of revenue


def test_get_metric_unknown_company() -> None:
    r = client.get("/companies/NOPE/metrics/revenue")
    assert r.status_code == 404


def test_get_ratio_operating_margin(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/ratios/operating_margin")
    assert r.status_code == 200
    body = r.json()
    assert body["result"] == 0.47  # 47000 / 100000
    assert body["formula"] == "operating_income / revenue"


def test_get_ratio_free_cash_flow(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/ratios/free_cash_flow")
    assert r.json()["result"] == 38000  # 50000 - 12000


def test_get_ratio_unknown(seeded_company: int) -> None:
    r = client.get(f"/companies/{TEST_TICKER}/ratios/bogus")
    assert r.status_code == 400


def test_compare_periods_growth(seeded_company: int) -> None:
    r = client.get(
        f"/companies/{TEST_TICKER}/comparisons",
        params={
            "metric": "revenue",
            "current_year": 2026,
            "current_quarter": 3,
            "prior_year": 2025,
            "prior_quarter": 3,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["current"]["value"] == 100000
    assert body["prior"]["value"] == 80000
    assert body["growth"]["result"] == 0.25  # (100000-80000)/80000
