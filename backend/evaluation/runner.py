"""Evaluation harness: run the agent over the eval dataset and score results.

Scoring is split into pure functions (unit-testable without the LLM) and a
runner that drives the agent and aggregates metrics.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.schemas.research import ResearchAnswer
from backend.workflows.agent import run_agent_with_trace

DATASET_PATH = Path(__file__).parents[2] / "tests" / "evaluation" / "eval_dataset.json"

_REFUSAL_MARKERS = (
    "cannot",
    "can't",
    "unable",
    "not able",
    "do not provide",
    "don't provide",
    "not available",
    "no information",
    "could not find",
    "couldn't find",
    "not disclosed",
    "does not",
    "outside",
    "investment advice",
    "predict",
)


def load_dataset(path: Path = DATASET_PATH) -> list[dict[str, Any]]:
    return json.loads(path.read_text())


def has_number(text: str) -> bool:
    """True if the text contains a numeric figure (digits, %, or $)."""
    return bool(re.search(r"\d", text))


def looks_like_refusal(answer: ResearchAnswer) -> bool:
    """True if the answer declines or flags missing/unsupported information."""
    text = answer.answer.lower()
    if any(m in text for m in _REFUSAL_MARKERS):
        return True
    if answer.confidence <= 0.3:
        return True
    return bool(answer.limitations) and not answer.supporting_evidence


@dataclass
class CaseResult:
    id: str
    category: str
    passed: bool
    checks: dict[str, bool] = field(default_factory=dict)
    tools_called: list[str] = field(default_factory=list)
    tokens: int = 0


def score_case(case: dict[str, Any], answer: ResearchAnswer, tools_called: list[str]) -> CaseResult:
    """Score one case against its expectations. Returns per-check booleans."""
    checks: dict[str, bool] = {}

    expected_tools = set(case.get("expected_tools", []))
    if expected_tools:
        checks["tool_selection"] = bool(expected_tools & set(tools_called))

    if case.get("requires_numeric_answer"):
        checks["numeric_answer"] = has_number(answer.answer)

    if case.get("requires_citation"):
        checks["has_citation"] = len(answer.supporting_evidence) > 0
        checks["citations_valid"] = answer.citations_valid

    if case.get("expect_refusal") or case.get("expect_insufficient"):
        checks["declined_appropriately"] = looks_like_refusal(answer)

    # A case passes only if all of its applicable checks pass.
    passed = all(checks.values()) if checks else bool(answer.answer)
    return CaseResult(
        id=case["id"],
        category=case["category"],
        passed=passed,
        checks=checks,
        tools_called=tools_called,
        tokens=answer.tokens_used,
    )


@dataclass
class EvalReport:
    total: int
    passed: int
    by_category: dict[str, dict[str, int]]
    total_tokens: int
    cases: list[CaseResult]

    @property
    def pass_rate(self) -> float:
        return round(self.passed / self.total, 3) if self.total else 0.0


def run_evaluation(
    db: Session, dataset: list[dict] | None = None, limit: int | None = None
) -> EvalReport:
    cases = dataset if dataset is not None else load_dataset()
    if limit:
        cases = cases[:limit]

    results: list[CaseResult] = []
    by_cat: dict[str, dict[str, int]] = {}

    for case in cases:
        answer, tool_log, _ = run_agent_with_trace(db, case["question"], case.get("ticker"))
        res = score_case(case, answer, tool_log)
        results.append(res)
        cat = by_cat.setdefault(res.category, {"passed": 0, "total": 0})
        cat["total"] += 1
        cat["passed"] += int(res.passed)

    passed = sum(r.passed for r in results)
    return EvalReport(
        total=len(results),
        passed=passed,
        by_category=by_cat,
        total_tokens=sum(r.tokens for r in results),
        cases=results,
    )
