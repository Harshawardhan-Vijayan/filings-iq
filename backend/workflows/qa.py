"""Day 10: grounded question answering.

Retrieve passages, ask the LLM to answer using ONLY those passages, and require
every claim to cite a passage by id. Citations are then validated against the
retrieved set so the model can't invent sources.
"""

from sqlalchemy.orm import Session

from backend.llm.client import chat_json
from backend.retrieval.search import RetrievedChunk, hybrid_search
from backend.schemas.research import Evidence, ResearchAnswer, ResearchQuery

_SYSTEM = """You are a financial research assistant. Answer the user's question using ONLY the \
numbered passages provided. Every factual claim in your answer must be supported by at least \
one passage, cited inline as [chunk_id].

Rules:
- Do NOT use outside knowledge. If the passages do not answer the question, say so.
- Do NOT compute financial ratios yourself; only state figures that appear in the passages.
- Be concise and specific.

Return a JSON object with exactly these keys:
{
  "answer": "<answer text with inline [chunk_id] citations>",
  "cited_chunk_ids": [<int>, ...],
  "confidence": <float 0-1>,
  "limitations": ["<caveat>", ...]
}"""


def _format_passages(chunks: list[RetrievedChunk]) -> str:
    blocks = []
    for c in chunks:
        header = f"[{c.chunk_id}] {c.ticker} {c.form_type} {c.filing_date} — {c.section_title}"
        blocks.append(f"{header}\n{c.content}")
    return "\n\n".join(blocks)


def _to_evidence(chunk: RetrievedChunk) -> Evidence:
    excerpt = chunk.content.strip()
    if len(excerpt) > 600:
        excerpt = excerpt[:600].rstrip() + "…"
    return Evidence(
        chunk_id=chunk.chunk_id,
        filing=chunk.form_type,
        filing_date=chunk.filing_date,
        section=chunk.section_title,
        excerpt=excerpt,
        source_reference=f"{chunk.ticker}/{chunk.form_type}/{chunk.filing_date}#chunk-{chunk.chunk_id}",
    )


def answer_question(db: Session, query: ResearchQuery) -> ResearchAnswer:
    chunks = hybrid_search(
        db,
        query.question,
        ticker=query.ticker,
        section_key=query.section_key,
        fiscal_year=query.fiscal_year,
        top_k=query.top_k,
    )

    if not chunks:
        return ResearchAnswer(
            answer="I could not find any filing passages relevant to this question.",
            confidence=0.0,
            limitations=["No matching passages were retrieved for the given filters."],
        )

    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": f"Question: {query.question}\n\nPassages:\n{_format_passages(chunks)}",
        },
    ]
    parsed, result = chat_json(messages)

    by_id = {c.chunk_id: c for c in chunks}
    cited_ids = [cid for cid in parsed.get("cited_chunk_ids", []) if cid in by_id]
    # Citations are valid if the model cited at least one real passage and invented none.
    raw_cited = parsed.get("cited_chunk_ids", [])
    citations_valid = bool(raw_cited) and all(cid in by_id for cid in raw_cited)

    evidence = [_to_evidence(by_id[cid]) for cid in cited_ids]
    limitations = list(parsed.get("limitations", []))
    if not citations_valid:
        limitations.append("Some citations could not be validated against retrieved passages.")

    return ResearchAnswer(
        answer=parsed.get("answer", "").strip() or "No answer was generated.",
        supporting_evidence=evidence,
        confidence=float(parsed.get("confidence", 0.0)),
        limitations=limitations,
        tokens_used=result.total_tokens,
        citations_valid=citations_valid,
    )
