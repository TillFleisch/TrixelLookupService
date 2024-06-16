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
