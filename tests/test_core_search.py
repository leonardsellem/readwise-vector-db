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
