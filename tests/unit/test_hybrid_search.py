"""Unit tests for RRF fusion in hybrid_search, with vector/fulltext mocked."""

from unittest.mock import patch

from backend.retrieval.search import RetrievedChunk, hybrid_search


def _chunk(chunk_id: int, score: float = 0.5) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        filing_id=1,
        ticker="MSFT",
        form_type="10-Q",
        filing_date="2026-03-31",
        fiscal_year=2026,
        fiscal_quarter=3,
        section_key="risk_factors",
        section_title="Risk Factors",
        content=f"chunk {chunk_id}",
        score=score,
    )


@patch("backend.retrieval.search.fulltext_search")
@patch("backend.retrieval.search.vector_search")
def test_rrf_rewards_agreement(mock_vec, mock_fts) -> None:
    # Chunk 1 ranks #1 in both lists -> should win.
    mock_vec.return_value = [_chunk(1), _chunk(2), _chunk(3)]
    mock_fts.return_value = [_chunk(1), _chunk(4), _chunk(5)]

    results = hybrid_search(None, "ai risk", top_k=3)
    assert results[0].chunk_id == 1


@patch("backend.retrieval.search.fulltext_search")
@patch("backend.retrieval.search.vector_search")
def test_rrf_unions_both_sources(mock_vec, mock_fts) -> None:
    # Vector-only and fulltext-only chunks should both appear in the union.
    mock_vec.return_value = [_chunk(1)]
    mock_fts.return_value = [_chunk(2)]

    results = hybrid_search(None, "q", top_k=5)
    ids = {r.chunk_id for r in results}
    assert ids == {1, 2}


@patch("backend.retrieval.search.fulltext_search")
@patch("backend.retrieval.search.vector_search")
def test_rrf_respects_top_k(mock_vec, mock_fts) -> None:
    mock_vec.return_value = [_chunk(i) for i in range(1, 11)]
    mock_fts.return_value = [_chunk(i) for i in range(11, 21)]

    results = hybrid_search(None, "q", top_k=4)
    assert len(results) == 4


@patch("backend.retrieval.search.fulltext_search")
@patch("backend.retrieval.search.vector_search")
def test_rrf_score_is_set(mock_vec, mock_fts) -> None:
    mock_vec.return_value = [_chunk(1)]
    mock_fts.return_value = [_chunk(1)]

    results = hybrid_search(None, "q", top_k=1, rrf_k=60)
    # appears at rank 1 in both -> 2 * 1/(60+1)
    assert results[0].score == round(2 / 61, 6)
