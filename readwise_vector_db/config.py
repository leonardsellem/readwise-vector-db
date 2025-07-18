"""Configuration settings for readwise-vector-db."""

from enum import Enum
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class DeployTarget(str, Enum):
    """Deployment target environment."""

    DOCKER = "docker"
    VERCEL = "vercel"


class DatabaseBackend(str, Enum):
    """Database backend selection."""

    LOCAL = "local"
    SUPABASE = "supabase"


class Settings(BaseSettings):  # type: ignore[misc]
    """Application settings loaded from environment variables or .env files."""

    # Deployment configuration
    deploy_target: DeployTarget = Field(
        default=DeployTarget.DOCKER, description="Deployment target: docker or vercel"
    )

    # Database configuration
    db_backend: DatabaseBackend = Field(
        default=DatabaseBackend.LOCAL, description="Database backend: local or supabase"
    )

    # Database URLs
    local_db_url: Optional[str] = Field(
        default=None, description="Local PostgreSQL database URL"
    )

    supabase_db_url: Optional[str] = Field(
        default=None, description="Supabase PostgreSQL database URL"
    )

    # API Keys
    openai_api_key: Optional[str] = Field(
        default=None, description="OpenAI API key for embeddings"
    )

    # Derived properties
    @property
    def is_serverless(self) -> bool:
        """Check if running in serverless environment."""
        return self.deploy_target == DeployTarget.VERCEL

    @field_validator("supabase_db_url")
    @classmethod
    def validate_supabase_config(cls, v, info):
        """Validate Supabase configuration when using Supabase backend."""
        # Check if db_backend is available in the validation context
        data = info.data if info.data else {}
        db_backend = data.get("db_backend")

        # If db_backend is SUPABASE and supabase_db_url is missing, raise error
        if db_backend == DatabaseBackend.SUPABASE and not v:
            raise ValueError(
                "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'"
            )
        return v

    # Add model validator to catch cases where field validator doesn't work
    @classmethod
    def __pydantic_init_subclass__(cls, **kwargs):
        super().__pydantic_init_subclass__(**kwargs)

    def model_post_init(self, __context) -> None:
        """Post-initialization validation."""
        if self.db_backend == DatabaseBackend.SUPABASE and not self.supabase_db_url:
            raise ValueError(
                "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'"
            )

    model_config = {
        # ↳ Load from .env files and environment variables
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        # ↳ Allow loading from Vercel/Supabase project secrets
        "env_prefix": "",
        # ↳ Allow extra environment variables (backward compatibility)
        "extra": "ignore",
    }


# Global settings instance
settings = Settings()
