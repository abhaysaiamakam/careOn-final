import os
import re
import logging
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

logger = logging.getLogger("careon.database")


def normalize_database_url(url: str) -> str:
    """
    Ensure correct driver prefix for PostgreSQL (psycopg 3).
    PostgreSQL URLs without driver (postgres:// or postgresql://) or with psycopg2
    are normalized to postgresql+psycopg://.
    """
    if url.startswith("postgres://"):
        return re.sub(r"^postgres://", "postgresql+psycopg://", url)
    if url.startswith("postgresql+psycopg2://"):
        return re.sub(r"^postgresql\+psycopg2://", "postgresql+psycopg://", url)
    if url.startswith("postgresql://") and not url.startswith("postgresql+"):
        return re.sub(r"^postgresql://", "postgresql+psycopg://", url)
    return url


# Environment-based DATABASE_URL configuration
# Default to PostgreSQL local socket; falls back gracefully to sqlite if specified
RAW_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg:///careon")
DATABASE_URL = normalize_database_url(RAW_DATABASE_URL)


def get_engine_args(url: str) -> dict:
    engine_args = {}
    if url.startswith("sqlite"):
        engine_args["connect_args"] = {"check_same_thread": False}
    else:
        # PostgreSQL connection pooling configuration
        engine_args["pool_size"] = int(os.getenv("DB_POOL_SIZE", "10"))
        engine_args["max_overflow"] = int(os.getenv("DB_MAX_OVERFLOW", "20"))
        engine_args["pool_timeout"] = int(os.getenv("DB_POOL_TIMEOUT", "30"))
        engine_args["pool_recycle"] = int(os.getenv("DB_POOL_RECYCLE", "1800"))
        engine_args["pool_pre_ping"] = True

        connect_args = {}
        # PostGIS schema support (Supabase installs PostGIS in the 'extensions' schema)
        search_path = os.getenv("DB_SEARCH_PATH", "public,extensions")
        connect_args["options"] = f"-c search_path={search_path}"

        # PgBouncer / Transaction pooler compatibility (e.g. Supabase port 6543)
        # In transaction pooling mode, automatic prepared statements can collide across connections.
        prep_threshold_env = os.getenv("DB_PREPARE_THRESHOLD")
        if prep_threshold_env is not None:
            connect_args["prepare_threshold"] = None if prep_threshold_env.lower() in ("none", "null", "false", "0") else int(prep_threshold_env)
        elif ":6543" in url:
            # Standard Supabase PgBouncer transaction pooler port
            connect_args["prepare_threshold"] = None

        sslmode_env = os.getenv("DB_SSLMODE")
        if sslmode_env:
            connect_args["sslmode"] = sslmode_env

        engine_args["connect_args"] = connect_args
    return engine_args


# Ensure directory exists if SQLite file path is specified
if DATABASE_URL.startswith("sqlite:///"):
    db_path = DATABASE_URL.replace("sqlite:///", "")
    if db_path.startswith("/"):
        dir_name = os.path.dirname(db_path)
    else:
        dir_name = os.path.dirname(os.path.abspath(db_path))
    if dir_name and not os.path.exists(dir_name):
        try:
            os.makedirs(dir_name, exist_ok=True)
        except OSError:
            pass

engine = create_engine(DATABASE_URL, **get_engine_args(DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def is_postgres(target_engine=None) -> bool:
    eng = target_engine or engine
    return eng.dialect.name == "postgresql"


def is_sqlite(target_engine=None) -> bool:
    eng = target_engine or engine
    return eng.dialect.name == "sqlite"


def check_db_connection(target_engine=None) -> bool:
    """Safe check for database connectivity that will not crash application startup."""
    eng = target_engine or engine
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
            return True
    except Exception as exc:
        logger.warning(f"Database connection check failed: {exc}")
        return False


def get_db() -> Generator[Session, None, None]:
    """Dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
