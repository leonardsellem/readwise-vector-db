"""Test database abstraction layer."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from readwise_vector_db.config import DatabaseBackend, DeployTarget, Settings
from readwise_vector_db.db import (
    _ensure_asyncpg_driver,
    close_connections,
    database_url,
    get_engine,
    get_engine_config,
    get_pool,
    get_session,
    get_session_maker,
)


class TestDatabaseUrl:
    """Test database URL generation."""

    def test_supabase_backend_with_url(self):
        """Test Supabase backend returns the configured URL."""
        settings = Settings(
            db_backend=DatabaseBackend.SUPABASE,
            supabase_db_url="postgresql+asyncpg://user:pass@supabase.co:5432/db",
        )

        result = database_url(settings)
        assert result == "postgresql+asyncpg://user:pass@supabase.co:5432/db"

    def test_supabase_backend_missing_url_raises_error(self):
        """Test Supabase backend without URL raises ValueError."""
        # Create a settings object with None URL to test the runtime error
        settings = Settings(
            db_backend=DatabaseBackend.SUPABASE,
            supabase_db_url="placeholder",
        )
        # Manually set it to None to test the runtime check
        settings.supabase_db_url = None

        with pytest.raises(ValueError) as exc_info:
            database_url(settings)

        assert "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'" in str(
            exc_info.value
        )

    def test_local_backend_with_url(self):
        """Test local backend returns the configured URL."""
        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://postgres:password@localhost:5432/local",
        )

        result = database_url(settings)
        assert result == "postgresql+asyncpg://postgres:password@localhost:5432/local"

    @patch.dict(
        os.environ, {"DATABASE_URL": "postgresql://user:pass@host:5432/db"}, clear=True
    )
    def test_local_backend_fallback_to_env_var(self):
        """Test local backend falls back to DATABASE_URL environment variable."""
        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            local_db_url=None,
        )

        result = database_url(settings)
        # Should ensure asyncpg driver
        assert result == "postgresql+asyncpg://user:pass@host:5432/db"

    @patch.dict(
        os.environ,
        {
            "POSTGRES_USER": "testuser",
            "POSTGRES_PASSWORD": "testpass",
            "POSTGRES_DB": "testdb",
        },
        clear=True,
    )
    def test_local_backend_fallback_to_individual_vars(self):
        """Test local backend constructs URL from individual environment variables."""
        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            local_db_url=None,
        )

        result = database_url(settings)
        assert result == "postgresql+asyncpg://testuser:testpass@localhost:5432/testdb"

    @patch.dict(os.environ, {}, clear=True)
    def test_local_backend_final_fallback_defaults(self):
        """Test local backend uses default values when no environment variables are set."""
        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            local_db_url=None,
        )

        result = database_url(settings)
        assert (
            result == "postgresql+asyncpg://postgres:postgres@localhost:5432/readwise"
        )


class TestEnsureAsyncpgDriver:
    """Test the asyncpg driver conversion logic."""

    def test_already_asyncpg_unchanged(self):
        """Test URLs with asyncpg driver are unchanged."""
        url = "postgresql+asyncpg://user:pass@host:5432/db"
        result = _ensure_asyncpg_driver(url)
        assert result == url

    def test_already_psycopg_async_unchanged(self):
        """Test URLs with psycopg_async driver are unchanged."""
        url = "postgresql+psycopg_async://user:pass@host:5432/db"
        result = _ensure_asyncpg_driver(url)
        assert result == url

    def test_psycopg_converted_to_asyncpg(self):
        """Test psycopg driver is converted to asyncpg."""
        url = "postgresql+psycopg://user:pass@host:5432/db"

        with patch("warnings.warn") as mock_warn:
            result = _ensure_asyncpg_driver(url)

        assert result == "postgresql+asyncpg://user:pass@host:5432/db"
        mock_warn.assert_called_once()

    def test_psycopg2_converted_to_asyncpg(self):
        """Test psycopg2 driver is converted to asyncpg."""
        url = "postgresql+psycopg2://user:pass@host:5432/db"

        with patch("warnings.warn") as mock_warn:
            result = _ensure_asyncpg_driver(url)

        assert result == "postgresql+asyncpg://user:pass@host:5432/db"
        mock_warn.assert_called_once()

    def test_plain_postgresql_converted_to_asyncpg(self):
        """Test plain postgresql:// URLs are converted to use asyncpg."""
        url = "postgresql://user:pass@host:5432/db"

        with patch("warnings.warn") as mock_warn:
            result = _ensure_asyncpg_driver(url)

        assert result == "postgresql+asyncpg://user:pass@host:5432/db"
        mock_warn.assert_called_once()


class TestEngineConfig:
    """Test SQLAlchemy engine configuration."""

    def test_serverless_config(self):
        """Test engine configuration for serverless deployment."""
        settings = Settings(deploy_target=DeployTarget.VERCEL)

        config = get_engine_config(settings)

        assert config["pool_size"] == 1
        assert config["max_overflow"] == 4
        assert config["pool_pre_ping"] is True
        assert config["pool_recycle"] == 3600
        assert config["echo"] is False
        assert config["future"] is True

    def test_container_config(self):
        """Test engine configuration for container deployment."""
        settings = Settings(deploy_target=DeployTarget.DOCKER)

        config = get_engine_config(settings)

        assert config["pool_size"] == 5
        assert config["max_overflow"] == 10
        assert config["pool_pre_ping"] is True
        assert config["echo"] is False
        assert config["future"] is True
        # Should not have pool_recycle for container deployment
        assert "pool_recycle" not in config or config.get("pool_recycle") != 3600


class TestGetEngine:
    """Test engine creation and caching."""

    def setUp(self):
        """Clear global engine state before each test."""
        import readwise_vector_db.db

        readwise_vector_db.db._engine = None

    @patch("readwise_vector_db.db.create_async_engine")
    def test_get_engine_with_settings(self, mock_create_engine):
        """Test get_engine with explicit settings."""
        self.setUp()

        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://test:test@localhost:5432/test",
        )

        mock_engine = AsyncMock()
        mock_create_engine.return_value = mock_engine

        result = get_engine(settings)

        assert result == mock_engine
        mock_create_engine.assert_called_once()

    @patch("readwise_vector_db.db.create_async_engine")
    @patch("readwise_vector_db.db.database_url")
    @patch("readwise_vector_db.db.get_engine_config")
    def test_get_engine_without_settings_uses_global(
        self, mock_get_config, mock_database_url, mock_create_engine
    ):
        """Test get_engine without settings uses global settings."""
        self.setUp()

        mock_engine = AsyncMock()
        mock_create_engine.return_value = mock_engine
        mock_database_url.return_value = (
            "postgresql+asyncpg://test:test@localhost:5432/test"
        )
        mock_get_config.return_value = {"echo": False, "future": True}

        # This will trigger the global settings import path (line 86)
        result = get_engine(None)

        assert result == mock_engine
        mock_create_engine.assert_called_once()
        # Verify that the functions were called with the global settings
        mock_database_url.assert_called_once()
        mock_get_config.assert_called_once()


class TestGetSessionMaker:
    """Test session maker creation and caching."""

    def setUp(self):
        """Clear global session maker state before each test."""
        import readwise_vector_db.db

        readwise_vector_db.db._session_maker = None
        readwise_vector_db.db._engine = None

    @patch("readwise_vector_db.db.get_engine")
    @patch("readwise_vector_db.db.sessionmaker")
    def test_get_session_maker_creates_new(self, mock_sessionmaker, mock_get_engine):
        """Test session maker creation."""
        self.setUp()

        mock_engine = AsyncMock()
        mock_get_engine.return_value = mock_engine
        mock_session_maker = AsyncMock()
        mock_sessionmaker.return_value = mock_session_maker

        result = get_session_maker()

        assert result == mock_session_maker
        mock_get_engine.assert_called_once()
        mock_sessionmaker.assert_called_once()


class TestGetSession:
    """Test session dependency."""

    @pytest.mark.asyncio
    async def test_get_session_yields_session(self):
        """Test get_session yields a session."""
        mock_session = AsyncMock()

        # Create a proper mock session maker that returns an async context manager
        class MockSessionMaker:
            def __call__(self):
                return MockSession()

        class MockSession:
            async def __aenter__(self):
                return mock_session

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

        mock_session_maker = MockSessionMaker()

        with patch(
            "readwise_vector_db.db.get_session_maker", return_value=mock_session_maker
        ):
            # get_session is an async generator
            session_gen = get_session()
            session = await session_gen.__anext__()

            assert session == mock_session

            # Clean up the generator
            try:
                await session_gen.__anext__()
            except StopAsyncIteration:
                pass


class TestGetPool:
    """Test asyncpg pool creation."""

    def setUp(self):
        """Clear global pool state before each test."""
        import readwise_vector_db.db

        readwise_vector_db.db._pool = None

    @pytest.mark.asyncio
    async def test_pool_serverless_config(self):
        """
        Test that the asyncpg connection pool is configured correctly for serverless deployment targets.
        
        Verifies that the pool is created with the expected parameters and that the database URL is normalized to exclude the driver suffix.
        """
        self.setUp()

        settings = Settings(
            deploy_target=DeployTarget.VERCEL,
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://user:pass@host:5432/db",
        )

        # Mock asyncpg.create_pool to avoid actual database connection
        mock_pool = AsyncMock()
        with patch(
            "readwise_vector_db.db.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ) as mock_create:
            result = await get_pool(settings)

            assert result == mock_pool
            mock_create.assert_called_once_with(
                "postgresql://user:pass@host:5432/db",
                min_size=0,
                max_size=5,
                command_timeout=30,
            )

    @pytest.mark.asyncio
    async def test_pool_container_config(self):
        """
        Test that `get_pool` creates an asyncpg connection pool with correct settings for container deployment.
        
        Verifies that the pool is configured with the expected connection string and pool parameters when using Docker as the deployment target and a local database backend.
        """
        self.setUp()

        settings = Settings(
            deploy_target=DeployTarget.DOCKER,
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://user:pass@host:5432/db",
        )

        # Mock asyncpg.create_pool to avoid actual database connection
        mock_pool = AsyncMock()
        with patch(
            "readwise_vector_db.db.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ) as mock_create:
            result = await get_pool(settings)

            assert result == mock_pool
            mock_create.assert_called_once_with(
                "postgresql://user:pass@host:5432/db",
                min_size=2,
                max_size=10,
                command_timeout=30,
            )

    @pytest.mark.asyncio
    async def test_pool_lazy_initialization(self):
        """Test that pool is created only once and cached."""
        self.setUp()

        settings = Settings(
            deploy_target=DeployTarget.VERCEL,
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://user:pass@host:5432/db",
        )

        mock_pool = AsyncMock()
        with patch(
            "readwise_vector_db.db.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ) as mock_create:
            # First call
            result1 = await get_pool(settings)
            # Second call
            result2 = await get_pool(settings)

            assert result1 == mock_pool
            assert result2 == mock_pool
            # Should only be called once due to caching
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_pool_without_settings_uses_global(self):
        """Test get_pool without settings uses global settings."""
        self.setUp()

        mock_pool = AsyncMock()
        with patch(
            "readwise_vector_db.db.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ) as mock_create:
            # This will trigger the global settings import path
            result = await get_pool(None)

            assert result == mock_pool
            mock_create.assert_called_once()


class TestCloseConnections:
    """Test connection cleanup."""

    @pytest.mark.asyncio
    async def test_close_connections_with_engine_and_pool(self):
        """Test closing both engine and pool."""
        import readwise_vector_db.db

        # Set up mock objects
        mock_engine = AsyncMock()
        mock_pool = AsyncMock()
        mock_session_maker = AsyncMock()

        readwise_vector_db.db._engine = mock_engine
        readwise_vector_db.db._pool = mock_pool
        readwise_vector_db.db._session_maker = mock_session_maker

        await close_connections()

        # Verify cleanup
        mock_engine.dispose.assert_called_once()
        mock_pool.close.assert_called_once()

        # Verify globals are reset
        assert readwise_vector_db.db._engine is None
        assert readwise_vector_db.db._pool is None
        assert readwise_vector_db.db._session_maker is None

    @pytest.mark.asyncio
    async def test_close_connections_with_only_engine(self):
        """Test closing only engine when pool is None."""
        import readwise_vector_db.db

        # Set up mock objects
        mock_engine = AsyncMock()

        readwise_vector_db.db._engine = mock_engine
        readwise_vector_db.db._pool = None
        readwise_vector_db.db._session_maker = None

        await close_connections()

        # Verify cleanup
        mock_engine.dispose.assert_called_once()

        # Verify globals are reset
        assert readwise_vector_db.db._engine is None
        assert readwise_vector_db.db._pool is None
        assert readwise_vector_db.db._session_maker is None

    @pytest.mark.asyncio
    async def test_close_connections_with_no_connections(self):
        """Test closing connections when nothing is initialized."""
        import readwise_vector_db.db

        readwise_vector_db.db._engine = None
        readwise_vector_db.db._pool = None
        readwise_vector_db.db._session_maker = None

        # Should not raise any errors
        await close_connections()

        # Verify globals remain None
        assert readwise_vector_db.db._engine is None
        assert readwise_vector_db.db._pool is None
        assert readwise_vector_db.db._session_maker is None


class TestIntegration:
    """Test integration scenarios."""

    def test_supabase_to_vercel_full_flow(self):
        """Test the full flow from Supabase settings to Vercel deployment."""
        settings = Settings(
            db_backend=DatabaseBackend.SUPABASE,
            deploy_target=DeployTarget.VERCEL,
            supabase_db_url="postgresql://user:pass@supabase.co:5432/db",
        )

        # Test URL generation
        url = database_url(settings)
        assert url == "postgresql+asyncpg://user:pass@supabase.co:5432/db"

        # Test engine config
        config = get_engine_config(settings)
        assert config["pool_size"] == 1
        assert config["pool_recycle"] == 3600

    def test_local_to_docker_full_flow(self):
        """Test the full flow from local settings to Docker deployment."""
        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            deploy_target=DeployTarget.DOCKER,
            local_db_url="postgresql://postgres:password@localhost:5432/readwise",
        )

        # Test URL generation
        url = database_url(settings)
        assert url == "postgresql+asyncpg://postgres:password@localhost:5432/readwise"

        # Test engine config
        config = get_engine_config(settings)
        assert config["pool_size"] == 5
        assert "pool_recycle" not in config or config.get("pool_recycle") != 3600
