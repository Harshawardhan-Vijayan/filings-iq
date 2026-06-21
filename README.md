# FilingsIQ

Evidence-grounded SEC research agent. Ask questions about public company filings; get answers backed by citations.

## Quick Start

```bash
cp .env.example .env
# fill in OPENAI_API_KEY

docker compose up -d db
source .venv/bin/activate  # or: python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
alembic upgrade head
uvicorn backend.api.main:app --reload
```

Visit `http://localhost:8000/health` to verify the service is running.

## Supported Companies (Phase 1)

MSFT · AAPL · JPM · GS · NVDA

## Development

```bash
pytest tests/unit          # fast unit tests (no DB required)
pytest tests/integration   # requires running PostgreSQL
ruff check backend tests
ruff format backend tests
mypy backend
```

## Architecture

```
SEC EDGAR → Ingestion → PostgreSQL + pgvector → FastAPI → LangGraph agent → React/Next.js
```

See [docs/product-requirements.md](docs/product-requirements.md) for full specs.
