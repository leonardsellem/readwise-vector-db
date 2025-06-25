"""Test configuration settings module."""

import os
import tempfile
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from readwise_vector_db.config import DatabaseBackend, DeployTarget, Settings


class TestSettings:
    """Test the Settings configuration class."""

    def test_default_values(self):
        """Test that default values are set correctly."""
        # ↳ Create settings without any environment variables
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

        assert settings.deploy_target == DeployTarget.DOCKER
        assert settings.db_backend == DatabaseBackend.LOCAL
        assert settings.local_db_url is None
        assert settings.supabase_db_url is None
        assert settings.openai_api_key is None
        assert not settings.is_serverless

    def test_deploy_target_docker(self):
        """Test docker deployment target configuration."""
        with patch.dict(os.environ, {"DEPLOY_TARGET": "docker"}, clear=True):
            settings = Settings()

        assert settings.deploy_target == DeployTarget.DOCKER
        assert not settings.is_serverless

    def test_deploy_target_vercel(self):
        """Test vercel deployment target configuration."""
        with patch.dict(os.environ, {"DEPLOY_TARGET": "vercel"}, clear=True):
            settings = Settings()

        assert settings.deploy_target == DeployTarget.VERCEL
        assert settings.is_serverless

    def test_db_backend_local(self):
        """Test local database backend configuration."""
        with patch.dict(os.environ, {"DB_BACKEND": "local"}, clear=True):
            settings = Settings()

        assert settings.db_backend == DatabaseBackend.LOCAL

    def test_db_backend_supabase_with_url(self):
        """Test supabase backend with required URL."""
        env_vars = {
            "DB_BACKEND": "supabase",
            "SUPABASE_DB_URL": "postgresql+asyncpg://user:pass@host:5432/db",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

        assert settings.db_backend == DatabaseBackend.SUPABASE
        assert settings.supabase_db_url == "postgresql+asyncpg://user:pass@host:5432/db"

    def test_db_backend_supabase_missing_url_raises_error(self):
        """Test that Supabase backend without URL raises validation error."""
        with patch.dict(os.environ, {"DB_BACKEND": "supabase"}, clear=True):
            with pytest.raises(ValidationError) as exc_info:
                Settings()

        error = exc_info.value.errors()[0]
        assert "SUPABASE_DB_URL is required" in str(error["msg"])

    def test_case_insensitive_env_vars(self):
        """Test that environment variables are case insensitive."""
        env_vars = {
            "deploy_target": "vercel",  # lowercase
            "DB_BACKEND": "local",  # uppercase
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

        assert settings.deploy_target == DeployTarget.VERCEL
        assert settings.db_backend == DatabaseBackend.LOCAL

    def test_all_environment_variables(self):
        """Test loading all configuration from environment variables."""
        env_vars = {
            "DEPLOY_TARGET": "vercel",
            "DB_BACKEND": "supabase",
            "LOCAL_DB_URL": "postgresql+asyncpg://localhost:5432/local",
            "SUPABASE_DB_URL": "postgresql+asyncpg://supabase.co:5432/remote",
            "OPENAI_API_KEY": "sk-test-key-123",
        }
        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

        assert settings.deploy_target == DeployTarget.VERCEL
        assert settings.db_backend == DatabaseBackend.SUPABASE
        assert settings.local_db_url == "postgresql+asyncpg://localhost:5432/local"
        assert (
            settings.supabase_db_url == "postgresql+asyncpg://supabase.co:5432/remote"
        )
        assert settings.openai_api_key == "sk-test-key-123"
        assert settings.is_serverless

    def test_dotenv_file_loading(self):
        """Test loading configuration from .env file."""
        # ↳ Create a temporary .env file for testing
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEPLOY_TARGET=vercel\n")
            f.write("DB_BACKEND=local\n")
            f.write("OPENAI_API_KEY=sk-from-file\n")
            env_file = f.name

        try:
            # ↳ Clear environment and test with file
            with patch.dict(os.environ, {}, clear=True):
                settings = Settings(_env_file=env_file)

            assert settings.deploy_target == DeployTarget.VERCEL
            assert settings.db_backend == DatabaseBackend.LOCAL
            assert settings.openai_api_key == "sk-from-file"
        finally:
            os.unlink(env_file)

    def test_env_vars_override_dotenv(self):
        """Test that environment variables take precedence over .env file."""
        # ↳ Create temporary .env file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("DEPLOY_TARGET=docker\n")
            f.write("OPENAI_API_KEY=sk-from-file\n")
            env_file = f.name

        try:
            # ↳ Override with environment variable
            env_vars = {"DEPLOY_TARGET": "vercel"}
            with patch.dict(os.environ, env_vars, clear=True):
                settings = Settings(_env_file=env_file)

            # ↳ Env var should override file
            assert settings.deploy_target == DeployTarget.VERCEL
            # ↳ File value should be used when not overridden
            assert settings.openai_api_key == "sk-from-file"
        finally:
            os.unlink(env_file)


class TestEnums:
    """Test the configuration enums."""

    def test_deploy_target_enum_values(self):
        """Test DeployTarget enum values."""
        assert DeployTarget.DOCKER == "docker"
        assert DeployTarget.VERCEL == "vercel"

    def test_database_backend_enum_values(self):
        """Test DatabaseBackend enum values."""
        assert DatabaseBackend.LOCAL == "local"
        assert DatabaseBackend.SUPABASE == "supabase"
