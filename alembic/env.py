import os
from logging.config import fileConfig

from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from alembic import context
from readwise_vector_db.config import DatabaseBackend, settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Load environment variables from .env file
load_dotenv()


def get_database_url() -> str:
    """Get database URL using the unified config system."""
    if settings.db_backend == DatabaseBackend.SUPABASE:
        if not settings.supabase_db_url:
            raise ValueError(
                "SUPABASE_DB_URL is required when DB_BACKEND is 'supabase'. "
                "Please set the environment variable."
            )
        return settings.supabase_db_url
    else:
        # Local backend
        if settings.local_db_url:
            return settings.local_db_url
        else:
            # Fallback to environment variables for backward compatibility
            pg_user = os.environ.get("POSTGRES_USER", "postgres")
            pg_password = os.environ.get("POSTGRES_PASSWORD", "postgres")
            pg_db = os.environ.get("POSTGRES_DB", "readwise")
            return f"postgresql://{pg_user}:{pg_password}@localhost:5432/{pg_db}"


# Add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from readwise_vector_db.models.highlight import Highlight  # noqa
from readwise_vector_db.models.sync_state import SyncState  # noqa

target_metadata = SQLModel.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = get_database_url()  # Use unified config system
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    configuration = config.get_section(config.config_ini_section)

    # Override the URL with our unified config system
    # ↳ This ensures consistency with the main application
    configuration["sqlalchemy.url"] = get_database_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
