"""Dataset integrity + pure scoring-logic tests (no LLM, safe for CI)."""

from backend.evaluation.runner import (
    has_number,
    load_dataset,
    looks_like_refusal,
    score_case,
)
from backend.schemas.research import Evidence, ResearchAnswer

VALID_CATEGORIES = {
    "numeric",
    "cross_quarter",
    "document",
    "comparison",
    "mixed",
    "unsupported",
    "insufficient_evidence",
}
KNOWN_TOOLS = {
    "search_filing_sections",
    "get_financial_metric",
    "compare_financial_periods",
    "calculate_financial_ratio",
    "compare_filing_sections",
}


def test_dataset_has_30_questions() -> None:
    assert len(load_dataset()) == 30


def test_dataset_ids_unique() -> None:
    ids = [c["id"] for c in load_dataset()]
    assert len(ids) == len(set(ids))


def test_dataset_categories_and_tools_valid() -> None:
    for c in load_dataset():
        assert c["category"] in VALID_CATEGORIES, c
        for t in c.get("expected_tools", []):
            assert t in KNOWN_TOOLS, t


def test_dataset_covers_all_required_categories() -> None:
    cats = {c["category"] for c in load_dataset()}
    assert VALID_CATEGORIES.issubset(cats)


def test_has_number() -> None:
    assert has_number("Revenue was $241.8B")
    assert has_number("operating margin was 47.4%")
    assert not has_number("Revenue increased significantly")


def test_looks_like_refusal_on_marker() -> None:
    ans = ResearchAnswer(answer="I cannot provide investment advice.", confidence=0.2)
    assert looks_like_refusal(ans)


def test_looks_like_refusal_false_for_real_answer() -> None:
    ans = ResearchAnswer(
        answer="Microsoft revenue was 241.8 billion dollars.",
        confidence=0.95,
        supporting_evidence=[
            Evidence(
                chunk_id=1,
                filing="10-Q",
                filing_date="2026-04-29",
                section="MD&A",
                excerpt="...",
                source_reference="x",
            )
        ],
    )
    assert not looks_like_refusal(ans)


def test_score_numeric_case_pass() -> None:
    case = {
        "id": "n1",
        "category": "numeric",
        "expected_tools": ["calculate_financial_ratio"],
        "requires_numeric_answer": True,
    }
    ans = ResearchAnswer(answer="Operating margin was 47.4%.", confidence=1.0)
    res = score_case(case, ans, tools_called=["calculate_financial_ratio"])
    assert res.passed
    assert res.checks["tool_selection"] and res.checks["numeric_answer"]


def test_score_numeric_case_fails_without_number() -> None:
    case = {"id": "n2", "category": "numeric", "requires_numeric_answer": True}
    ans = ResearchAnswer(answer="It went up.", confidence=0.8)
    res = score_case(case, ans, tools_called=[])
    assert not res.passed


def test_score_citation_case_requires_evidence() -> None:
    case = {
        "id": "d1",
        "category": "document",
        "expected_tools": ["search_filing_sections"],
        "requires_citation": True,
    }
    ans = ResearchAnswer(answer="Risks include AI [5].", confidence=0.9, citations_valid=True)
    # no supporting_evidence attached -> should fail has_citation
    res = score_case(case, ans, tools_called=["search_filing_sections"])
    assert res.checks["has_citation"] is False
    assert not res.passed


def test_score_unsupported_case_expects_refusal() -> None:
    case = {"id": "u1", "category": "unsupported", "expect_refusal": True}
    ans = ResearchAnswer(answer="I cannot predict future stock prices.", confidence=0.1)
    res = score_case(case, ans, tools_called=[])
    assert res.passed
    assert res.checks["declined_appropriately"]
