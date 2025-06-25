"""Test backward compatibility across different deployment configurations.

This test suite ensures that all combinations of DB_BACKEND and DEPLOY_TARGET
work correctly, with special emphasis on preserving the default Docker/local
PostgreSQL path.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest

from readwise_vector_db.config import DatabaseBackend, DeployTarget, Settings


class TestBackwardCompatibility:
    """Test backward compatibility across deployment configurations."""

    @pytest.mark.parametrize(
        "db_backend,deploy_target,should_work,expected_error",
        [
            # ✅ Default Docker + Local PostgreSQL (must always work)
            (DatabaseBackend.LOCAL, DeployTarget.DOCKER, True, None),
            # ✅ Cloud deployment with Supabase
            (DatabaseBackend.SUPABASE, DeployTarget.VERCEL, True, None),
            # ✅ Hybrid: Local PostgreSQL with Vercel (for testing)
            (DatabaseBackend.LOCAL, DeployTarget.VERCEL, True, None),
            # ❌ Invalid: Supabase backend without SUPABASE_DB_URL
            (
                DatabaseBackend.SUPABASE,
                DeployTarget.DOCKER,
                False,
                "SUPABASE_DB_URL is required",
            ),
        ],
    )
    def test_deployment_combinations(
        self, db_backend, deploy_target, should_work, expected_error
    ):
        """Test all valid combinations of DB_BACKEND and DEPLOY_TARGET."""
        env_vars = {
            "DB_BACKEND": db_backend.value,
            "DEPLOY_TARGET": deploy_target.value,
        }

        # ↳ Add required Supabase URL if using Supabase backend
        if db_backend == DatabaseBackend.SUPABASE and should_work:
            env_vars["SUPABASE_DB_URL"] = (
                "postgresql+asyncpg://test:pass@supabase.co:6543/postgres"
            )

        # Temporarily move .env file if we're testing the failure case
        env_backup = None
        if not should_work and expected_error and "SUPABASE_DB_URL" in expected_error:
            if os.path.exists(".env"):
                env_backup = tempfile.NamedTemporaryFile(delete=False)
                shutil.copy2(".env", env_backup.name)
                os.remove(".env")

        try:
            with patch.dict(os.environ, env_vars, clear=True):
                if should_work:
                    # ↳ Should create settings without error
                    settings = Settings()
                    assert settings.db_backend == db_backend
                    assert settings.deploy_target == deploy_target
                else:
                    # ↳ Should raise validation error with expected message
                    with pytest.raises(Exception) as exc_info:
                        Settings()
                    assert expected_error in str(exc_info.value)
        finally:
            # Restore .env file if it was backed up
            if env_backup:
                shutil.copy2(env_backup.name, ".env")
                os.unlink(env_backup.name)

    def test_default_docker_local_postgres_unchanged(self):
        """Ensure the default Docker + local PostgreSQL path still works exactly as before."""
        # ↳ Test with absolutely no environment variables (legacy behavior)
        with patch.dict(os.environ, {}, clear=True):
            settings = Settings()

            # ↳ These are the original default values that must never change
            assert settings.deploy_target == DeployTarget.DOCKER
            assert settings.db_backend == DatabaseBackend.LOCAL
            assert not settings.is_serverless
            assert settings.supabase_db_url is None

    def test_explicit_docker_local_configuration(self):
        """Test explicitly setting Docker + local config (should match defaults)."""
        env_vars = {
            "DEPLOY_TARGET": "docker",
            "DB_BACKEND": "local",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.deploy_target == DeployTarget.DOCKER
            assert settings.db_backend == DatabaseBackend.LOCAL
            assert not settings.is_serverless

    def test_vercel_requires_supabase_best_practice(self):
        """Test that Vercel + Supabase is the recommended cloud combination."""
        env_vars = {
            "DEPLOY_TARGET": "vercel",
            "DB_BACKEND": "supabase",
            "SUPABASE_DB_URL": "postgresql+asyncpg://postgres:pass@db.abc123.supabase.co:6543/postgres",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()

            assert settings.deploy_target == DeployTarget.VERCEL
            assert settings.db_backend == DatabaseBackend.SUPABASE
            assert settings.is_serverless
            assert settings.supabase_db_url is not None

    def test_fail_fast_behavior_supabase_missing_url(self):
        """Test that missing SUPABASE_DB_URL fails immediately with clear error."""
        env_vars = {
            "DB_BACKEND": "supabase",
            # ↳ Intentionally missing SUPABASE_DB_URL
        }

        with patch.dict(os.environ, env_vars, clear=True):
            with pytest.raises(Exception) as exc_info:
                Settings()

            # ↳ Error should be clear and actionable
            error_msg = str(exc_info.value)
            assert "SUPABASE_DB_URL is required" in error_msg

    def test_environment_variable_case_insensitivity(self):
        """Test that environment variable names are case insensitive (values must match enum case)."""
        test_cases = [
            # Different environment variable name cases (values must be exact enum values)
            {"deploy_target": "docker", "db_backend": "local"},  # lowercase names
            {"DEPLOY_TARGET": "docker", "DB_BACKEND": "local"},  # uppercase names
            {"Deploy_Target": "docker", "Db_Backend": "local"},  # mixed case names
        ]

        for env_vars in test_cases:
            with patch.dict(os.environ, env_vars, clear=True):
                settings = Settings()
                assert settings.deploy_target == DeployTarget.DOCKER
                assert settings.db_backend == DatabaseBackend.LOCAL

    def test_hybrid_deployment_scenarios(self):
        """Test hybrid deployment scenarios that might be used in development."""
        # ↳ Scenario 1: Vercel + Local PostgreSQL (for testing Vercel builds locally)
        env_vars = {
            "DEPLOY_TARGET": "vercel",
            "DB_BACKEND": "local",
            "LOCAL_DB_URL": "postgresql+asyncpg://localhost:5432/test",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.deploy_target == DeployTarget.VERCEL
            assert settings.db_backend == DatabaseBackend.LOCAL
            assert settings.is_serverless  # ↳ Vercel is always serverless

        # ↳ Scenario 2: Docker + Supabase (for local API with cloud DB)
        env_vars = {
            "DEPLOY_TARGET": "docker",
            "DB_BACKEND": "supabase",
            "SUPABASE_DB_URL": "postgresql+asyncpg://postgres:pass@supabase.co:6543/postgres",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            settings = Settings()
            assert settings.deploy_target == DeployTarget.DOCKER
            assert settings.db_backend == DatabaseBackend.SUPABASE
            assert not settings.is_serverless  # ↳ Docker is not serverless

    def test_production_ready_configurations(self):
        """Test configurations that are production-ready."""
        production_configs = [
            # Traditional Docker deployment
            {
                "env": {
                    "DEPLOY_TARGET": "docker",
                    "DB_BACKEND": "local",
                    "LOCAL_DB_URL": "postgresql+asyncpg://user:pass@db:5432/readwise",
                },
                "expected": {
                    "deploy_target": DeployTarget.DOCKER,
                    "db_backend": DatabaseBackend.LOCAL,
                    "is_serverless": False,
                },
            },
            # Modern serverless deployment
            {
                "env": {
                    "DEPLOY_TARGET": "vercel",
                    "DB_BACKEND": "supabase",
                    "SUPABASE_DB_URL": "postgresql+asyncpg://postgres:pass@db.proj.supabase.co:6543/postgres",
                },
                "expected": {
                    "deploy_target": DeployTarget.VERCEL,
                    "db_backend": DatabaseBackend.SUPABASE,
                    "is_serverless": True,
                },
            },
        ]

        for config in production_configs:
            with patch.dict(os.environ, config["env"], clear=True):
                settings = Settings()

                for key, expected_value in config["expected"].items():
                    actual_value = getattr(settings, key)
                    assert (
                        actual_value == expected_value
                    ), f"Config {config['env']}: {key} = {actual_value}, expected {expected_value}"
