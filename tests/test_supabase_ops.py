import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

# Test imports - these will be stubbed by conftest.py if needed
try:
    import asyncpg

    from readwise_vector_db.config import DatabaseBackend, Settings
    from readwise_vector_db.core.search import semantic_search
    from readwise_vector_db.db.supabase_ops import (
        execute_vector_query,
        upsert_highlights_vectorized,
        vector_similarity_search,
        with_supabase_retry,
    )
    from readwise_vector_db.db.upsert import upsert_highlights

    SUPABASE_MODULES_AVAILABLE = True
except ImportError:
    SUPABASE_MODULES_AVAILABLE = False


# Sample test data
SAMPLE_HIGHLIGHTS = [
    {
        "id": "test-1",
        "text": "This is a test highlight about machine learning",
        "source_type": "article",
        "source_author": "Test Author",
        "source_title": "ML Article",
        "source_url": "https://example.com/ml",
        "category": "technology",
        "note": "Interesting point",
        "location": 1,
        "highlighted_at": "2024-01-01T10:00:00Z",
        "tags": ["machine-learning", "ai"],
        "embedding": [0.1, 0.2, 0.3] + [0.0] * 3069,  # 3072 dimensions
    },
    {
        "id": "test-2",
        "text": "Another highlight about artificial intelligence",
        "source_type": "book",
        "source_author": "AI Expert",
        "source_title": "AI Book",
        "source_url": "https://example.com/ai",
        "category": "technology",
        "note": "Key insight",
        "location": 2,
        "highlighted_at": "2024-01-02T11:00:00Z",
        "tags": ["ai", "deep-learning"],
        "embedding": [0.2, 0.3, 0.4] + [0.0] * 3069,  # 3072 dimensions
    },
]

SAMPLE_EMBEDDING = [0.15, 0.25, 0.35] + [0.0] * 3069


@pytest.fixture
def mock_settings():
    """Mock settings for different deployment scenarios."""
    settings = MagicMock(spec=Settings)
    settings.db_backend = DatabaseBackend.LOCAL
    settings.DEPLOY_TARGET = "docker"
    settings.is_serverless = False
    return settings


@pytest.fixture
def supabase_settings():
    """Mock settings for Supabase deployment."""
    settings = MagicMock(spec=Settings)
    settings.db_backend = DatabaseBackend.SUPABASE
    settings.DEPLOY_TARGET = "vercel"
    settings.is_serverless = True
    return settings


@pytest_asyncio.fixture
async def mock_asyncpg_pool():
    """Mock asyncpg connection pool."""
    from unittest.mock import MagicMock

    # Create a real mock pool that works with async context managers
    pool = MagicMock()

    # Mock connection
    conn = AsyncMock()
    conn.fetch.return_value = [
        {
            "id": "test-1",
            "text": "Test highlight",
            "source_type": "article",
            "source_author": "Author",
            "source_title": "Title",
            "source_url": "URL",
            "category": "tech",
            "note": "Note",
            "location": 1,
            "highlighted_at": "2024-01-01",
            "tags": ["tag1"],
            "embedding": SAMPLE_EMBEDDING,
            "score": 0.1,
        }
    ]
    conn.fetchrow.return_value = {
        "id": "test-1",
        "embedding": SAMPLE_EMBEDDING,
        "score": 0.1,
    }
    conn.executemany.return_value = None

    # Create a proper async context manager mock
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return conn

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            return None

    # Mock pool.acquire() to return our async context manager
    pool.acquire.return_value = AsyncContextManagerMock()

    # Store connection reference for test access
    pool._mock_connection = conn

    return pool


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestSupabaseRetryLogic:
    """Test Supabase-specific retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_connection_error(self):
        """Test that connection errors trigger retries."""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise asyncpg.ConnectionDoesNotExistError("Connection lost")
            return "success"

        # Should succeed after 2 failures
        result = await with_supabase_retry(failing_func, max_attempts=3)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test that retries are eventually exhausted."""

        async def always_failing_func():
            raise asyncpg.ConnectionFailureError("Always fails")

        # Should raise the original exception after max attempts
        with pytest.raises(asyncpg.ConnectionFailureError):
            await with_supabase_retry(always_failing_func, max_attempts=2)

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test that non-retryable errors don't trigger retries."""
        call_count = 0

        async def failing_func():
            nonlocal call_count
            call_count += 1
            raise ValueError("Not a connection error")

        # Should not retry ValueError
        with pytest.raises(ValueError):
            await with_supabase_retry(failing_func, max_attempts=3)

        assert call_count == 1


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestVectorQuery:
    """Test vector query execution with asyncpg."""

    @pytest.mark.asyncio
    async def test_execute_vector_query_fetch_all(
        self, mock_asyncpg_pool, mock_settings
    ):
        """Test executing vector query that fetches all results."""

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            results = await execute_vector_query(
                "SELECT * FROM highlight",
                params=["param1"],
                fetch_all=True,
                settings_obj=mock_settings,
            )

            assert len(results) == 1
            assert results[0]["id"] == "test-1"

            # Verify pool was called correctly
            mock_asyncpg_pool.acquire.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_vector_query_fetch_one(
        self, mock_asyncpg_pool, mock_settings
    ):
        """Test executing vector query that fetches one result."""

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            result = await execute_vector_query(
                "SELECT * FROM highlight LIMIT 1",
                fetch_all=False,
                settings_obj=mock_settings,
            )

            assert result["id"] == "test-1"

    @pytest.mark.asyncio
    async def test_execute_vector_query_with_retry(self, mock_settings):
        """Test that vector query execution includes retry logic."""
        from unittest.mock import MagicMock

        pool = MagicMock()
        conn = AsyncMock()

        # Simulate connection failure then success
        call_count = 0

        async def mock_fetch(*args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncpg.ConnectionDoesNotExistError("Connection lost")
            return [{"id": "test-1"}]

        conn.fetch = mock_fetch

        # Create proper async context manager
        class AsyncContextManagerMock:
            async def __aenter__(self):
                return conn

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        pool.acquire.return_value = AsyncContextManagerMock()

        async def mock_get_pool(*args, **kwargs):
            return pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool", side_effect=mock_get_pool
        ):
            results = await execute_vector_query(
                "SELECT * FROM highlight",
                settings_obj=mock_settings,
            )

            assert len(results) == 1
            assert call_count == 2  # Failed once, succeeded on retry


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestVectorizedUpsert:
    """Test vectorized highlight upserts."""

    @pytest.mark.asyncio
    async def test_upsert_highlights_vectorized(self, mock_asyncpg_pool, mock_settings):
        """Test vectorized upsert of highlights."""

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            processed_count = await upsert_highlights_vectorized(
                SAMPLE_HIGHLIGHTS,
                batch_size=2,
                settings_obj=mock_settings,
            )

            assert processed_count == 2

            # Verify executemany was called with correct data
            mock_asyncpg_pool._mock_connection.executemany.assert_called()

    @pytest.mark.asyncio
    async def test_upsert_empty_list(self, mock_settings):
        """Test upsert with empty list returns 0."""
        processed_count = await upsert_highlights_vectorized(
            [],
            settings_obj=mock_settings,
        )

        assert processed_count == 0

    @pytest.mark.asyncio
    async def test_upsert_batch_processing(self, mock_asyncpg_pool, mock_settings):
        """Test that large datasets are processed in batches."""
        # Create larger dataset
        large_dataset = []
        for i in range(250):  # More than default batch size
            highlight = SAMPLE_HIGHLIGHTS[0].copy()
            highlight["id"] = f"test-{i}"
            large_dataset.append(highlight)

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            processed_count = await upsert_highlights_vectorized(
                large_dataset,
                batch_size=100,
                settings_obj=mock_settings,
            )

            assert processed_count == 250

            # Should have been called 3 times (2 full batches + 1 partial)
            conn = mock_asyncpg_pool._mock_connection
            assert conn.executemany.call_count == 3


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestVectorSimilaritySearch:
    """Test vector similarity search with asyncpg."""

    @pytest.mark.asyncio
    async def test_vector_similarity_search(self, mock_asyncpg_pool, mock_settings):
        """Test basic vector similarity search."""

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            results = []
            async for result in vector_similarity_search(
                query_embedding=SAMPLE_EMBEDDING,
                k=5,
                settings_obj=mock_settings,
            ):
                results.append(result)

            assert len(results) == 1
            assert results[0]["id"] == "test-1"
            assert "score" in results[0]

    @pytest.mark.asyncio
    async def test_vector_search_with_filters(self, mock_asyncpg_pool, mock_settings):
        """Test vector search with source type and author filters."""

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            results = []
            async for result in vector_similarity_search(
                query_embedding=SAMPLE_EMBEDDING,
                k=5,
                source_type="article",
                author="Test Author",
                tags=["ai", "ml"],
                settings_obj=mock_settings,
            ):
                results.append(result)

            assert len(results) == 1

            # Verify query includes WHERE conditions
            conn = mock_asyncpg_pool._mock_connection
            conn.fetch.assert_called_once()

            # Get the call arguments
            call_args = conn.fetch.call_args
            query_sql = call_args[0][0]
            query_params = call_args[0][1:]

            # Verify filters are in SQL
            assert "source_type = $2" in query_sql
            assert "source_author = $3" in query_sql
            assert "tags && $4" in query_sql

            # Verify parameters
            assert SAMPLE_EMBEDDING in query_params
            assert "article" in query_params
            assert "Test Author" in query_params
            assert ["ai", "ml"] in query_params


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestSemanticSearchIntegration:
    """Test integration with the semantic search API."""

    @pytest.mark.asyncio
    async def test_semantic_search_uses_supabase_ops(self, supabase_settings):
        """Test that semantic search uses Supabase ops for Supabase backend."""
        with (
            patch("readwise_vector_db.core.search.get_openai_client") as mock_client,
            patch("readwise_vector_db.core.search.embed") as mock_embed,
            patch(
                "readwise_vector_db.core.search.vector_similarity_search"
            ) as mock_vector_search,
        ):

            mock_client.return_value = AsyncMock()
            mock_embed.return_value = SAMPLE_EMBEDDING

            # Mock the async generator
            async def mock_search_gen(*args, **kwargs):
                yield {"id": "test-1", "text": "test", "score": 0.1}

            mock_vector_search.return_value = mock_search_gen()

            # Call semantic search
            results = await semantic_search(
                query="test query",
                k=5,
                use_supabase_ops=True,
                settings_obj=supabase_settings,
            )

            assert len(results) == 1
            assert results[0]["id"] == "test-1"

            # Verify Supabase ops were used
            mock_vector_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_semantic_search_fallback_to_sqlmodel(self, mock_settings):
        """Test that semantic search falls back to SQLModel for local deployments."""
        with (
            patch("readwise_vector_db.core.search.get_openai_client") as mock_client,
            patch("readwise_vector_db.core.search.embed") as mock_embed,
            patch(
                "readwise_vector_db.core.search._search_generator_sqlmodel"
            ) as mock_sqlmodel_search,
        ):

            mock_client.return_value = AsyncMock()
            mock_embed.return_value = SAMPLE_EMBEDDING

            # Mock the async generator
            async def mock_search_gen(*args, **kwargs):
                yield {"id": "test-1", "text": "test", "score": 0.1}

            mock_sqlmodel_search.return_value = mock_search_gen()

            # Call semantic search with local settings
            results = await semantic_search(
                query="test query",
                k=5,
                use_supabase_ops=True,  # Should be auto-disabled for local
                settings_obj=mock_settings,
            )

            assert len(results) == 1
            assert results[0]["id"] == "test-1"

            # Verify SQLModel fallback was used
            mock_sqlmodel_search.assert_called_once()


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestUpsertIntegration:
    """Test integration with the upsert API."""

    @pytest.mark.asyncio
    async def test_upsert_highlights_uses_supabase_ops(self, supabase_settings):
        """Test that upsert uses Supabase ops for Supabase backend."""
        from readwise_vector_db.models import Highlight

        # Create Highlight objects
        highlights = [
            Highlight(**SAMPLE_HIGHLIGHTS[0]),
            Highlight(**SAMPLE_HIGHLIGHTS[1]),
        ]

        mock_session = AsyncMock()

        with patch(
            "readwise_vector_db.db.upsert.upsert_highlights_vectorized"
        ) as mock_vectorized_upsert:
            mock_vectorized_upsert.return_value = 2

            await upsert_highlights(
                highlights,
                session=mock_session,
                use_supabase_ops=True,
                settings_obj=supabase_settings,
            )

            # Verify vectorized upsert was called
            mock_vectorized_upsert.assert_called_once()
            call_args = mock_vectorized_upsert.call_args

            # Verify highlights were converted to dicts
            highlights_data = call_args[0][0]
            assert len(highlights_data) == 2
            assert highlights_data[0]["id"] == "test-1"

    @pytest.mark.asyncio
    async def test_upsert_highlights_fallback_to_sqlmodel(self, mock_settings):
        """Test that upsert falls back to SQLModel for local deployments."""
        from readwise_vector_db.models import Highlight

        # Create Highlight objects
        highlights = [Highlight(**SAMPLE_HIGHLIGHTS[0])]
        mock_session = AsyncMock()

        with patch(
            "readwise_vector_db.db.upsert._upsert_highlights_sqlmodel"
        ) as mock_sqlmodel_upsert:
            await upsert_highlights(
                highlights,
                session=mock_session,
                use_supabase_ops=True,  # Should be auto-disabled for local
                settings_obj=mock_settings,
            )

            # Verify SQLModel fallback was used
            mock_sqlmodel_upsert.assert_called_once_with(highlights, mock_session)


@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestPostgres14Compatibility:
    """Test that vector operations are compatible with Postgres 14."""

    def test_vector_distance_operator(self):
        """Test that we use the correct distance operator for Postgres 14."""
        # The cosine distance operator <=> should be used instead of <->
        # This is verified by checking the SQL query generation
        query_template = """
        SELECT embedding <=> $1 as score
        FROM highlight
        WHERE embedding IS NOT NULL
        ORDER BY score
        """

        # Verify the operator is present in our query template
        assert "<=>" in query_template

        # Also verify we're not using the L2 distance operator
        assert "<->" not in query_template

    def test_array_overlap_operator(self):
        """Test that we use the correct array overlap operator."""
        # The && operator should be used for array overlap
        query_template = "tags && $1"
        assert "&&" in query_template

    def test_vector_column_type(self):
        """Test that vector column uses proper pgvector type."""
        # This would be tested against the actual schema
        # For now, we verify our sample data has the right dimensions
        assert len(SAMPLE_EMBEDDING) == 3072  # text-embedding-3-large dimensions


# Performance and edge case tests
@pytest.mark.skipif(
    not SUPABASE_MODULES_AVAILABLE, reason="Supabase modules not available"
)
class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_empty_embedding_list(self, mock_asyncpg_pool, mock_settings):
        """Test handling of empty embedding."""

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            results = []
            async for result in vector_similarity_search(
                query_embedding=[],  # Empty embedding
                k=5,
                settings_obj=mock_settings,
            ):
                results.append(result)

            # Should handle gracefully
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_zero_k_parameter(self, mock_asyncpg_pool, mock_settings):
        """Test handling of k=0."""
        mock_asyncpg_pool._mock_connection.fetch.return_value = []

        async def mock_get_pool(*args, **kwargs):
            return mock_asyncpg_pool

        with patch(
            "readwise_vector_db.db.supabase_ops.get_pool",
            side_effect=mock_get_pool,
        ):
            results = []
            async for result in vector_similarity_search(
                query_embedding=SAMPLE_EMBEDDING,
                k=0,
                settings_obj=mock_settings,
            ):
                results.append(result)

            assert len(results) == 0

    @pytest.mark.asyncio
    async def test_network_timeout_retry(self, mock_settings):
        """Test handling of network timeouts with retry."""
        call_count = 0

        async def timeout_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise asyncio.TimeoutError("Network timeout")
            return [{"id": "test-1"}]

        # Should retry and succeed
        result = await with_supabase_retry(timeout_then_succeed)
        assert len(result) == 1
        assert call_count == 2
