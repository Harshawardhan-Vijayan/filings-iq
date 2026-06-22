from unittest.mock import patch

from backend.parsers.xbrl_parser import _fp_to_quarter, parse_xbrl_facts

MOCK_FACTS = {
    "facts": {
        "us-gaap": {
            "RevenueFromContractWithCustomerExcludingAssessedTax": {
                "units": {
                    "USD": [
                        {
                            "start": "2024-10-01", "end": "2024-12-31",
                            "val": 69632000000, "accn": "0001193125-25-027207",
                            "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-01-29",
                        },
                        {
                            "start": "2023-10-01", "end": "2023-12-31",
                            "val": 62020000000, "accn": "0000950170-24-008814",
                            "fy": 2024, "fp": "Q2", "form": "10-Q", "filed": "2024-01-30",
                        },
                    ]
                }
            },
            "OperatingIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "start": "2024-10-01", "end": "2024-12-31",
                            "val": 31650000000, "accn": "0001193125-25-027207",
                            "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-01-29",
                        },
                    ]
                }
            },
            "Assets": {
                "units": {
                    "USD": [
                        {
                            "end": "2024-12-31",
                            "val": 523013000000, "accn": "0001193125-25-027207",
                            "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-01-29",
                        },
                    ]
                }
            },
            # 8-K entries should be ignored
            "NetIncomeLoss": {
                "units": {
                    "USD": [
                        {
                            "start": "2024-10-01", "end": "2024-12-31",
                            "val": 24108000000, "accn": "0001193125-25-012345",
                            "fy": 2025, "fp": "Q2", "form": "8-K", "filed": "2025-01-29",
                        },
                        {
                            "start": "2024-10-01", "end": "2024-12-31",
                            "val": 24108000000, "accn": "0001193125-25-027207",
                            "fy": 2025, "fp": "Q2", "form": "10-Q", "filed": "2025-01-29",
                        },
                    ]
                }
            },
        }
    }
}


def test_fp_to_quarter() -> None:
    assert _fp_to_quarter("Q1") == 1
    assert _fp_to_quarter("Q3") == 3
    assert _fp_to_quarter("FY") is None
    assert _fp_to_quarter("CY") is None


@patch("backend.parsers.xbrl_parser.fetch_company_facts", return_value=MOCK_FACTS)
def test_parse_extracts_revenue(mock_fetch):
    rows = parse_xbrl_facts("0000789019", company_id=1)
    revenue_rows = [r for r in rows if r["metric_name"] == "revenue"]
    assert len(revenue_rows) == 2
    vals = {r["fiscal_year"]: r["value"] for r in revenue_rows}
    assert vals[2025] == 69632000000.0
    assert vals[2024] == 62020000000.0


@patch("backend.parsers.xbrl_parser.fetch_company_facts", return_value=MOCK_FACTS)
def test_parse_ignores_8k(mock_fetch):
    rows = parse_xbrl_facts("0000789019", company_id=1)
    # net_income only has one valid 10-Q entry (the 8-K entry must be skipped)
    net_income_rows = [r for r in rows if r["metric_name"] == "net_income"]
    assert len(net_income_rows) == 1
    assert net_income_rows[0]["form_type"] == "10-Q"


@patch("backend.parsers.xbrl_parser.fetch_company_facts", return_value=MOCK_FACTS)
def test_parse_links_to_filing_id(mock_fetch):
    acc_map = {"000119312525027207": 42}
    rows = parse_xbrl_facts("0000789019", company_id=1, accession_to_filing_id=acc_map)
    revenue_fy25 = next(r for r in rows if r["metric_name"] == "revenue" and r["fiscal_year"] == 2025)
    assert revenue_fy25["filing_id"] == 42


@patch("backend.parsers.xbrl_parser.fetch_company_facts", return_value=MOCK_FACTS)
def test_parse_stock_metric_has_no_period_start(mock_fetch):
    rows = parse_xbrl_facts("0000789019", company_id=1)
    assets_rows = [r for r in rows if r["metric_name"] == "assets"]
    assert len(assets_rows) == 1
    assert assets_rows[0]["period_start"] is None
    assert assets_rows[0]["value"] == 523013000000.0
