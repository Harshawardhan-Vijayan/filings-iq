"""Unit tests for agent routing, tool dispatch, and tool accumulation (LLM-free)."""

from unittest.mock import MagicMock, patch

from backend.retrieval.search import RetrievedChunk
from backend.workflows.agent import _route_after_agent, tools_node


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
        content="risk text",
        score=0.9,
    )


def test_route_to_tools_when_tool_calls_present() -> None:
    state = {
        "messages": [{"role": "assistant", "tool_calls": [{"id": "1"}]}],
        "n_tool_calls": 0,
    }
    assert _route_after_agent(state) == "tools"


def test_route_to_finalize_when_no_tool_calls() -> None:
    state = {"messages": [{"role": "assistant", "content": "done"}], "n_tool_calls": 0}
    assert _route_after_agent(state) == "finalize"


def test_route_to_finalize_when_tool_budget_exhausted() -> None:
    from backend.config import settings

    state = {
        "messages": [{"role": "assistant", "tool_calls": [{"id": "1"}]}],
        "n_tool_calls": settings.max_tool_calls,
    }
    assert _route_after_agent(state) == "finalize"


@patch("backend.workflows.agent.execute_tool")
def test_tools_node_accumulates_evidence(mock_exec: MagicMock) -> None:
    from backend.tools.registry import ToolOutcome

    mock_exec.return_value = ToolOutcome(
        result=[{"chunk_id": 5}], evidence=[_chunk(5)], calculation=None
    )
    state = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "call_1",
                        "function": {
                            "name": "search_filing_sections",
                            "arguments": '{"query":"x","ticker":"MSFT"}',
                        },
                    }
                ],
            }
        ],
        "evidence": {},
        "calculations": [],
        "tool_log": [],
        "n_tool_calls": 0,
    }
    out = tools_node(state, db=None)
    assert 5 in out["evidence"]
    assert out["tool_log"] == ["search_filing_sections"]
    assert out["n_tool_calls"] == 1
    # a tool-result message was appended for the model to read
    assert out["messages"][-1]["role"] == "tool"
    assert out["messages"][-1]["tool_call_id"] == "call_1"


@patch("backend.workflows.agent.execute_tool", side_effect=ValueError("boom"))
def test_tools_node_surfaces_errors(mock_exec: MagicMock) -> None:
    state = {
        "messages": [
            {
                "role": "assistant",
                "tool_calls": [
                    {"id": "c1", "function": {"name": "get_financial_metric", "arguments": "{}"}}
                ],
            }
        ],
        "evidence": {},
        "calculations": [],
        "tool_log": [],
        "n_tool_calls": 0,
    }
    out = tools_node(state, db=None)
    assert "boom" in out["messages"][-1]["content"]
    # the loop still advances so the agent can react to the error
    assert out["n_tool_calls"] == 1
