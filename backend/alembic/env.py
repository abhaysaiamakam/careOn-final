import os
import sys
from logging.config import fileConfig

from sqlalchemy import create_engine, engine_from_config
from sqlalchemy import pool

from alembic import context
from geoalchemy2 import alembic_helpers

# Ensure app package is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base, DATABASE_URL, normalize_database_url
import app.models  # ensure models are registered

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set database URL dynamically from environment with full Psycopg 3 normalization
# Escape % to %% to prevent configparser.InterpolationSyntaxError on URL-encoded passwords
raw_target_url = os.getenv("DATABASE_URL", DATABASE_URL)
target_url = normalize_database_url(raw_target_url)
config.set_main_option("sqlalchemy.url", target_url.replace("%", "%%"))

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=alembic_helpers.include_object,
        process_revision_directives=alembic_helpers.writer,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    # Ensure PostGIS in Supabase 'extensions' schema is in search_path during migrations
    connect_args = {}
    if target_url.startswith("postgresql"):
        search_path = os.getenv("DB_SEARCH_PATH", "public,extensions")
        connect_args["options"] = f"-c search_path={search_path}"
        if ":6543" in target_url or os.getenv("DB_PREPARE_THRESHOLD", "").lower() in ("none", "null", "false"):
            connect_args["prepare_threshold"] = None
        if os.getenv("DB_SSLMODE"):
            connect_args["sslmode"] = os.getenv("DB_SSLMODE")

    connectable = create_engine(
        target_url,
        poolclass=pool.NullPool,
        connect_args=connect_args,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=alembic_helpers.include_object,
            process_revision_directives=alembic_helpers.writer,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
