import time

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes.filings import router as filings_router
from backend.api.routes.metrics import router as metrics_router
from backend.api.routes.search import router as search_router
from backend.config import settings
from backend.database import check_db_connection

app = FastAPI(
    title="FilingsIQ",
    description="Evidence-grounded SEC research agent",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(filings_router)
app.include_router(metrics_router)
app.include_router(search_router)

_start_time = time.time()


@app.get("/health")
def health() -> dict:
    db_ok = check_db_connection()
    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "unavailable",
        "environment": settings.environment,
        "uptime_seconds": round(time.time() - _start_time, 1),
        "supported_tickers": settings.supported_tickers,
    }
