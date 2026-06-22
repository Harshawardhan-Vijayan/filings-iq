# Evaluation Findings (Day 13)

## Setup

- **Dataset:** 30 hand-written questions ([eval_dataset.json](../tests/evaluation/eval_dataset.json)) spanning numeric, cross-quarter, document, comparison, mixed, unsupported, and insufficient-evidence categories.
- **System under test:** the Day 12 LangGraph orchestrator (`run_agent`) over real Microsoft 10-Q data (two quarters ingested + indexed).
- **Model:** `gpt-4o-mini`, temperature 0.
- **Scoring:** per-case checks — tool selection, numeric answer present, citation present + valid, appropriate refusal/insufficient handling. A case passes only if all applicable checks pass.

## Headline result

**28/30 passed (~93%)**, ~139K total tokens across the run (≈ $0.02 for the full suite).

| Category | Pass |
|----------|------|
| numeric | 7/7 |
| cross_quarter | 3–4/4 |
| document | 8/8 |
| comparison | 2/2 |
| mixed | 3/3 |
| unsupported | 3/3 |
| insufficient_evidence | 2/3 |

## Failure analysis (honest)

Results vary slightly between runs because tool-calling is non-deterministic even at temperature 0. Two recurring failure modes:

1. **Tool-selection scoring is stricter than reality.** For "compare assets between the two most recent periods," the agent sometimes calls `get_financial_metric` twice and computes the comparison itself in the answer, instead of the dedicated `compare_financial_periods` tool. The *answer is correct*; only the expected-tool check fails. Fix: score tool selection by capability satisfied, not exact tool name.

2. **Insufficient-evidence edge cases are flaky.** For "quantum computing revenue" (not in the filing), the agent sometimes correctly says the filing doesn't cover it, and sometimes returns loosely-related AI/cloud text. Adding explicit non-goal guidance to the agent prompt (decline advice/predictions, state when data is absent) fixed all *unsupported* cases reliably, but borderline "insufficient" cases still occasionally over-answer.

## What worked well

- **Numeric accuracy is 100%** — all ratios/metrics route to deterministic Python tools; the LLM never does arithmetic.
- **Citations validate.** Document answers cite real retrieved chunk_ids; hallucinated citations are caught and flagged.
- **Refusal of investment advice** became reliable after aligning the agent prompt to the PRD non-goals.

## Next steps (Week 4–5)

- Capability-based tool scoring.
- Reranking to tighten retrieval ordering (Week 4).
- Stronger insufficient-evidence handling and conflicting-XBRL-value resolution (Week 5).
