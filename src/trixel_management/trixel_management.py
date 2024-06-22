"""Endpoints related to Trixel Management servers."""

import base64
import binascii
import os
from http import HTTPStatus

import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import PositiveInt
from requests.exceptions import SSLError
from sqlalchemy.orm import Session

from database import get_db
from logging_helper import get_logger

from . import crud, schema

TAG_TMS = "Trixel Management Servers"
ACTIVE_TMS_LIMIT = 1

logger = get_logger(__name__)
allow_insecure_tms = os.getenv("TLS_ALLOW_INSECURE_TMS", "False").lower() in ("1", "true")

router = APIRouter(prefix="/TMS", tags=[TAG_TMS])


def api_ping_verification(host: str):
    """
    Verify that the API at the given address responds to pings.

    :param host: The address where the TMS is located
    :raises HTTPException: if the host does not respond with a successful ping
    """
    try:
        # TODO: perform ping asynchronously
        logger.debug("Pinging TMS")
        request = requests.get(f"http{'' if allow_insecure_tms  else 's'}://{host}/ping")
        if not (request.status_code == 200 and request.text == '{"ping":"pong"}'):
            del request
            raise Exception()
        del request
    except SSLError:
        logger.error("TMS Ping unsuccessful (SSL)!")
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail="TMS ping SSL-Error!")
    except Exception:
        logger.error("TMS Ping unsuccessful!")
        raise HTTPException(HTTPStatus.BAD_REQUEST, detail="TMS ping unsuccessful!")
    logger.debug("Ping succeeded!")


@router.get(
    "",
    name="Get TMS IDs.",
    summary="Get a list of all registered trixel management server IDs.",
    tags=[TAG_TMS],
)
def get_tms_list(
    active: bool | None = Query(None, description="Filters results by the TMS state."),
    limit: PositiveInt = Query(100, description="Limits the number of results."),
    offset: PositiveInt = Query(0, description="Skip the first n results."),
    db: Session = Depends(get_db),
) -> list[int]:
    """Get a list of all registered trixel management server IDs."""
    return crud.get_tms_list(db, active=active, limit=limit, offset=offset)


@router.get(
    "/delegations",
    name="Get all delegations",
    summary="Get a list of all delegations",
    tags=[TAG_TMS],
)
def get_delegations(
    limit: PositiveInt = Query(100, description="Limits the number of results."),
    offset: PositiveInt = Query(0, description="Skip the first n results."),
    db: Session = Depends(get_db),
) -> list[schema.TMSDelegation]:
    """Get a list of all delegations."""
    return crud.get_all_delegations(db, offset=offset, limit=limit)


@router.get(
    "/{tms_id}",
    name="Get TMS info.",
    summary="Get detailed information about a TMS.",
    tags=[TAG_TMS],
    responses={
        404: {"content": {"application/json": {"example": {"detail": "TMS with the given ID does not exist."}}}},
    },
)
def get_tms(
    tms_id: int = Path(description="ID of the desired TMS."),
    db: Session = Depends(get_db),
) -> schema.TrixelManagementServer:
    """Get detailed information about a TMS."""
    if result := crud.get_tms(db, tms_id=tms_id):
        return result[0]
    raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="TMS with the given ID does not exist.")


@router.post(
    "",
    name="Add TMS.",
    summary="Add a TMS to this TLS.",
    tags=[TAG_TMS],
    responses={
        409: {
            "content": {
                "application/json": {"example": {"detail": "Maximum number of Trixel Management Servers reached!"}}
            }
        },
        400: {"content": {"application/json": {"example": {"detail": "TMS ping unsuccessful!"}}}},
    },
)
def create_tms(
    host: str = Query(description="Address under which the TMS is available."),
    db: Session = Depends(get_db),
) -> schema.TrixelManagementServerCreate:
    """
    Add a trixel management server to this trixel lookup server.

    Returns TMS details including the authentication token. Store this token properly, it is only sent once.
    Requires a valid response from the TMS when requesting the /ping endpoint.
    """
    logger.debug("Adding new TMS")
    if len(crud.get_tms_list(db, active=True)) >= ACTIVE_TMS_LIMIT:
        logger.error("Maximum number of Trixel Management Server reached!")
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail="Maximum number of Trixel Management Servers reached!"
        )

    api_ping_verification(host)
    result = crud.create_tms(db, host=host)

    # TODO: replace fixed delegation and activation with dynamic trixel allocation and allow multiple TMS.
    result = crud.update_tms(db, id=result.id, active=True)
    crud.insert_delegations(db, tms_id=result.id, trixel_ids=[x for x in range(8, 16)])  # Delegate all root nodes

    logger.debug("Added new TMS with auto-delegations.")
    return result


@router.put(
    "/{tms_id}",
    name="Update TMS details.",
    summary="Update TMS details.",
    tags=[TAG_TMS],
    responses={
        403: {"content": {"application/json": {"example": {"detail": "Can only modify own TMS properties."}}}},
        401: {"content": {"application/json": {"example": {"detail": "Invalid TMS authentication token!"}}}},
        400: {"content": {"application/json": {"example": {"detail": "TMS ping unsuccessful!"}}}},
    },
)
def update_tms(
    host: str = Query(description="New address under which the TMS is available."),
    token: str = Header(description="TMS authentication token."),
    tms_id: int = Path(description="TMS to which changes apply."),
    db: Session = Depends(get_db),
) -> schema.TrixelManagementServer:
    """Update the details of the provided TMS."""
    try:
        id = crud.verify_tms_token(db, token=base64.b64decode(token))

        if id != tms_id:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Can only modify own TMS properties.")

    except (binascii.Error, PermissionError):
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid TMS authentication token!")

    logger.debug("Updating TMS information")
    api_ping_verification(host)
    return crud.update_tms(db, id=tms_id, host=host)


@router.get(
    "/{tms_id}/delegations",
    name="Get all delegations for the provided TMS",
    summary="Get all delegations for the provided TMS, including other TMSs which manage excluded trixels.",
    tags=[TAG_TMS],
    responses={
        404: {"content": {"application/json": {"example": {"detail": "TMS with the given ID does not exist."}}}},
    },
)
def get_tms_delegations(
    tms_id: int = Path(description="ID of the desired TMS."),
    db: Session = Depends(get_db),
) -> list[schema.TMSDelegation]:
    """Get the delegations and exceptions associated with this TMS."""
    try:
        return crud.get_tms_delegations(db, tms_id=tms_id)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="TMS with the given ID does not exist.")
