"""Unit tests for grounded QA: citation validation logic with LLM + retrieval mocked."""

from unittest.mock import patch

from backend.llm.client import LLMResult
from backend.retrieval.search import RetrievedChunk
from backend.schemas.research import ResearchQuery
from backend.workflows.qa import answer_question


def _chunk(cid: int) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=cid,
        filing_id=1,
        ticker="MSFT",
        form_type="10-Q",
        filing_date="2026-04-29",
        fiscal_year=2026,
        fiscal_quarter=3,
        section_key="risk_factors",
        section_title="Risk Factors",
        content=f"Risk content {cid}",
        score=0.9,
    )


def test_no_passages_returns_low_confidence() -> None:
    with patch("backend.workflows.qa.hybrid_search", return_value=[]):
        ans = answer_question(None, ResearchQuery(question="anything", ticker="MSFT"))
    assert ans.confidence == 0.0
    assert ans.supporting_evidence == []
    assert ans.limitations


def test_valid_citations_pass() -> None:
    chunks = [_chunk(10), _chunk(11)]
    llm_json = {
        "answer": "AI poses reputational risk [10].",
        "cited_chunk_ids": [10],
        "confidence": 0.9,
        "limitations": [],
    }
    with (
        patch("backend.workflows.qa.hybrid_search", return_value=chunks),
        patch(
            "backend.workflows.qa.chat_json",
            return_value=(llm_json, LLMResult(content="", prompt_tokens=100, completion_tokens=20)),
        ),
    ):
        ans = answer_question(None, ResearchQuery(question="AI risks?", ticker="MSFT"))

    assert ans.citations_valid is True
    assert len(ans.supporting_evidence) == 1
    assert ans.supporting_evidence[0].chunk_id == 10
    assert ans.tokens_used == 120


def test_hallucinated_citation_flagged() -> None:
    chunks = [_chunk(10)]
    llm_json = {
        "answer": "Made-up claim [999].",
        "cited_chunk_ids": [999],  # not in retrieved set
        "confidence": 0.8,
        "limitations": [],
    }
    with (
        patch("backend.workflows.qa.hybrid_search", return_value=chunks),
        patch(
            "backend.workflows.qa.chat_json",
            return_value=(llm_json, LLMResult(content="")),
        ),
    ):
        ans = answer_question(None, ResearchQuery(question="q", ticker="MSFT"))

    assert ans.citations_valid is False
    assert ans.supporting_evidence == []  # invalid citation produces no evidence
    assert any("could not be validated" in lim for lim in ans.limitations)


def test_no_citations_flagged_invalid() -> None:
    chunks = [_chunk(10)]
    llm_json = {"answer": "Vague.", "cited_chunk_ids": [], "confidence": 0.5, "limitations": []}
    with (
        patch("backend.workflows.qa.hybrid_search", return_value=chunks),
        patch(
            "backend.workflows.qa.chat_json",
            return_value=(llm_json, LLMResult(content="")),
        ),
    ):
        ans = answer_question(None, ResearchQuery(question="q", ticker="MSFT"))
    assert ans.citations_valid is False
