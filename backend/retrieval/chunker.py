"""Token-based chunking of filing sections for embedding."""

from dataclasses import dataclass

import tiktoken

from backend.config import settings

# text-embedding-3-* uses the cl100k_base encoding
_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    chunk_index: int
    content: str
    token_count: int


def chunk_text(
    text: str,
    chunk_tokens: int | None = None,
    overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Split text into overlapping token windows.

    Overlap preserves context across chunk boundaries so a sentence split in two
    still retrieves coherently.
    """
    chunk_tokens = chunk_tokens or settings.chunk_tokens
    overlap_tokens = overlap_tokens or settings.chunk_overlap_tokens
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be smaller than chunk_tokens")

    tokens = _ENCODING.encode(text)
    if not tokens:
        return []

    step = chunk_tokens - overlap_tokens
    chunks: list[Chunk] = []
    idx = 0
    for start in range(0, len(tokens), step):
        window = tokens[start : start + chunk_tokens]
        if not window:
            break
        content = _ENCODING.decode(window).strip()
        if content:
            chunks.append(Chunk(chunk_index=idx, content=content, token_count=len(window)))
            idx += 1
        if start + chunk_tokens >= len(tokens):
            break

    return chunks


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))
