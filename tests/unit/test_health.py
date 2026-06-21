from unittest.mock import patch

from fastapi.testclient import TestClient

from backend.api.main import app

client = TestClient(app)


def test_health_returns_ok_when_db_connected() -> None:
    with patch("backend.api.main.check_db_connection", return_value=True):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "MSFT" in data["supported_tickers"]


def test_health_returns_degraded_when_db_unavailable() -> None:
    with patch("backend.api.main.check_db_connection", return_value=False):
        response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "degraded"
    assert data["database"] == "unavailable"
