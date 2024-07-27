"""Database and session preset configuration."""

import os
from typing import Any, AsyncGenerator

from sqlalchemy import URL, event
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

# Prefer custom DB definition over custom (partial) definition over default
DATABASE_URL = os.getenv("TLS_CUSTOM_DB_URL")

if DATABASE_URL is None and os.getenv("TLS_DB_DIALECT") is not None:
    DATABASE_URL = URL.create(
        os.getenv("TLS_DB_DIALECT", ""),
        username=os.getenv("TLS_DB_USER", None),
        password=os.getenv("TLS_DB_PASSWORD", None),
        host=os.getenv("TLS_DB_HOST", None),
        port=os.getenv("TLS_DB_PORT", None),
        database=os.getenv("TLS_DB_DBNAME", None),
    )


# Default local sqlite
connect_args = {}
if DATABASE_URL is None:
    DATABASE_URL = "sqlite+aiosqlite:///./tls_sqlite.db"
    connect_args = {"check_same_thread": False}

use_sqlite = "sqlite" in DATABASE_URL

engine = create_async_engine(DATABASE_URL, connect_args=connect_args)

MetaSession = async_sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False, bind=engine)

Base = declarative_base()


# source: https://docs.sqlalchemy.org/en/20/dialects/sqlite.html#sqlite-foreign-keys
@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Explicitly enable foreign key support (required for cascades)."""
    if use_sqlite:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


async def get_db() -> AsyncGenerator[AsyncSession, Any]:
    """Instantiate a temporary session for endpoint invocation."""
    async with MetaSession() as db:
        yield db


def except_columns(base, *exclusions: str) -> list[str]:
    """Get a list of column names except the ones provided.

    :param base: model from which columns are retrieved
    :param exclusions: list of column names which should be excluded
    :returns: list of column names which are not present in the exclusions
    """
    return [c for c in base.__table__.c if c.name not in exclusions]
