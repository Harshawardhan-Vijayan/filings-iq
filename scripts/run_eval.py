"""CLI: run the evaluation dataset through the agent and print a report.

Usage:
    python scripts/run_eval.py            # full dataset
    python scripts/run_eval.py --limit 5  # first 5 cases (cheap smoke test)
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from backend.database import SessionLocal
from backend.evaluation.runner import run_evaluation


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = run_evaluation(db, limit=args.limit)
    finally:
        db.close()

    print(f"\n{'=' * 54}")
    print(f"  EVALUATION REPORT — {report.passed}/{report.total} passed ({report.pass_rate:.0%})")
    print(f"{'=' * 54}")
    for cat, stats in sorted(report.by_category.items()):
        print(f"  {cat:<22} {stats['passed']}/{stats['total']}")
    print(f"{'-' * 54}")
    print(f"  total tokens: {report.total_tokens:,}")
    print("\n  Failures:")
    fails = [c for c in report.cases if not c.passed]
    if not fails:
        print("    (none)")
    for c in fails:
        failed_checks = [k for k, v in c.checks.items() if not v]
        print(f"    {c.id} ({c.category}): failed {failed_checks}  tools={c.tools_called}")


if __name__ == "__main__":
    main()
