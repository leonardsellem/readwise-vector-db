"""
Tests for the shared search service used by both TCP and HTTP MCP servers.

This module tests the SearchService that encapsulates parameter processing
and search invocation logic shared between different MCP implementations.
"""

from datetime import date
from unittest.mock import patch

import pytest

from readwise_vector_db.mcp.search_service import SearchParams, SearchService


class TestSearchParams:
    """Test SearchParams class."""

    def test_basic_params(self):
        """Test basic parameter initialization."""
        params = SearchParams("test query", k=10)
        assert params.query == "test query"
        assert params.k == 10
        assert params.source_type is None
        assert params.author is None
        assert params.tags is None
        assert params.highlighted_at_range is None

    def test_full_params(self):
        """Test initialization with all parameters."""
        date_range = (date(2024, 1, 1), date(2024, 12, 31))
        params = SearchParams(
            query="full test",
            k=50,
            source_type="article",
            author="Test Author",
            tags=["tag1", "tag2"],
            highlighted_at_range=date_range,
        )
        assert params.query == "full test"
        assert params.k == 50
        assert params.source_type == "article"
        assert params.author == "Test Author"
        assert params.tags == ["tag1", "tag2"]
        assert params.highlighted_at_range == date_range

    def test_string_representation(self):
        """Test string representation for logging."""
        params = SearchParams("test", k=5, author="Author", tags=["tag"])
        str_repr = str(params)
        assert "test" in str_repr
        assert "k=5" in str_repr
        assert "author=Author" in str_repr
        assert "tags=1 items" in str_repr


class TestSearchServiceParsing:
    """Test SearchService parameter parsing methods."""

    def test_parse_mcp_params_basic(self):
        """Test basic MCP parameter parsing."""
        params = {"q": "test query", "k": 15}
        search_params = SearchService.parse_mcp_params(params)

        assert search_params.query == "test query"
        assert search_params.k == 15
        assert search_params.source_type is None

    def test_parse_mcp_params_full(self):
        """Test full MCP parameter parsing with filters."""
        params = {
            "q": "complex query",
            "k": 25,
            "source_type": "book",
            "author": "Jane Doe",
            "tags": ["fiction", "mystery"],
            "highlighted_at_range": ["2024-01-01", "2024-06-30"],
        }
        search_params = SearchService.parse_mcp_params(params)

        assert search_params.query == "complex query"
        assert search_params.k == 25
        assert search_params.source_type == "book"
        assert search_params.author == "Jane Doe"
        assert search_params.tags == ["fiction", "mystery"]
        assert search_params.highlighted_at_range == (
            date(2024, 1, 1),
            date(2024, 6, 30),
        )

    def test_parse_mcp_params_invalid_query(self):
        """Test MCP parsing with invalid query parameter."""
        params = {"q": "", "k": 10}
        with pytest.raises(ValueError, match="Missing or invalid 'q' parameter"):
            SearchService.parse_mcp_params(params)

        params = {"k": 10}  # Missing q
        with pytest.raises(ValueError, match="Missing or invalid 'q' parameter"):
            SearchService.parse_mcp_params(params)

    def test_parse_mcp_params_invalid_k(self):
        """Test MCP parsing handles invalid k parameter."""
        params = {"q": "test", "k": -5}
        search_params = SearchService.parse_mcp_params(params)
        assert search_params.k == 20  # Should default to 20

        params = {"q": "test", "k": "invalid"}
        search_params = SearchService.parse_mcp_params(params)
        assert search_params.k == 20  # Should default to 20

    def test_parse_mcp_params_invalid_date_range(self):
        """Test MCP parsing handles invalid date ranges gracefully."""
        params = {"q": "test", "highlighted_at_range": ["invalid-date", "2024-12-31"]}
        search_params = SearchService.parse_mcp_params(params)
        assert search_params.highlighted_at_range is None

    def test_parse_http_params_basic(self):
        """Test basic HTTP parameter parsing."""
        search_params = SearchService.parse_http_params(query="http test", k=30)
        assert search_params.query == "http test"
        assert search_params.k == 30

    def test_parse_http_params_with_dates(self):
        """Test HTTP parameter parsing with date range."""
        search_params = SearchService.parse_http_params(
            query="date test", from_date="2024-03-01", to_date="2024-09-30"
        )
        assert search_params.query == "date test"
        assert search_params.highlighted_at_range == (
            date(2024, 3, 1),
            date(2024, 9, 30),
        )

    def test_parse_http_params_invalid_query(self):
        """Test HTTP parsing with invalid query."""
        with pytest.raises(ValueError, match="Missing or invalid 'q' parameter"):
            SearchService.parse_http_params(query="")

    def test_parse_http_params_invalid_dates(self):
        """Test HTTP parsing handles invalid dates gracefully."""
        search_params = SearchService.parse_http_params(
            query="test", from_date="bad-date", to_date="2024-12-31"
        )
        assert search_params.highlighted_at_range is None


class TestSearchServiceExecution:
    """Test SearchService search execution."""

    @pytest.mark.asyncio
    async def test_execute_search_basic(self):
        """Test basic search execution."""
        # Mock search results
        mock_results = [
            {"id": 1, "text": "Result 1", "score": 0.9},
            {"id": 2, "text": "Result 2", "score": 0.8},
        ]

        async def mock_semantic_search(*args, **kwargs):
            for result in mock_results:
                yield result

        search_params = SearchParams("test query")

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            mock_semantic_search,
        ):
            results = []
            async for result in SearchService.execute_search(search_params):
                results.append(result)

            assert len(results) == 2
            assert results[0]["id"] == 1
            assert results[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_execute_search_with_client_id(self):
        """Test search execution with client ID for logging."""

        async def mock_semantic_search(*args, **kwargs):
            yield {"id": 1, "text": "Test", "score": 0.9}

        search_params = SearchParams("test query")

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            mock_semantic_search,
        ):
            results = []
            async for result in SearchService.execute_search(
                search_params, client_id="test-client"
            ):
                results.append(result)

            assert len(results) == 1

    @pytest.mark.asyncio
    async def test_execute_search_no_streaming(self):
        """Test search execution without streaming."""

        async def mock_semantic_search(*args, **kwargs):
            stream = kwargs.get('stream', False)
            if stream:
                # Return async generator for streaming
                async def async_gen():
                    yield {"id": 1, "text": "Test", "score": 0.9}
                return async_gen()
            else:
                # Return list for non-streaming
                return [{"id": 1, "text": "Test", "score": 0.9}]

        search_params = SearchParams("test query")

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            mock_semantic_search,
        ):
            results = []
            async for result in SearchService.execute_search(
                search_params, stream=False
            ):
                results.append(result)

            assert len(results) == 1


class TestLegacyCompatibility:
    """Test legacy compatibility functions."""

    @pytest.mark.asyncio
    async def test_execute_mcp_search_legacy(self):
        """Test legacy execute_mcp_search function."""
        from readwise_vector_db.mcp.search_service import execute_mcp_search

        async def mock_semantic_search(*args, **kwargs):
            yield {"id": 1, "text": "Legacy test", "score": 0.9}

        params = {"q": "legacy test", "k": 10}

        with patch(
            "readwise_vector_db.mcp.search_service.semantic_search",
            mock_semantic_search,
        ):
            results = []
            async for result in execute_mcp_search(params, client_id="legacy-client"):
                results.append(result)

            assert len(results) == 1
            assert results[0]["text"] == "Legacy test"
