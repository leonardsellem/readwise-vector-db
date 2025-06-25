from datetime import date
from unittest.mock import patch, AsyncMock

import pytest
from fastapi.testclient import TestClient

from readwise_vector_db.api import app

client = TestClient(app)


def test_search_endpoint():
    with patch(
        "readwise_vector_db.api.routes.semantic_search", new_callable=AsyncMock
    ) as mock_semantic_search:
        mock_data = [
            {
                "id": "1",
                "text": "mocked text",
                "source_type": "article",
                "embedding": [],
                "score": 0.9,
            }
        ]
        
        # Set what the async mock should return when awaited
        mock_semantic_search.return_value = mock_data

        response = client.post("/search", json={"q": "test query", "k": 1})

        assert response.status_code == 200
        response_json = response.json()
        assert "results" in response_json
        assert len(response_json["results"]) == 1
        # We need to add the other required fields for the model to be valid
        mock_data[0]["source_id"] = None
        mock_data[0]["title"] = None
        mock_data[0]["author"] = None
        mock_data[0]["url"] = None
        mock_data[0]["tags"] = None
        mock_data[0]["highlighted_at"] = None
        mock_data[0]["updated_at"] = None
        assert response_json["results"] == mock_data
        mock_semantic_search.assert_called_once_with(
            "test query", 1, None, None, None, None
        )


def test_health_endpoint():
    # Mock the database dependency to avoid real DB connections
    with patch("readwise_vector_db.api.routes.get_db") as mock_get_db:
        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=None)
        mock_get_db.return_value = mock_db
        
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.parametrize(
    "filters, expected_filters",
    [
        (
            {"source_type": "book"},
            {
                "source_type": "book",
                "author": None,
                "tags": None,
                "highlighted_at_range": None,
            },
        ),
        (
            {"author": "John Doe"},
            {
                "source_type": None,
                "author": "John Doe",
                "tags": None,
                "highlighted_at_range": None,
            },
        ),
        (
            {"tags": ["python", "fastapi"]},
            {
                "source_type": None,
                "author": None,
                "tags": ["python", "fastapi"],
                "highlighted_at_range": None,
            },
        ),
        (
            {"highlighted_at_range": ["2023-01-01", "2023-12-31"]},
            {
                "source_type": None,
                "author": None,
                "tags": None,
                "highlighted_at_range": (date(2023, 1, 1), date(2023, 12, 31)),
            },
        ),
    ],
)
def test_search_with_filters(filters, expected_filters):
    with patch(
        "readwise_vector_db.api.routes.semantic_search", new_callable=AsyncMock
    ) as mock_semantic_search:
        # Set what the async mock should return when awaited
        mock_semantic_search.return_value = []
        payload = {"q": "test", "k": 5, **filters}
        response = client.post("/search", json=payload)

        assert response.status_code == 200
        mock_semantic_search.assert_called_once_with(
            "test",
            5,
            expected_filters["source_type"],
            expected_filters["author"],
            expected_filters["tags"],
            expected_filters["highlighted_at_range"],
        )
