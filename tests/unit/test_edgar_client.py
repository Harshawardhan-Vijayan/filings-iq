from unittest.mock import MagicMock, patch

import pytest

from backend.ingestion.edgar_client import get_company_cik, list_company_filings


MOCK_TICKERS = {
    "0": {"cik_str": 789019, "ticker": "MSFT", "title": "MICROSOFT CORP"},
    "1": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
}

MOCK_SUBMISSIONS = {
    "name": "MICROSOFT CORP",
    "sic": "7372",
    "filings": {
        "recent": {
            "accessionNumber": ["0001564590-24-000001", "0001564590-24-000002"],
            "form": ["10-Q", "10-K"],
            "filingDate": ["2024-10-30", "2024-07-30"],
            "reportDate": ["2024-09-30", "2024-06-30"],
            "primaryDocument": ["msft-20240930.htm", "msft-20240630.htm"],
        }
    },
}


@patch("backend.ingestion.edgar_client._get")
def test_get_company_cik_msft(mock_get: MagicMock) -> None:
    mock_get.return_value = MOCK_TICKERS
    cik = get_company_cik("MSFT")
    assert cik == "0000789019"


@patch("backend.ingestion.edgar_client._get")
def test_get_company_cik_case_insensitive(mock_get: MagicMock) -> None:
    mock_get.return_value = MOCK_TICKERS
    cik = get_company_cik("msft")
    assert cik == "0000789019"


@patch("backend.ingestion.edgar_client._get")
def test_get_company_cik_unknown_raises(mock_get: MagicMock) -> None:
    mock_get.return_value = MOCK_TICKERS
    with pytest.raises(ValueError, match="UNKNOWN"):
        get_company_cik("UNKNOWN")


@patch("backend.ingestion.edgar_client._get")
def test_list_company_filings_filters_by_form_type(mock_get: MagicMock) -> None:
    mock_get.return_value = MOCK_SUBMISSIONS
    filings = list_company_filings("0000789019", form_types=["10-Q"])
    assert len(filings) == 1
    assert filings[0]["form_type"] == "10-Q"
    assert filings[0]["accession_number"] == "0001564590-24-000001"


@patch("backend.ingestion.edgar_client._get")
def test_list_company_filings_max_results(mock_get: MagicMock) -> None:
    mock_get.return_value = MOCK_SUBMISSIONS
    filings = list_company_filings("0000789019", form_types=["10-Q", "10-K"], max_results=1)
    assert len(filings) == 1
