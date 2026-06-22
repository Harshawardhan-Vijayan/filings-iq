"""OpenAI embeddings client."""

from functools import lru_cache

from openai import OpenAI

from backend.config import settings


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is not set — add it to .env")
    return OpenAI(api_key=settings.openai_api_key)


def embed_texts(texts: list[str], batch_size: int = 100) -> list[list[float]]:
    """Embed a list of texts, batching requests to the OpenAI API."""
    if not texts:
        return []

    client = _client()
    out: list[list[float]] = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(model=settings.embedding_model, input=batch)
        # API preserves input order
        out.extend(item.embedding for item in resp.data)
    return out


def embed_query(text: str) -> list[float]:
    """Embed a single query string."""
    return embed_texts([text])[0]
