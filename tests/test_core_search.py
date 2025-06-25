"""
Tests for the core search functionality including both streaming and non-streaming modes.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from readwise_vector_db.core.search import get_openai_client, semantic_search


@pytest.mark.asyncio
async def test_get_openai_client():
    """Test the OpenAI client singleton pattern"""
    with patch("os.environ.get", return_value="dummy-key"):
        with patch("openai.AsyncClient") as mock_client:
            # First call should create the client
            client1 = get_openai_client()
            mock_client.assert_called_once_with(api_key="dummy-key")

            # Second call should reuse the existing client
            client2 = get_openai_client()
            assert mock_client.call_count == 1
            assert client1 == client2


@pytest.mark.asyncio
async def test_get_openai_client_missing_api_key():
    """Test get_openai_client raises error when OPENAI_API_KEY is missing"""
    # Reset the global client to force recreation
    import readwise_vector_db.core.search

    readwise_vector_db.core.search._openai_client = None

    with patch("os.environ.get", return_value=None):
        with pytest.raises(
            ValueError, match="OPENAI_API_KEY environment variable must be set"
        ):
            get_openai_client()


@pytest.mark.asyncio
async def test_semantic_search_non_streaming():
    """Test semantic search in non-streaming mode"""
    # Mock the embedding function
    with patch("readwise_vector_db.core.search.embed", return_value=[0.1, 0.2, 0.3]):
        # Mock the Highlight class and its attributes
        mock_highlight = MagicMock()
        mock_highlight.__table__ = MagicMock()
        mock_highlight.__table__.c.embedding = MagicMock()
        mock_highlight.__table__.c.embedding.isnot = MagicMock()
        mock_highlight.embedding = MagicMock()
        mock_highlight.embedding.cosine_distance = MagicMock()

        # Create test results
        test_results = [
            {"id": "1", "text": "Test highlight 1", "score": 0.1},
            {"id": "2", "text": "Test highlight 2", "score": 0.2},
        ]

        # Mock the actual search function to return our test data
        async def mock_search_generator(*args, **kwargs):
            for result in test_results:
                yield result

        with patch("readwise_vector_db.core.search.get_openai_client"):
            with patch("readwise_vector_db.core.search.Highlight", mock_highlight):
                # Replace the _search_generator function directly
                with patch(
                    "readwise_vector_db.core.search._search_generator",
                    return_value=mock_search_generator(),
                ):
                    # Call the function in non-streaming mode
                    results = await semantic_search(
                        query="test query",
                        k=5,
                        stream=False,
                    )

                    # Check the results
                    assert len(results) == 2
                    assert results[0]["id"] == "1"
                    assert results[0]["text"] == "Test highlight 1"
                    assert results[0]["score"] == 0.1
                    assert results[1]["id"] == "2"
                    assert results[1]["text"] == "Test highlight 2"
                    assert results[1]["score"] == 0.2


@pytest.mark.asyncio
async def test_semantic_search_streaming():
    """Test semantic search in streaming mode"""
    # Mock the embedding function
    with patch("readwise_vector_db.core.search.embed", return_value=[0.1, 0.2, 0.3]):
        # Mock the Highlight class and its attributes
        mock_highlight = MagicMock()
        mock_highlight.__table__ = MagicMock()
        mock_highlight.__table__.c.embedding = MagicMock()
        mock_highlight.__table__.c.embedding.isnot = MagicMock()
        mock_highlight.embedding = MagicMock()
        mock_highlight.embedding.cosine_distance = MagicMock()

        # Create test results
        test_results = [
            {"id": "1", "text": "Test highlight 1", "score": 0.1},
            {"id": "2", "text": "Test highlight 2", "score": 0.2},
        ]

        # Create an async generator (properly mocked)
        async def mock_search_generator(*args, **kwargs):
            for result in test_results:
                yield result

        with patch("readwise_vector_db.core.search.get_openai_client"):
            with patch("readwise_vector_db.core.search.Highlight", mock_highlight):
                # Replace the _search_generator function directly
                with patch(
                    "readwise_vector_db.core.search._search_generator",
                    return_value=mock_search_generator(),
                ):
                    # Call the function in streaming mode
                    result_stream = await semantic_search(
                        query="test query",
                        k=5,
                        stream=True,
                    )

                    # Collect results from the stream
                    results = []
                    async for result in result_stream:
                        results.append(result)

                    # Check the results
                    assert len(results) == 2
                    assert results[0]["id"] == "1"
                    assert results[0]["text"] == "Test highlight 1"
                    assert results[0]["score"] == 0.1
                    assert results[1]["id"] == "2"
                    assert results[1]["text"] == "Test highlight 2"
                    assert results[1]["score"] == 0.2


@pytest.mark.asyncio
async def test_semantic_search_filters():
    """Test semantic search with filters"""
    # Mock the embedding function
    with patch("readwise_vector_db.core.search.embed", return_value=[0.1, 0.2, 0.3]):
        # Mock the Highlight class and its attributes
        mock_highlight = MagicMock()
        mock_highlight.source_type = MagicMock()
        mock_highlight.author = MagicMock()
        mock_highlight.tags = MagicMock()
        mock_highlight.highlighted_at = MagicMock()
        mock_highlight.__table__ = MagicMock()
        mock_highlight.__table__.c.embedding = MagicMock()
        mock_highlight.__table__.c.embedding.isnot = MagicMock()
        mock_highlight.tags.op = MagicMock()
        mock_highlight.tags.op.return_value = MagicMock()
        mock_highlight.highlighted_at.between = MagicMock()

        # Mock empty result
        mock_result = MagicMock()
        mock_result.__iter__.return_value = []

        mock_exec = AsyncMock(return_value=mock_result)
        mock_session = AsyncMock()
        mock_session.exec = mock_exec

        mock_session_ctx = AsyncMock()
        mock_session_ctx.__aenter__.return_value = mock_session
        mock_session_ctx.__aexit__.return_value = None

        # Create an async generator for get_session
        async def mock_get_session():
            yield mock_session_ctx

        with patch("readwise_vector_db.core.search.get_openai_client"):
            with patch("readwise_vector_db.core.search.Highlight", mock_highlight):
                with patch(
                    "readwise_vector_db.core.search.get_session",
                    return_value=mock_get_session(),
                ):
                    import datetime

                    # Call with filters
                    await semantic_search(
                        query="test query",
                        k=10,
                        source_type="article",
                        author="Test Author",
                        tags=["tag1", "tag2"],
                        highlighted_at_range=(
                            datetime.date(2023, 1, 1),
                            datetime.date(2023, 12, 31),
                        ),
                        stream=False,
                    )

                    # Verify the query was built
                    mock_session.exec.assert_called_once()


@pytest.mark.asyncio
async def test_search_with_date_range_filtering_supabase():
    """Test semantic search with date range filtering using Supabase operations"""
    from datetime import date

    from readwise_vector_db.config import DatabaseBackend, Settings

    # Create mock settings for Supabase
    mock_settings = MagicMock(spec=Settings)
    mock_settings.db_backend = DatabaseBackend.SUPABASE
    mock_settings.is_serverless = False

    # Mock search results with different dates
    search_results = [
        {
            "id": "1",
            "text": "Result 1",
            "highlighted_at": "2023-06-15T10:00:00Z",  # Within range
            "score": 0.1,
        },
        {
            "id": "2",
            "text": "Result 2",
            "highlighted_at": "2022-01-01T10:00:00Z",  # Outside range
            "score": 0.2,
        },
        {
            "id": "3",
            "text": "Result 3",
            "highlighted_at": "2023-12-01T10:00:00Z",  # Within range
            "score": 0.3,
        },
    ]

    async def mock_vector_search(*args, **kwargs):
        for result in search_results:
            yield result

    with patch("readwise_vector_db.core.search.embed", return_value=[0.1, 0.2, 0.3]):
        with patch("readwise_vector_db.core.search.get_openai_client"):
            with patch(
                "readwise_vector_db.core.search.vector_similarity_search",
                return_value=mock_vector_search(),
            ):
                # Test with date range that should filter out the 2022 result
                results = await semantic_search(
                    query="test query",
                    k=5,
                    highlighted_at_range=(date(2023, 1, 1), date(2023, 12, 31)),
                    use_supabase_ops=True,
                    settings_obj=mock_settings,
                    stream=False,
                )

                # Should only get 2 results (the ones from 2023)
                assert len(results) == 2
                assert results[0]["id"] == "1"
                assert results[1]["id"] == "3"


@pytest.mark.asyncio
async def test_search_with_date_parsing_error_supabase():
    """Test semantic search handles date parsing errors gracefully"""
    from datetime import date

    from readwise_vector_db.config import DatabaseBackend, Settings

    # Create mock settings for Supabase
    mock_settings = MagicMock(spec=Settings)
    mock_settings.db_backend = DatabaseBackend.SUPABASE
    mock_settings.is_serverless = False

    # Mock search results with invalid date formats
    search_results = [
        {
            "id": "1",
            "text": "Result 1",
            "highlighted_at": "invalid-date-format",  # Should be skipped
            "score": 0.1,
        },
        {
            "id": "2",
            "text": "Result 2",
            "highlighted_at": "2023-06-15T10:00:00Z",  # Valid date
            "score": 0.2,
        },
    ]

    async def mock_vector_search(*args, **kwargs):
        for result in search_results:
            yield result

    with patch("readwise_vector_db.core.search.embed", return_value=[0.1, 0.2, 0.3]):
        with patch("readwise_vector_db.core.search.get_openai_client"):
            with patch(
                "readwise_vector_db.core.search.vector_similarity_search",
                return_value=mock_vector_search(),
            ):
                # Test with date range - should handle parsing error gracefully
                results = await semantic_search(
                    query="test query",
                    k=5,
                    highlighted_at_range=(date(2023, 1, 1), date(2023, 12, 31)),
                    use_supabase_ops=True,
                    settings_obj=mock_settings,
                    stream=False,
                )

                # Should only get 1 result (the valid one)
                assert len(results) == 1
                assert results[0]["id"] == "2"


@pytest.mark.asyncio
async def test_search_sqlmodel_fallback_when_supabase_disabled():
    """Test that search falls back to SQLModel when use_supabase_ops=False"""
    from readwise_vector_db.config import DatabaseBackend, Settings

    # Create mock settings for local backend
    mock_settings = MagicMock(spec=Settings)
    mock_settings.db_backend = DatabaseBackend.LOCAL
    mock_settings.is_serverless = False

    # Mock the Highlight class and its attributes for SQLModel
    mock_highlight = MagicMock()
    mock_highlight.__table__ = MagicMock()
    mock_highlight.__table__.c.embedding = MagicMock()
    mock_highlight.__table__.c.embedding.isnot = MagicMock()

    # Mock empty result
    mock_result = MagicMock()
    mock_result.__iter__.return_value = []

    mock_exec = AsyncMock(return_value=mock_result)
    mock_session = AsyncMock()
    mock_session.exec = mock_exec

    mock_session_ctx = AsyncMock()
    mock_session_ctx.__aenter__.return_value = mock_session
    mock_session_ctx.__aexit__.return_value = None

    # Create an async generator for get_session
    async def mock_get_session():
        yield mock_session_ctx

    with patch("readwise_vector_db.core.search.embed", return_value=[0.1, 0.2, 0.3]):
        with patch("readwise_vector_db.core.search.get_openai_client"):
            with patch("readwise_vector_db.core.search.Highlight", mock_highlight):
                with patch(
                    "readwise_vector_db.core.search.get_session",
                    return_value=mock_get_session(),
                ):
                    # Call with use_supabase_ops=False to force SQLModel path
                    results = await semantic_search(
                        query="test query",
                        k=5,
                        use_supabase_ops=False,
                        settings_obj=mock_settings,
                        stream=False,
                    )

                    # Should use SQLModel path and return empty results
                    assert results == []
                    mock_session.exec.assert_called_once()
