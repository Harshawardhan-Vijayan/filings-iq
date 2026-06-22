"""Day 12: the research orchestrator.

A single LangGraph workflow:

    classify -> agent (tool-calling loop) -> finalize (validate citations)

One graph, real tools, bounded loop. Numeric work goes to deterministic tools;
qualitative work goes to retrieval. The final answer must cite retrieved
passages, and citations are validated against what was actually retrieved.
"""

import json
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph
from sqlalchemy.orm import Session

from backend.config import settings
from backend.retrieval.embeddings import _client
from backend.retrieval.search import RetrievedChunk
from backend.schemas.research import Evidence, ResearchAnswer
from backend.tools.registry import TOOL_SCHEMAS, execute_tool

_CLASSIFY_SYSTEM = """Classify a financial research question into one of:
- "financial": needs reported numbers or ratios (revenue, margin, growth, cash flow)
- "document": needs qualitative filing text (risks, strategy, MD&A narrative)
- "comparison": asks what changed between periods/filings
- "mixed": needs both numbers and text
Return JSON: {"classification": "...", "ticker": "<TICKER or null>"}"""

_AGENT_SYSTEM = """You are FilingsIQ, a financial research agent. Answer using the provided \
tools only. Never compute ratios yourself — call calculate_financial_ratio. Never state numbers \
not returned by a tool. For qualitative claims, call search_filing_sections and cite the \
returned chunk_id values. Call tools until you have enough evidence, then stop.

Scope (these are non-goals — do not attempt them):
- Do NOT give investment advice or buy/sell/hold recommendations. Decline and explain you \
report filing evidence only.
- Do NOT predict future prices or results.
- If the filings do not contain the requested information, say so explicitly rather than \
guessing or substituting loosely related content."""

_FINALIZE_SYSTEM = """Produce the final answer as JSON with these keys:
{
  "answer": "<concise answer with inline [chunk_id] citations for qualitative claims>",
  "cited_chunk_ids": [<int>, ...],
  "confidence": <float 0-1>,
  "limitations": ["<caveat>", ...]
}
Only cite chunk_ids that appeared in tool results. If evidence is insufficient, say so plainly \
and set a low confidence. For investment-advice or prediction requests, decline in the answer \
and set confidence to 0."""


class AgentState(TypedDict, total=False):
    question: str
    ticker: str | None
    classification: str
    messages: list[dict[str, Any]]
    evidence: dict[int, RetrievedChunk]
    calculations: list[dict]
    tool_log: list[str]
    n_tool_calls: int
    tokens_used: int
    answer: ResearchAnswer


def _llm():
    return _client()


def classify_node(state: AgentState, db: Session) -> AgentState:
    resp = _llm().chat.completions.create(
        model=settings.llm_model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": _CLASSIFY_SYSTEM},
            {"role": "user", "content": state["question"]},
        ],
    )
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {}

    classification = parsed.get("classification", "mixed")
    ticker = state.get("ticker") or parsed.get("ticker")

    state["classification"] = classification
    state["ticker"] = ticker
    state["tokens_used"] = state.get("tokens_used", 0) + (
        resp.usage.total_tokens if resp.usage else 0
    )
    state["messages"] = [
        {"role": "system", "content": _AGENT_SYSTEM},
        {
            "role": "user",
            "content": f"Question ({classification}): {state['question']}"
            + (f"\nTicker: {ticker}" if ticker else ""),
        },
    ]
    state["evidence"] = {}
    state["calculations"] = []
    state["tool_log"] = []
    state["n_tool_calls"] = 0
    return state


def agent_node(state: AgentState, db: Session) -> AgentState:
    resp = _llm().chat.completions.create(
        model=settings.llm_model,
        temperature=0.0,
        tools=TOOL_SCHEMAS,
        tool_choice="auto",
        messages=state["messages"],
    )
    msg = resp.choices[0].message
    state["tokens_used"] += resp.usage.total_tokens if resp.usage else 0

    # Append the assistant message (with tool calls) back to history
    assistant_msg: dict[str, Any] = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        assistant_msg["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]
    state["messages"].append(assistant_msg)
    return state


def tools_node(state: AgentState, db: Session) -> AgentState:
    last = state["messages"][-1]
    for tc in last.get("tool_calls", []):
        name = tc["function"]["name"]
        try:
            args = json.loads(tc["function"]["arguments"] or "{}")
        except json.JSONDecodeError:
            args = {}
        try:
            outcome = execute_tool(db, name, args)
            content = json.dumps(outcome.result, default=str)
            for chunk in outcome.evidence:
                state["evidence"][chunk.chunk_id] = chunk
            if outcome.calculation:
                state["calculations"].append(outcome.calculation)
        except Exception as e:  # surface tool errors back to the model
            content = json.dumps({"error": str(e)})

        state["tool_log"].append(name)
        state["n_tool_calls"] += 1
        state["messages"].append(
            {
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": content,
            }
        )
    return state


def _route_after_agent(state: AgentState) -> str:
    last = state["messages"][-1]
    if last.get("tool_calls") and state["n_tool_calls"] < settings.max_tool_calls:
        return "tools"
    return "finalize"


def finalize_node(state: AgentState, db: Session) -> AgentState:
    messages = state["messages"] + [{"role": "system", "content": _FINALIZE_SYSTEM}]
    resp = _llm().chat.completions.create(
        model=settings.llm_model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=messages,
    )
    state["tokens_used"] += resp.usage.total_tokens if resp.usage else 0
    try:
        parsed = json.loads(resp.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        parsed = {}

    evidence_pool = state["evidence"]
    raw_cited = parsed.get("cited_chunk_ids", [])
    valid_cited = [cid for cid in raw_cited if cid in evidence_pool]
    # Valid if every cited id is real. (Pure-numeric answers may legitimately cite nothing.)
    citations_valid = all(cid in evidence_pool for cid in raw_cited)

    supporting = []
    for cid in valid_cited:
        c = evidence_pool[cid]
        excerpt = c.content.strip()
        if len(excerpt) > 600:
            excerpt = excerpt[:600].rstrip() + "…"
        supporting.append(
            Evidence(
                chunk_id=cid,
                filing=c.form_type,
                filing_date=c.filing_date,
                section=c.section_title,
                excerpt=excerpt,
                source_reference=f"{c.ticker}/{c.form_type}/{c.filing_date}#chunk-{cid}",
            )
        )

    limitations = list(parsed.get("limitations", []))
    if not citations_valid:
        limitations.append("Some citations could not be validated against retrieved passages.")

    from backend.schemas.calculation import CalculationResult

    calcs = [CalculationResult(**c) for c in state["calculations"] if "formula" in c]

    state["answer"] = ResearchAnswer(
        answer=parsed.get("answer", "").strip() or "No answer was generated.",
        supporting_evidence=supporting,
        calculations=calcs,
        confidence=float(parsed.get("confidence", 0.0)),
        limitations=limitations,
        tokens_used=state["tokens_used"],
        citations_valid=citations_valid,
    )
    return state


def build_graph(db: Session):
    """Construct the orchestrator graph. db is bound into each node."""
    g = StateGraph(AgentState)
    g.add_node("classify", lambda s: classify_node(s, db))
    g.add_node("agent", lambda s: agent_node(s, db))
    g.add_node("tools", lambda s: tools_node(s, db))
    g.add_node("finalize", lambda s: finalize_node(s, db))

    g.set_entry_point("classify")
    g.add_edge("classify", "agent")
    g.add_conditional_edges("agent", _route_after_agent, {"tools": "tools", "finalize": "finalize"})
    g.add_edge("tools", "agent")
    g.add_edge("finalize", END)
    return g.compile()


def run_agent_with_trace(
    db: Session, question: str, ticker: str | None = None
) -> tuple[ResearchAnswer, list[str], str]:
    """Run the agent and also return the tool-call log and classification (for eval)."""
    graph = build_graph(db)
    final = graph.invoke(
        {"question": question, "ticker": ticker},
        config={"recursion_limit": 2 * settings.max_tool_calls + 5},
    )
    return final["answer"], final.get("tool_log", []), final.get("classification", "")


def run_agent(db: Session, question: str, ticker: str | None = None) -> ResearchAnswer:
    answer, _, _ = run_agent_with_trace(db, question, ticker)
    return answer
