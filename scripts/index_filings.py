"""CLI: chunk + embed + store filing sections into pgvector.

Usage:
    python scripts/index_filings.py            # index all filings
    python scripts/index_filings.py MSFT       # index one ticker
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.database import SessionLocal
from backend.retrieval.index import index_all_filings


def main() -> None:
    ticker = sys.argv[1].upper() if len(sys.argv) > 1 else None
    label = ticker or "ALL companies"
    print(f"Indexing filings for {label} ...")

    db = SessionLocal()
    try:
        total = index_all_filings(db, ticker)
        print(f"  ✓ created {total} embedded chunks")
    finally:
        db.close()


if __name__ == "__main__":
    main()
