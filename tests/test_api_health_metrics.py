from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from readwise_vector_db.api import app


@pytest.fixture
def mock_db_session():
    """Mock async database session for testing."""
    session = AsyncMock()
    # Mock successful DB connection (SELECT 1 executes without error)
    session.execute.return_value = (
        None  # execute() doesn't need to return anything specific
    )
    return session


@pytest.fixture
def mock_db_session_failure():
    """Mock failed async database session for testing."""
    session = AsyncMock()
    # Mock DB connection failure
    session.execute.side_effect = OperationalError("Connection failed", None, None)
    return session


def test_health_endpoint_success():
    """Test /health endpoint when database is healthy."""
    with patch("readwise_vector_db.api.AsyncSessionLocal") as mock_session_local:
        # Mock the context manager behavior of AsyncSessionLocal
        mock_session = AsyncMock()
        mock_session.execute.return_value = None  # Successful DB query
        mock_session_local.return_value.__aenter__.return_value = mock_session

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_health_endpoint_db_failure():
    """Test /health endpoint when database is down."""
    with patch("readwise_vector_db.api.AsyncSessionLocal") as mock_session_local:
        # Mock the context manager to raise an exception
        mock_session = AsyncMock()
        mock_session.execute.side_effect = OperationalError(
            "Connection failed", None, None
        )
        mock_session_local.return_value.__aenter__.return_value = mock_session

        client = TestClient(app)
        response = client.get("/health")

        assert response.status_code == 503
        assert response.json() == {"detail": "DB unavailable"}


def test_metrics_endpoint():
    """Test /metrics endpoint returns Prometheus metrics."""
    client = TestClient(app)
    response = client.get("/metrics")

    assert response.status_code == 200
    text = response.text
    # Check for presence of custom Prometheus metrics
    assert "rows_synced_total" in text
    assert "error_rate" in text
    assert "sync_duration_seconds" in text
    # Check for standard FastAPI instrumentator metrics
    assert "http_requests_total" in text or "fastapi" in text.lower()
