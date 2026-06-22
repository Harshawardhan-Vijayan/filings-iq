"""Parse SEC XBRL company facts into structured financial metrics."""

from datetime import date
from typing import Any

from backend.ingestion.edgar_client import EDGAR_COMPANY_FACTS, _get

# Maps our stable metric names to preferred XBRL tags (in priority order).
# First tag found with data wins.
METRIC_TAGS: dict[str, list[str]] = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "Revenues",
        "SalesRevenueNet",
    ],
    "operating_income": ["OperatingIncomeLoss"],
    "net_income": ["NetIncomeLoss"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsAndShortTermInvestments"],
    "long_term_debt": ["LongTermDebt", "LongTermDebtNoncurrent"],
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities"],
    "capex": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForCapitalImprovements",
    ],
    "assets": ["Assets"],
    "liabilities": ["Liabilities"],
}

# Only these form types produce reliable period-level data
_VALID_FORMS = {"10-Q", "10-K"}

# fiscal_period string → quarter number (None = annual)
_FP_TO_QUARTER: dict[str, int | None] = {
    "Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4,
    "FY": None, "CY": None,
}


def _fp_to_quarter(fp: str) -> int | None:
    return _FP_TO_QUARTER.get(fp.upper())


def fetch_company_facts(cik: str) -> dict[str, Any]:
    """Fetch raw XBRL company facts JSON from SEC EDGAR."""
    return _get(f"{EDGAR_COMPANY_FACTS}/CIK{cik}.json")


def parse_xbrl_facts(
    cik: str,
    company_id: int,
    accession_to_filing_id: dict[str, int] | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch and parse XBRL facts for a company.

    Returns a list of dicts ready to be inserted as FinancialFact rows.
    accession_to_filing_id maps accession numbers to filing DB IDs for linking.
    """
    data = fetch_company_facts(cik)
    gaap = data.get("facts", {}).get("us-gaap", {})
    if not gaap:
        return []

    acc_map = accession_to_filing_id or {}
    rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()  # (metric_name, period_end, form_type)

    for metric_name, tag_list in METRIC_TAGS.items():
        for tag in tag_list:
            if tag not in gaap:
                continue
            units_dict = gaap[tag].get("units", {})
            usd_entries = units_dict.get("USD", [])
            if not usd_entries:
                continue

            for entry in usd_entries:
                form = entry.get("form", "")
                if form not in _VALID_FORMS:
                    continue

                period_end_str = entry.get("end", "")
                if not period_end_str:
                    continue

                dedup_key = (metric_name, period_end_str, form)
                if dedup_key in seen:
                    continue
                seen.add(dedup_key)

                fp = entry.get("fp", "")
                accn = entry.get("accn", "").replace("-", "")

                rows.append({
                    "company_id": company_id,
                    "filing_id": acc_map.get(accn),
                    "metric_name": metric_name,
                    "xbrl_tag": tag,
                    "value": float(entry["val"]),
                    "unit": "USD",
                    "period_start": date.fromisoformat(entry["start"]) if entry.get("start") else None,
                    "period_end": date.fromisoformat(period_end_str),
                    "fiscal_year": entry.get("fy"),
                    "fiscal_quarter": _fp_to_quarter(fp),
                    "fiscal_period": fp,
                    "form_type": form,
                })
            break  # first tag with data wins for this metric

    return rows
