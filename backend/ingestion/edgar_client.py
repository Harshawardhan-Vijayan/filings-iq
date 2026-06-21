"""SEC EDGAR HTTP client with rate limiting (10 req/s per EDGAR guidelines)."""

import time
from typing import Any

import httpx

from backend.config import settings

EDGAR_BASE = "https://www.sec.gov"
EDGAR_SUBMISSIONS = "https://data.sec.gov/submissions"
EDGAR_COMPANY_FACTS = "https://data.sec.gov/api/xbrl/companyfacts"

# EDGAR allows max 10 requests/second
_MIN_INTERVAL = 0.11
_last_request_time: float = 0.0


def _get(url: str) -> dict[str, Any]:
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    headers = {"User-Agent": settings.sec_user_agent, "Accept": "application/json"}
    response = httpx.get(url, headers=headers, timeout=30)
    response.raise_for_status()
    _last_request_time = time.monotonic()
    return response.json()  # type: ignore[no-any-return]


def get_company_cik(ticker: str) -> str:
    """Return zero-padded 10-digit CIK for a ticker symbol."""
    data = _get(f"{EDGAR_BASE}/files/company_tickers.json")
    ticker_upper = ticker.upper()
    for entry in data.values():
        if entry["ticker"] == ticker_upper:
            return str(entry["cik_str"]).zfill(10)
    raise ValueError(f"Ticker {ticker!r} not found in EDGAR company list")


def get_company_info(cik: str) -> dict[str, Any]:
    """Return company submission metadata from EDGAR."""
    return _get(f"{EDGAR_SUBMISSIONS}/CIK{cik}.json")


def list_company_filings(
    cik: str,
    form_types: list[str] | None = None,
    max_results: int = 20,
) -> list[dict[str, Any]]:
    """Return recent filings for a company, optionally filtered by form type."""
    if form_types is None:
        form_types = ["10-K", "10-Q", "8-K"]

    data = get_company_info(cik)
    recent = data["filings"]["recent"]

    filings: list[dict[str, Any]] = []
    for i, form in enumerate(recent["form"]):
        if form not in form_types:
            continue
        filings.append(
            {
                "accession_number": recent["accessionNumber"][i],
                "form_type": form,
                "filing_date": recent["filingDate"][i],
                "report_date": recent["reportDate"][i],
                "primary_document": recent["primaryDocument"][i],
                "company_name": data["name"],
                "cik": cik,
            }
        )
        if len(filings) >= max_results:
            break

    return filings


def get_filing_index_url(cik: str, accession_number: str) -> str:
    """Return the EDGAR filing index URL for a given accession number."""
    acc_no_clean = accession_number.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_clean}/{accession_number}-index.htm"


def download_filing_document(cik: str, accession_number: str, filename: str) -> str:
    """Download the primary filing document and return its text content."""
    acc_no_clean = accession_number.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{acc_no_clean}/{filename}"

    elapsed = time.monotonic() - _last_request_time
    if elapsed < _MIN_INTERVAL:
        time.sleep(_MIN_INTERVAL - elapsed)

    headers = {"User-Agent": settings.sec_user_agent}
    response = httpx.get(url, headers=headers, timeout=60, follow_redirects=True)
    response.raise_for_status()
    return response.text
