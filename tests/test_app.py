"""Global tests for the Trixel Lookup Server app."""

from http import HTTPStatus

import pytest
from conftest import client


@pytest.mark.order(100)
def test_ping():
    """Test ping endpoint."""
    response = client.get("/ping")
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"ping": "pong"}


@pytest.mark.order(100)
def test_version():
    """Test version endpoint."""
    response = client.get("/version")
    assert response.status_code == HTTPStatus.OK
    assert "version" in response.json()


@pytest.mark.order(101)
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


@pytest.mark.order(102)
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


@pytest.mark.order(103)
def test_update_trixel_sensor_count_combined():
    """Test combined trixel retrieval for previous insertions."""
    response = client.get("/trixel/15/sensor_count")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 2


@pytest.mark.order(104)
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


@pytest.mark.order(105)
def test_get_trixel_list():
    """Test global trixel list retrieval."""
    response = client.get("/trixel")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data[0] == 15

    response = client.put("/trixel/141/sensor_count/ambient_temperature?sensor_count=1")
    assert response.status_code == HTTPStatus.OK, response.text
    response = client.put("/trixel/141/sensor_count/relative_humidity?sensor_count=1")
    assert response.status_code == HTTPStatus.OK, response.text
    response = client.put("/trixel/8/sensor_count/ambient_temperature?sensor_count=1")
    assert response.status_code == HTTPStatus.OK, response.text

    response = client.get("/trixel")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 3
    assert 15 in data
    assert 8 in data
    assert 141 in data

    response = client.get("/trixel?types=relative_humidity")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 2
    assert 15 in data
    assert 141 in data


@pytest.mark.order(106)
def test_get_trixel_list_offset_limit():
    """Test global trixel list retrieval with offset and limits."""
    response = client.get("/trixel?offset=1&limit=1")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 1
    assert 15 in data


@pytest.mark.order(100)
def test_empty_trixel_list(empty_db):
    """Test global trixel retrieval on empty db."""
    response = client.get("/trixel")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 0


@pytest.mark.order(106)
def test_get_sub_trixel_list():
    """Test sub-trixel list retrieval."""
    response = client.get("/trixel/35")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0] == 141


@pytest.mark.order(106)
@pytest.mark.parametrize("id", [37, 566])
def test_non_existent_sub_trixel_list(id: int):
    """Test sub-trixel list retrieval on non existent/empty trixel."""
    response = client.get(f"/trixel/{id}")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 0


@pytest.mark.order(100)
def test_empty_sensor_count(empty_db):
    """Test get sensor_count for empty(undefined) trixel."""
    response = client.get("/trixel/15/sensor_count")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 15
    assert len(data["sensor_counts"]) == 0


@pytest.mark.order(100)
@pytest.mark.parametrize("id", [4, 16, -1, 123])
def test_get_sensor_count_invalid_id(id: int):
    """Test invalid trixel ID on get sensor_count endpoint."""
    response = client.get(f"/trixel/{id}/sensor_count")
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


@pytest.mark.order(100)
@pytest.mark.parametrize("id", [4, 16, -1, 123])
def test_update_trixel_invalid_id(id: int, empty_db):
    """Test invalid trixel id for put/update trixel sensor count endpoint."""
    response = client.put(f"/trixel/{id}/sensor_count/ambient_temperature?sensor_count=4")
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text
