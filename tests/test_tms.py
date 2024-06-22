"""Test related to Trixel Management Servers."""

import urllib
from http import HTTPStatus

import pytest
import requests_mock
from conftest import client


@pytest.mark.order(200)
def test_post_TMS_unreachable_tms(empty_db):
    """Test adding and unreachable TMS."""
    host = "doener"
    response = client.post(f"/TMS/?{urllib.parse.urlencode({'host':host})}")
    assert response.status_code == HTTPStatus.BAD_REQUEST, response.text


@pytest.mark.order(201)
def test_post_and_update_TMS():
    """Test insertion and update of TMS with valid authentication token."""
    token = None
    with requests_mock.Mocker() as m:
        host = "bread.crumbs.local"
        m.get("https://bread.crumbs.local/ping", text='{"ping":"pong"}')
        response = client.post(f"/TMS/?{urllib.parse.urlencode({'host':host})}")
        assert response.status_code == HTTPStatus.OK, response.text
        data = response.json()
        assert "token" in data
        token = data["token"]
        assert isinstance(data["id"], int)
        assert data["host"] == host

    # Update host information
    new_host = "sausage.dog.local"
    response = client.put(f"/TMS/{data['id']}/?{urllib.parse.urlencode({'host':new_host})}", headers={"token": token})
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["host"] == new_host

    # Update host for other TMS
    new_host = "sausage.dog.local"
    response = client.put(f"/TMS/35/?{urllib.parse.urlencode({'host':new_host})}", headers={"token": token})
    assert response.status_code == HTTPStatus.FORBIDDEN, response.text


@pytest.mark.order(202)
def test_post_invalid_token():
    """Test updating TMS details with invalid token."""
    new_host = "portal.gun.local"
    response = client.put(f"/TMS/1/?{urllib.parse.urlencode({'host':new_host})}", headers={"token": "fake-token"})
    assert response.status_code == HTTPStatus.UNAUTHORIZED, response.text


@pytest.mark.order(202)
def test_put_tms_max_exceeded():
    """Test adding TMS past the max limitation."""
    with requests_mock.Mocker() as m:
        host = "toaster.oven.local"
        m.get("https://toaster.oven.local/ping", text='{"ping":"pong"}')
        response = client.post(f"/TMS/?{urllib.parse.urlencode({'host':host})}")
        assert response.status_code == HTTPStatus.CONFLICT, response.text


@pytest.mark.order(202)
def test_get_tms_list():
    """Test tms overview list retrieval."""
    response = client.get("/TMS")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 1
    assert data[0] == 1

    response = client.get("/TMS?active=false")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 0


@pytest.mark.order(202)
def test_get_tms_detail():
    """Test tms detail retrieval."""
    response = client.get("/TMS/1")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert data["id"] == 1
    assert data["host"] == "sausage.dog.local"


@pytest.mark.order(202)
def test_get_delegations():
    """Test global delegation list retrieval."""
    response = client.get("/TMS/delegations")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 8


@pytest.mark.order(202)
def test_tms_delegation():
    """Test tms specific delegation list retrieval."""
    response = client.get("/TMS/1/delegations")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 8


@pytest.mark.order(200)
def test_get_tms_list_empty(empty_db):
    """Test list retrieval on empty db."""
    response = client.get("/TMS")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 0


@pytest.mark.order(200)
def test_get_tms_detail_empty(empty_db):
    """Test detail retrieval on non-existent id / empty db."""
    response = client.get("/TMS/1")
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text


@pytest.mark.order(200)
def test_get_delegations_empty(empty_db):
    """Test global delegation list on empty db."""
    response = client.get("/TMS/delegations")
    assert response.status_code == HTTPStatus.OK, response.text
    data = response.json()
    assert len(data) == 0


@pytest.mark.order(200)
def test_get_tms_delegation_empty(empty_db):
    """Test delegation retrieval on non-existent id / empty db."""
    response = client.get("/TMS/1/delegations")
    assert response.status_code == HTTPStatus.NOT_FOUND, response.text
