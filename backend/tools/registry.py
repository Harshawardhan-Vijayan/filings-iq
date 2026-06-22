"""Tool registry for the research agent.

Each tool wraps a deterministic Python function from earlier days and exposes an
OpenAI tool-calling schema. execute_tool dispatches a call and returns a
JSON-serializable result plus any evidence chunks it surfaced.
"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from backend.models.filing import Filing
from backend.retrieval.search import RetrievedChunk, hybrid_search
from backend.tools.calculations import (
    calculate_debt_to_assets,
    calculate_free_cash_flow,
    calculate_net_margin,
    calculate_operating_margin,
)
from backend.tools.metrics import compare_metric_periods, get_financial_metric
from backend.workflows.comparison import compare_sections

_RATIO_FUNCS = {
    "operating_margin": (calculate_operating_margin, ["operating_income", "revenue"]),
    "net_margin": (calculate_net_margin, ["net_income", "revenue"]),
    "free_cash_flow": (calculate_free_cash_flow, ["operating_cash_flow", "capex"]),
    "debt_to_assets": (calculate_debt_to_assets, ["long_term_debt", "assets"]),
}


@dataclass
class ToolOutcome:
    result: Any
    evidence: list[RetrievedChunk] = field(default_factory=list)
    calculation: dict | None = None


# ---- OpenAI tool schemas ----------------------------------------------------

TOOL_SCHEMAS: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "search_filing_sections",
            "description": "Semantic + keyword search over filing text. Use for qualitative "
            "questions about risks, strategy, MD&A narrative, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "ticker": {"type": "string"},
                    "section_key": {
                        "type": "string",
                        "description": "Optional filter, e.g. risk_factors, mda, business",
                    },
                    "top_k": {"type": "integer", "default": 5},
                },
                "required": ["query", "ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_financial_metric",
            "description": "Get a single reported financial metric (revenue, operating_income, "
            "net_income, cash, long_term_debt, operating_cash_flow, capex, "
            "assets, liabilities). Latest period if year/quarter omitted.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "metric_name": {"type": "string"},
                    "fiscal_year": {"type": "integer"},
                    "fiscal_quarter": {"type": "integer"},
                },
                "required": ["ticker", "metric_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_financial_periods",
            "description": "Compare one metric across two periods and get the growth rate.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "metric_name": {"type": "string"},
                    "current_year": {"type": "integer"},
                    "current_quarter": {"type": "integer"},
                    "prior_year": {"type": "integer"},
                    "prior_quarter": {"type": "integer"},
                },
                "required": ["ticker", "metric_name", "current_year", "prior_year"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_financial_ratio",
            "description": "Compute a ratio deterministically: operating_margin, net_margin, "
            "free_cash_flow, or debt_to_assets.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ratio_name": {"type": "string"},
                    "ticker": {"type": "string"},
                    "fiscal_year": {"type": "integer"},
                    "fiscal_quarter": {"type": "integer"},
                },
                "required": ["ratio_name", "ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "compare_filing_sections",
            "description": "Diff a section (e.g. risk_factors) between the two most recent "
            "filings of a ticker to find what changed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "section_key": {"type": "string", "default": "risk_factors"},
                },
                "required": ["ticker"],
            },
        },
    },
]


# ---- dispatch ---------------------------------------------------------------


def _two_recent_filings(db: Session, ticker: str) -> tuple[Filing, Filing]:
    filings = (
        db.query(Filing)
        .join(Filing.company)
        .filter_by(ticker=ticker.upper())
        .order_by(Filing.filing_date.desc())
        .limit(2)
        .all()
    )
    if len(filings) < 2:
        raise ValueError(f"Need at least two filings for {ticker} to compare")
    return filings[0], filings[1]


def execute_tool(db: Session, name: str, args: dict) -> ToolOutcome:
    if name == "search_filing_sections":
        chunks = hybrid_search(
            db,
            args["query"],
            ticker=args.get("ticker"),
            section_key=args.get("section_key"),
            top_k=args.get("top_k", 5),
        )
        result = [
            {
                "chunk_id": c.chunk_id,
                "section": c.section_title,
                "filing": c.form_type,
                "filing_date": c.filing_date,
                "text": c.content,
            }
            for c in chunks
        ]
        return ToolOutcome(result=result, evidence=chunks)

    if name == "get_financial_metric":
        mv = get_financial_metric(
            db,
            args["ticker"],
            args["metric_name"],
            args.get("fiscal_year"),
            args.get("fiscal_quarter"),
        )
        return ToolOutcome(result=mv.model_dump())

    if name == "compare_financial_periods":
        comp = compare_metric_periods(
            db,
            args["ticker"],
            args["metric_name"],
            args["current_year"],
            args.get("current_quarter"),
            args["prior_year"],
            args.get("prior_quarter"),
        )
        return ToolOutcome(result=comp.model_dump(), calculation=comp.growth.model_dump())

    if name == "calculate_financial_ratio":
        ratio = args["ratio_name"]
        if ratio not in _RATIO_FUNCS:
            raise ValueError(f"Unknown ratio '{ratio}'")
        func, required = _RATIO_FUNCS[ratio]
        values = [
            get_financial_metric(
                db, args["ticker"], m, args.get("fiscal_year"), args.get("fiscal_quarter")
            ).value
            for m in required
        ]
        calc = func(*values)
        return ToolOutcome(result=calc.model_dump(), calculation=calc.model_dump())

    if name == "compare_filing_sections":
        current, prior = _two_recent_filings(db, args["ticker"])
        comp = compare_sections(
            db,
            current.id,
            prior.id,
            args.get("section_key", "risk_factors"),
        )
        result = {
            "section": comp.section_title,
            "current": comp.current_label,
            "prior": comp.prior_label,
            "added": comp.added[:10],
            "removed": comp.removed[:10],
            "modified": [{"old": m.old, "new": m.new} for m in comp.modified[:10]],
            "summary": comp.summary,
        }
        return ToolOutcome(result=result)

    raise ValueError(f"Unknown tool '{name}'")
