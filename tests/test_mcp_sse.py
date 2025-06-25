"""
Tests for MCP Server-Sent Events (SSE) streaming endpoint.

This module tests the HTTP-based MCP server that uses Server-Sent Events
for streaming search results to clients in serverless environments.
"""

import json
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from readwise_vector_db.api.routes import setup_routes


@pytest.fixture
def app():
    """Create FastAPI app for testing without lifespan management."""
    app = FastAPI(
        title="ReadWise Vector DB Test", description="Test app", docs_url="/docs"
    )
    setup_routes(app)
    return app


@pytest.fixture
def test_client(app):
    """Create FastAPI test client for SSE endpoint testing."""
    return TestClient(app)


def test_mcp_stream_basic_search(test_client):
    """Test basic SSE streaming functionality."""
    # Mock search results
    mock_results = [
        {
            "id": 1,
            "text": "Test highlight 1",
            "score": 0.9,
            "source_type": "article",
            "author": "Test Author",
            "title": "Test Title",
            "url": "https://example.com",
            "tags": ["test"],
            "highlighted_at": "2024-01-01",
            "updated_at": "2024-01-01",
        },
        {
            "id": 2,
            "text": "Test highlight 2",
            "score": 0.8,
            "source_type": "book",
            "author": "Another Author",
            "title": "Another Title",
            "url": None,
            "tags": None,
            "highlighted_at": None,
            "updated_at": None,
        },
    ]

    # Mock the semantic_search function to return async generator when stream=True
    def mock_search(*args, stream=False, **kwargs):
        if stream:
            # Return async generator directly for streaming
            async def async_gen():
                for result in mock_results:
                    yield result

            return async_gen()
        else:
            # Return list directly for non-streaming
            return mock_results

    with patch("readwise_vector_db.mcp.search_service.semantic_search", mock_search):
        # Make request to SSE endpoint
        with test_client.stream(
            "GET", "/mcp/stream", params={"q": "test query", "k": 5}
        ) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["connection"] == "keep-alive"

            # Read content and parse events
            content = response.read().decode()
            lines = content.split("\n")

            # Verify we got result events and completion event
            result_events = [line for line in lines if line.startswith("event: result")]
            data_lines = [line for line in lines if line.startswith("data: ")]
            complete_events = [line for line in lines if "complete" in line]

            assert len(result_events) == 2  # Two result events
            assert len(complete_events) >= 1  # At least one completion event

            # Parse first result data
            first_data_line = data_lines[0]
            result_data = json.loads(first_data_line[6:])  # Remove "data: " prefix
            assert result_data["id"] == 1
            assert result_data["text"] == "Test highlight 1"
            assert result_data["score"] == 0.9


def test_mcp_stream_with_filters(test_client):
    """Test SSE streaming with query filters."""
    mock_results = [
        {
            "id": 1,
            "text": "Filtered result",
            "score": 0.9,
            "source_type": "article",
            "author": "Target Author",
            "title": "Test Title",
            "url": None,
            "tags": ["python", "ai"],
            "highlighted_at": None,
            "updated_at": None,
        }
    ]

    def mock_search(*args, stream=False, **kwargs):
        # Verify filters are passed correctly
        assert args[2] == "article"  # source_type
        assert args[3] == "Target Author"  # author
        assert args[4] == ["python", "ai"]  # tags
        if stream:
            # Return async generator directly for streaming
            async def async_gen():
                for result in mock_results:
                    yield result

            return async_gen()
        else:
            # Return list directly for non-streaming
            return mock_results

    with patch("readwise_vector_db.mcp.search_service.semantic_search", mock_search):
        params = {
            "q": "test query",
            "k": 10,
            "source_type": "article",
            "author": "Target Author",
            "tags": "python,ai",  # Comma-separated
            "highlighted_at_start": "2024-01-01",
            "highlighted_at_end": "2024-12-31",
        }

        with test_client.stream("GET", "/mcp/stream", params=params) as response:
            assert response.status_code == 200
            # Just verify we get a response
            content = response.read()
            assert len(content) > 0


def test_mcp_stream_empty_results(test_client):
    """Test SSE streaming when no results are found."""

    def mock_search(*args, stream=False, **kwargs):
        if stream:
            # Return empty async generator directly for streaming
            async def async_gen():
                # Empty async generator - yield nothing but still be an async generator
                if False:  # This makes it an async generator but yields nothing
                    yield None  # pragma: no cover

            return async_gen()
        else:
            # Return empty list directly for non-streaming
            return []

    with patch("readwise_vector_db.mcp.search_service.semantic_search", mock_search):
        with test_client.stream(
            "GET", "/mcp/stream", params={"q": "nonexistent query"}
        ) as response:
            assert response.status_code == 200

            # Collect events
            content = response.read().decode()
            lines = content.split("\n")

            # Should still get completion event with 0 results
            # Look for event: complete line (SSE format splits event and data across lines)
            complete_events = [
                line for line in lines if line.startswith("event: complete")
            ]
            assert len(complete_events) >= 1


def test_mcp_stream_error_handling(test_client):
    """Test SSE streaming error handling."""

    def mock_search(*args, stream=False, **kwargs):
        if stream:
            # Return async generator that raises an error for streaming
            async def async_gen():
                # Yield first to make it an async generator, then raise
                if False:  # This makes it an async generator
                    yield None  # pragma: no cover
                raise Exception("Search failed")

            return async_gen()
        else:
            # Raise error directly for non-streaming
            raise Exception("Search failed")

    with patch("readwise_vector_db.mcp.search_service.semantic_search", mock_search):
        with test_client.stream(
            "GET", "/mcp/stream", params={"q": "error query"}
        ) as response:
            assert response.status_code == 200  # SSE endpoint should still return 200

            # Collect events
            content = response.read().decode()
            lines = content.split("\n")
            # Look for event: error line (SSE format splits event and data across lines)
            error_lines = [line for line in lines if line.startswith("event: error")]

            # Should get error event
            assert len(error_lines) >= 1

            # Find the data line that follows the event line
            error_event_index = lines.index(error_lines[0])
            if error_event_index + 1 < len(lines):
                data_line = lines[error_event_index + 1]
                if data_line.startswith("data: "):
                    error_data = json.loads(data_line[6:])  # Remove "data: " prefix
                    assert "Search failed" in error_data["message"]


def test_mcp_stream_parameter_validation(test_client):
    """Test SSE endpoint parameter validation."""
    # Test missing required parameter
    response = test_client.get("/mcp/stream")
    assert response.status_code == 422  # Validation error

    # Test invalid k parameter
    response = test_client.get("/mcp/stream", params={"q": "test", "k": 0})
    assert response.status_code == 422  # k must be >= 1

    # Test k parameter too large
    response = test_client.get("/mcp/stream", params={"q": "test", "k": 1000})
    assert response.status_code == 422  # k must be <= 100


def test_mcp_stream_date_range_parsing(test_client):
    """Test date range parameter parsing in SSE endpoint."""

    def mock_search(*args, stream=False, **kwargs):
        # Verify date range tuple is passed correctly
        date_range = args[5]  # highlighted_at_range parameter
        if date_range:
            from datetime import date

            start_date, end_date = date_range
            assert isinstance(start_date, date)
            assert isinstance(end_date, date)
            assert start_date.year == 2024
            assert end_date.year == 2024

        if stream:
            # Return empty async generator directly for streaming
            async def async_gen():
                # Return empty async generator - yield nothing but still be an async generator
                if False:  # This makes it an async generator but yields nothing
                    yield None  # pragma: no cover

            return async_gen()
        else:
            # Return empty list directly for non-streaming
            return []

    with patch("readwise_vector_db.mcp.search_service.semantic_search", mock_search):
        params = {
            "q": "date test",
            "highlighted_at_start": "2024-01-01",
            "highlighted_at_end": "2024-12-31",
        }

        with test_client.stream("GET", "/mcp/stream", params=params) as response:
            assert response.status_code == 200
