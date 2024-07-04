"""Pytest configuration, fixtures and db-testing-preamble."""

import asyncio
from typing import Any, AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from crud import init_measurement_type_enum
from database import Base
from trixellookupserver import app, get_db

# Testing preamble based on: https://fastapi.tiangolo.com/advanced/testing-database/
DATABASE_URL = "sqlite+aiosqlite://"

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False})


TestingSessionLocal = async_sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False, bind=engine)


async def override_get_db() -> AsyncGenerator[AsyncSession, Any]:
    """Instantiate a temporary session for endpoint invocation."""
    async with TestingSessionLocal() as db:
        yield db


@pytest.fixture(scope="function", name="db")
async def get_db_session():
    """Get a database session which can be used in tests."""
    async for db in override_get_db():
        return db


async def reset_db():
    """Drop all tables within the DB and re-instantiates the model."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)


def prepare_db():
    """Set up empty temporary test database."""
    loop = asyncio.get_event_loop()
    loop.run_until_complete(reset_db())

    TestingSessionLocal = async_sessionmaker(autoflush=False, autocommit=False, expire_on_commit=False, bind=engine)

    async def override_get_db() -> AsyncGenerator[AsyncSession, Any]:
        """Override the default database session retrieval with the test environment db."""
        async with TestingSessionLocal() as db:
            yield db

    app.dependency_overrides[get_db] = override_get_db

    async def init_enums():
        """Initialize/synchronize enum tables within the DB."""
        async for db in override_get_db():
            await init_measurement_type_enum(db)

    loop.run_until_complete(init_enums())


@pytest.fixture(scope="function")
def empty_db():
    """Reset the test database before test execution."""
    prepare_db()
    yield


prepare_db()
client = TestClient(app)
