"""Global tests for the Trixel Lookup Server app."""

from http import HTTPStatus

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base
from trixellookupserver import app, get_db

# Testing preamble based on: https://fastapi.tiangolo.com/advanced/testing-database/
DATABASE_URL = "sqlite://"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


def override_get_db():
    """Override the default database session retrieval with the test environment db."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def empty_db():
    """Reset the test database before test execution."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


def test_ping():
    """Test ping endpoint."""
    response = client.get("/ping")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"ping": "pong"}


def test_version():
    """Test version endpoint."""
    response = client.get("/version")
    assert response.status_code == HTTPStatus.OK
    assert "version" in response.json()


@pytest.mark.order(1)
def test_update_trixel_sensor_count_temperature(empty_db):
    """Test trixel update/insertion for temperature."""
    response = client.put("/trixel/15/sensor_count/ambient_temperature?sensor_count=3")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15

    response = client.get("/trixel/15/sensor_count?types=ambient_temperature")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 1
    assert "ambient_temperature" in data["sensor_counts"]
    assert data["sensor_counts"]["ambient_temperature"] == 3


@pytest.mark.order(2)
def test_update_trixel_sensor_count_humidity():
    """Test trixel update/insertion for relative humidity."""
    response = client.put("/trixel/15/sensor_count/relative_humidity?sensor_count=4")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15

    response = client.get("/trixel/15/sensor_count?types=relative_humidity")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 1
    assert "relative_humidity" in data["sensor_counts"]
    assert data["sensor_counts"]["relative_humidity"] == 4


@pytest.mark.order(3)
def test_update_trixel_sensor_count_combined():
    """Test combined trixel retrieval for previous insertions."""
    response = client.get("/trixel/15/sensor_count")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 2


@pytest.mark.order(4)
def test_update_trixel_sensor_count_overwrite():
    """Test update to existing trixel from previous insertions."""
    response = client.put("/trixel/15/sensor_count/ambient_temperature?sensor_count=8")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15

    response = client.get("/trixel/15/sensor_count?types=ambient_temperature")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 1
    assert "ambient_temperature" in data["sensor_counts"]
    assert data["sensor_counts"]["ambient_temperature"] == 8


def test_empty_sensor_count(empty_db):
    """Test get sensor_count for empty(undefined) trixel."""
    response = client.get("/trixel/15/sensor_count")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 0


@pytest.mark.parametrize("id", [4, 16, -1, 123])
def test_get_sensor_count_invalid_id(id: int):
    """Test invalid trixel ID on get sensor_count endpoint."""
    response = client.get(f"/trixel/{id}/sensor_count")
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


@pytest.mark.parametrize("id", [4, 16, -1, 123])
def test_update_trixel_invalid_id(id: int, empty_db):
    """Test invalid trixel id for put/update trixel sensor count endpoint."""
    response = client.put(f"/trixel/{id}/sensor_count/ambient_temperature?sensor_count=4")
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
