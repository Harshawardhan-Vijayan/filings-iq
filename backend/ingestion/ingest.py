"""Filing ingestion pipeline — download and persist SEC filings to the database."""

import json
from datetime import date
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.ingestion.edgar_client import (
    download_filing_document,
    get_company_cik,
    get_company_info,
    list_company_filings,
)
from backend.models.company import Company
from backend.models.filing import Filing
from backend.models.filing_section import FilingSection
from backend.models.financial_fact import FinancialFact
from backend.parsers.section_parser import parse_filing_sections
from backend.parsers.xbrl_parser import parse_xbrl_facts

RAW_DATA_DIR = Path(__file__).parents[2] / "data" / "raw"


def _get_or_create_company(db: Session, ticker: str) -> Company:
    company = db.query(Company).filter_by(ticker=ticker).first()
    if company:
        return company

    cik = get_company_cik(ticker)
    info = get_company_info(cik)

    company = Company(
        ticker=ticker,
        name=info["name"],
        cik=cik,
        sic_code=info.get("sic"),
    )
    db.add(company)
    db.flush()
    return company


def _parse_fiscal_period(report_date: str, form_type: str) -> tuple[int | None, int | None]:
    if not report_date:
        return None, None
    try:
        d = date.fromisoformat(report_date)
    except ValueError:
        return None, None

    fiscal_year = d.year
    if form_type == "10-K":
        return fiscal_year, None

    month = d.month
    quarter = (month - 1) // 3 + 1
    return fiscal_year, quarter


def ingest_filing(db: Session, ticker: str, accession_number: str) -> Filing:
    """Download a single filing and persist it. Returns the Filing record."""
    if ticker not in settings.supported_tickers:
        raise ValueError(f"{ticker} is not a supported ticker")

    existing = db.query(Filing).filter_by(accession_number=accession_number).first()
    if existing:
        return existing

    company = _get_or_create_company(db, ticker)
    filings = list_company_filings(company.cik, max_results=100)
    meta = next((f for f in filings if f["accession_number"] == accession_number), None)
    if not meta:
        raise ValueError(f"Accession number {accession_number} not found for {ticker}")

    fiscal_year, fiscal_quarter = _parse_fiscal_period(meta["report_date"], meta["form_type"])

    acc_dir = RAW_DATA_DIR / ticker / accession_number.replace("-", "")
    acc_dir.mkdir(parents=True, exist_ok=True)

    content = download_filing_document(company.cik, accession_number, meta["primary_document"])
    local_file = acc_dir / meta["primary_document"]
    local_file.write_text(content, encoding="utf-8")

    meta_file = acc_dir / "metadata.json"
    meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    source_url = (
        f"https://www.sec.gov/Archives/edgar/data/{int(company.cik)}/"
        f"{accession_number.replace('-', '')}/{meta['primary_document']}"
    )

    filing = Filing(
        company_id=company.id,
        form_type=meta["form_type"],
        filing_date=date.fromisoformat(meta["filing_date"]),
        period_of_report=date.fromisoformat(meta["report_date"]) if meta["report_date"] else None,
        accession_number=accession_number,
        source_url=source_url,
        local_path=str(local_file),
        fiscal_year=fiscal_year,
        fiscal_quarter=fiscal_quarter,
    )
    db.add(filing)
    db.flush()

    sections = parse_filing_sections(str(local_file), meta["form_type"])
    for s in sections:
        db.add(FilingSection(
            filing_id=filing.id,
            section_key=s.section_key,
            section_title=s.section_title,
            content=s.content,
            sequence=s.sequence,
            word_count=s.word_count,
        ))

    db.commit()
    db.refresh(filing)
    return filing


def ingest_xbrl_facts(db: Session, ticker: str) -> int:
    """Fetch all XBRL facts for a company and upsert into financial_facts. Returns row count."""
    company = db.query(Company).filter_by(ticker=ticker).first()
    if not company:
        raise ValueError(f"Company {ticker} not yet ingested — run ingest_filing first")

    # Build accession → filing_id map for linking facts to filings
    filings = db.query(Filing).filter_by(company_id=company.id).all()
    acc_map = {f.accession_number.replace("-", ""): f.id for f in filings}

    rows = parse_xbrl_facts(company.cik, company.id, acc_map)

    # Delete existing facts for this company before re-inserting
    db.query(FinancialFact).filter_by(company_id=company.id).delete()

    for row in rows:
        db.add(FinancialFact(**row))

    db.commit()
    return len(rows)


def ingest_recent_filings(
    db: Session,
    ticker: str,
    form_types: list[str] | None = None,
    max_filings: int = 5,
) -> list[Filing]:
    """Ingest the most recent N filings for a ticker."""
    if ticker not in settings.supported_tickers:
        raise ValueError(f"{ticker} is not a supported ticker")

    company = _get_or_create_company(db, ticker)
    db.commit()

    recent = list_company_filings(company.cik, form_types=form_types, max_results=max_filings)
    results: list[Filing] = []
    for meta in recent:
        filing = ingest_filing(db, ticker, meta["accession_number"])
        results.append(filing)

    return results
