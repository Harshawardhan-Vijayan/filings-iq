from unittest.mock import MagicMock, patch

from backend.retrieval.embeddings import embed_query, embed_texts


def _mock_response(vectors: list[list[float]]) -> MagicMock:
    resp = MagicMock()
    resp.data = [MagicMock(embedding=v) for v in vectors]
    return resp


def test_embed_texts_empty_returns_empty() -> None:
    assert embed_texts([]) == []


@patch("backend.retrieval.embeddings._client")
def test_embed_texts_preserves_order(mock_client: MagicMock) -> None:
    client = MagicMock()
    client.embeddings.create.return_value = _mock_response([[0.1, 0.2], [0.3, 0.4]])
    mock_client.return_value = client

    result = embed_texts(["a", "b"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]


@patch("backend.retrieval.embeddings._client")
def test_embed_texts_batches(mock_client: MagicMock) -> None:
    client = MagicMock()
    # each call returns one vector per input in that batch
    client.embeddings.create.side_effect = [
        _mock_response([[1.0]]),
        _mock_response([[2.0]]),
        _mock_response([[3.0]]),
    ]
    mock_client.return_value = client

    result = embed_texts(["a", "b", "c"], batch_size=1)
    assert client.embeddings.create.call_count == 3
    assert result == [[1.0], [2.0], [3.0]]


@patch("backend.retrieval.embeddings._client")
def test_embed_query(mock_client: MagicMock) -> None:
    client = MagicMock()
    client.embeddings.create.return_value = _mock_response([[0.5, 0.5]])
    mock_client.return_value = client

    assert embed_query("question") == [0.5, 0.5]
