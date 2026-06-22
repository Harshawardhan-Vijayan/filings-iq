"""CLI: ingest recent filings for a ticker.

Usage:
    python scripts/ingest.py MSFT
    python scripts/ingest.py MSFT --form-type 10-K --max 1
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.database import SessionLocal
from backend.ingestion.ingest import ingest_recent_filings


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest SEC filings for a ticker")
    parser.add_argument("ticker", help="Ticker symbol, e.g. MSFT")
    parser.add_argument("--form-type", default="10-Q", help="Form type (default: 10-Q)")
    parser.add_argument(
        "--max", type=int, default=3, dest="max_filings", help="Max filings to ingest"
    )
    args = parser.parse_args()

    print(f"Ingesting {args.max_filings}x {args.form_type} for {args.ticker.upper()} ...")
    db = SessionLocal()
    try:
        filings = ingest_recent_filings(
            db,
            args.ticker.upper(),
            form_types=[args.form_type],
            max_filings=args.max_filings,
        )
        for f in filings:
            print(f"  ✓ {f.form_type} {f.filing_date} — {f.accession_number}")
            print(f"    saved to: {f.local_path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
