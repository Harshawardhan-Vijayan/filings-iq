# FilingsIQ — Product Requirements

## Overview

FilingsIQ is an evidence-grounded SEC research agent that helps users investigate public companies using their SEC filings. Every answer is backed by a citation to the source filing.

## Target User

Financial analysts and individual investors who need to extract evidence from long financial filings quickly and accurately.

## Problem

Reading and cross-referencing 10-K, 10-Q, and 8-K filings is time-consuming. Analysts spend hours searching for specific facts, comparing periods, and verifying calculations. FilingsIQ reduces this to seconds by combining structured financial data with document retrieval.

## Input / Output

**Input:** Company ticker, time period (optional), research question  
**Output:** Direct answer, supporting evidence with citations, calculations with methodology, uncertainty flags

## Example Questions

- How did Microsoft's cloud revenue change between the last two quarters?
- Which risks were newly added in the latest 10-Q?
- Why did operating margin decline?
- Compare debt, cash flow, and capital expenditure across four quarters.
- Generate a one-page research memo with citations.

## Supported Companies (Phase 1)

| Company         | Ticker |
|-----------------|--------|
| Microsoft       | MSFT   |
| Apple           | AAPL   |
| JPMorgan Chase  | JPM    |
| Goldman Sachs   | GS     |
| Nvidia          | NVDA   |

## Supported Filing Types

- 10-K (annual report)
- 10-Q (quarterly report)
- 8-K (current report / material events)

## Non-Goals

- Stock price prediction
- Personalized investment advice
- Coverage of all public companies (Phase 1)
- Real-time data feeds

## Response Schema

```json
{
  "answer": "Operating margin decreased from 44.1% to 41.8% year-over-year.",
  "supporting_evidence": [
    {
      "filing": "10-Q",
      "filing_date": "2025-10-30",
      "section": "Management Discussion and Analysis",
      "excerpt": "...",
      "source_reference": "msft-20251030.htm#section-mda"
    }
  ],
  "calculations": [
    {
      "label": "Operating margin Q1 FY2025",
      "formula": "operating_income / revenue",
      "inputs": {"operating_income": 30649000000, "revenue": 69632000000},
      "result": 0.4401
    }
  ],
  "confidence": 0.87,
  "limitations": []
}
```

## Success Metrics

| Metric                  | Target (Phase 1) |
|-------------------------|-----------------|
| Answer correctness      | ≥ 85%           |
| Citation correctness    | ≥ 90%           |
| Retrieval recall @ 5    | ≥ 80%           |
| Calculation accuracy    | 100% (deterministic) |
| Task completion rate    | ≥ 80%           |
| P95 latency             | ≤ 10s           |
| Cost per question       | ≤ $0.05         |

## Architecture Principles

1. **Deterministic first**: Python functions calculate all financial ratios. The LLM never does arithmetic.
2. **Evidence-grounded**: Every factual claim in an answer must link to a filing excerpt.
3. **Fail explicitly**: If evidence is insufficient, say so rather than speculating.
4. **Structured + unstructured**: XBRL facts for numbers, document retrieval for narrative.
