"""Database and session preset configuration."""

import os

from sqlalchemy import URL, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Prefer custom DB definition over custom (partial) definition over default
DATABASE_URL = os.getenv("TLS_CUSTOM_DB_URL")

if DATABASE_URL is None and os.getenv("TLS_DB_DIALECT") is not None:
    DATABASE_URL = URL.create(
        os.getenv("TLS_DB_DIALECT", ""),
        username=os.getenv("TLS_DB_USER", ""),
        password=os.getenv("TLS_DB_PASSWORD", ""),
        host=os.getenv("TLS_DB_HOST", ""),
        database=os.getenv("TLS_DB_DBNAME", ""),
    )


# Default local sqlite
connect_args = {}
if DATABASE_URL is None:
    DATABASE_URL = "sqlite:///./tls_sqlite.db"
    connect_args = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, connect_args=connect_args)

MetaSession = sessionmaker(autoflush=False, autocommit=False, bind=engine)

Base = declarative_base()


def get_db():
    """Instantiate a temporary session for endpoint invocation."""
    db = MetaSession()
    try:
        yield db
    finally:
        db.close()


def except_columns(base, *exclusions: str) -> list[str]:
    """Get a list of column names except the ones provided.

    :param base: model from which columns are retrieved
    :param exclusions: list of column names which should be excluded
    :returns: list of column names which are not present in the exclusions
    """
    return [c for c in base.__table__.c if c.name not in exclusions]
