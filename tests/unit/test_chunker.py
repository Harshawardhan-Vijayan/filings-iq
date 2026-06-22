from backend.retrieval.chunker import chunk_text, count_tokens


def test_empty_text_yields_no_chunks() -> None:
    assert chunk_text("") == []


def test_short_text_single_chunk() -> None:
    chunks = chunk_text("Microsoft cloud revenue grew this quarter.", chunk_tokens=500)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert "Microsoft" in chunks[0].content


def test_long_text_splits_into_multiple_chunks() -> None:
    text = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(text, chunk_tokens=100, overlap_tokens=10)
    assert len(chunks) > 1
    # chunk indices are sequential
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_chunks_respect_token_budget() -> None:
    text = " ".join(f"word{i}" for i in range(2000))
    chunks = chunk_text(text, chunk_tokens=100, overlap_tokens=10)
    for c in chunks:
        assert c.token_count <= 100


def test_overlap_must_be_smaller_than_chunk() -> None:
    import pytest

    with pytest.raises(ValueError):
        chunk_text("some text", chunk_tokens=50, overlap_tokens=50)


def test_count_tokens() -> None:
    assert count_tokens("hello world") > 0
