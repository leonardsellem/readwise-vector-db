"""Test database abstraction layer."""

import os
from unittest.mock import AsyncMock, patch

import pytest

from readwise_vector_db.config import DatabaseBackend, DeployTarget, Settings
from readwise_vector_db.db import (
    _ensure_asyncpg_driver,
    database_url,
    get_engine_config,
    get_pool,
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
        # The validation happens at Settings creation time in Pydantic v2
        with pytest.raises(ValueError) as exc_info:
            Settings(
                db_backend=DatabaseBackend.SUPABASE,
                supabase_db_url=None,
            )

        assert "SUPABASE_DB_URL is required" in str(exc_info.value)

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


class TestGetPool:
    """Test asyncpg pool creation."""

    @pytest.mark.asyncio
    async def test_pool_serverless_config(self):
        """Test asyncpg pool configuration for serverless deployment."""
        settings = Settings(
            deploy_target=DeployTarget.VERCEL,
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://user:pass@host:5432/db",
        )

        # Clear any existing pool
        import readwise_vector_db.db

        readwise_vector_db.db._pool = None

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
            "postgresql+asyncpg://user:pass@host:5432/db",
            min_size=0,
            max_size=5,
            command_timeout=30,
        )

    @pytest.mark.asyncio
    async def test_pool_container_config(self):
        """Test asyncpg pool configuration for container deployment."""
        settings = Settings(
            deploy_target=DeployTarget.DOCKER,
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://user:pass@host:5432/db",
        )

        # Clear any existing pool
        import readwise_vector_db.db

        readwise_vector_db.db._pool = None

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
            "postgresql+asyncpg://user:pass@host:5432/db",
            min_size=2,
            max_size=10,
            command_timeout=30,
        )

    @pytest.mark.asyncio
    async def test_pool_lazy_initialization(self):
        """Test that pool is only created once (lazy initialization)."""
        settings = Settings(
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://user:pass@host:5432/db",
        )

        # Clear any existing pool
        import readwise_vector_db.db

        readwise_vector_db.db._pool = None

        mock_pool = AsyncMock()
        with patch(
            "readwise_vector_db.db.asyncpg.create_pool",
            new_callable=AsyncMock,
            return_value=mock_pool,
        ) as mock_create:
            # First call should create pool
            result1 = await get_pool(settings)
            # Second call should return same pool
            result2 = await get_pool(settings)

        assert result1 == mock_pool
        assert result2 == mock_pool
        # create_pool should only be called once
        mock_create.assert_called_once()


class TestIntegration:
    """Integration tests combining multiple components."""

    def test_supabase_to_vercel_full_flow(self):
        """Test complete configuration flow for Supabase + Vercel deployment."""
        settings = Settings(
            deploy_target=DeployTarget.VERCEL,
            db_backend=DatabaseBackend.SUPABASE,
            supabase_db_url="postgresql://user:pass@proj.supabase.co:5432/postgres",
        )

        # URL generation should work
        url = database_url(settings)
        assert url == "postgresql+asyncpg://user:pass@proj.supabase.co:5432/postgres"

        # Engine config should be optimized for serverless
        config = get_engine_config(settings)
        assert config["pool_size"] == 1
        assert config["max_overflow"] == 4
        assert settings.is_serverless is True

    def test_local_to_docker_full_flow(self):
        """Test complete configuration flow for local database + Docker deployment."""
        settings = Settings(
            deploy_target=DeployTarget.DOCKER,
            db_backend=DatabaseBackend.LOCAL,
            local_db_url="postgresql+asyncpg://postgres:secret@db:5432/readwise",
        )

        # URL generation should work
        url = database_url(settings)
        assert url == "postgresql+asyncpg://postgres:secret@db:5432/readwise"

        # Engine config should be optimized for containers
        config = get_engine_config(settings)
        assert config["pool_size"] == 5
        assert config["max_overflow"] == 10
        assert settings.is_serverless is False
