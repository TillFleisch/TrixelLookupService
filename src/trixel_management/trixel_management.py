"""Endpoints related to Trixel Management servers."""

import os
from datetime import datetime, timezone
from http import HTTPStatus
from typing import Annotated

import jwt
import requests
from fastapi import APIRouter, Depends, Header, HTTPException, Path, Query
from pydantic import NonNegativeInt
from requests.exceptions import SSLError
from sqlalchemy.ext.asyncio import AsyncSession

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


async def verify_tms_token(
    token: Annotated[str, Header(description="TMS authentication token.")],
    db: AsyncSession = Depends(get_db),
) -> int:
    """
    Dependency which adds the token header attribute for TMS authentication and performs validation.

    :returns: TMS ID of the valid token
    :raises PermissionError: if the provided token is invalid
    """
    try:
        tms_id = await crud.verify_tms_token(db, jwt_token=token)
        return tms_id
    except PermissionError:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid TMS authentication token!")


@router.get(
    "",
    name="Get TMS IDs.",
    summary="Get a list of all registered trixel management server IDs.",
    tags=[TAG_TMS],
)
async def get_tms_list(
    active: Annotated[bool | None, Query(description="Filters results by the TMS state.")] = None,
    limit: Annotated[NonNegativeInt, Query(description="Limits the number of results.")] = 100,
    offset: Annotated[NonNegativeInt, Query(description="Skip the first n results.")] = 0,
    db: AsyncSession = Depends(get_db),
) -> list[int]:
    """Get a list of all registered trixel management server IDs."""
    return await crud.get_tms_list(db, active=active, limit=limit, offset=offset)


@router.get(
    "/delegations",
    name="Get all delegations",
    summary="Get a list of all delegations",
    tags=[TAG_TMS],
)
async def get_delegations(
    limit: Annotated[NonNegativeInt, Query(description="Limits the number of results.")] = 100,
    offset: Annotated[NonNegativeInt, Query(description="Skip the first n results.")] = 0,
    db: AsyncSession = Depends(get_db),
) -> list[schema.TMSDelegation]:
    """Get a list of all delegations."""
    return await crud.get_all_delegations(db, offset=offset, limit=limit)


@router.get(
    "/{tms_id}",
    name="Get TMS info.",
    summary="Get detailed information about a TMS.",
    tags=[TAG_TMS],
    responses={
        404: {"content": {"application/json": {"example": {"detail": "TMS with the given ID does not exist."}}}},
    },
)
async def get_tms(
    tms_id: Annotated[int, Path(description="ID of the desired TMS.")],
    db: AsyncSession = Depends(get_db),
) -> schema.TrixelManagementServer:
    """Get detailed information about a TMS."""
    if result := await crud.get_tms(db, tms_id=tms_id):
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
    status_code=HTTPStatus.CREATED,
)
async def create_tms(
    host: Annotated[str, Query(description="Address under which the TMS is available.")],
    db: AsyncSession = Depends(get_db),
) -> schema.TrixelManagementServerCreate:
    """
    Add a trixel management server to this trixel lookup server.

    Returns TMS details including the authentication token. Store this token properly, it is only sent once.
    Requires a valid response from the TMS when requesting the /ping endpoint.
    """
    logger.debug("Adding new TMS")
    if len(await crud.get_tms_list(db, active=True)) >= ACTIVE_TMS_LIMIT:
        logger.error("Maximum number of Trixel Management Server reached!")
        raise HTTPException(
            status_code=HTTPStatus.CONFLICT, detail="Maximum number of Trixel Management Servers reached!"
        )

    api_ping_verification(host)
    result = await crud.create_tms(db, host=host)

    # TODO: replace fixed delegation and activation with dynamic trixel allocation and allow multiple TMS.
    update_result = await crud.update_tms(db, id=result.id, active=True)
    await crud.insert_delegations(
        db, tms_id=update_result.id, trixel_ids=[x for x in range(8, 16)]
    )  # Delegate all root nodes

    payload = {"iat": datetime.now(tz=timezone.utc), "tms_id": result.id}
    jwt_token = jwt.encode(payload, result.token_secret, algorithm="HS256")

    logger.debug("Added new TMS with auto-delegations.")
    return schema.TrixelManagementServerCreate(
        id=update_result.id, active=update_result.active, host=update_result.host, token=jwt_token
    )


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
async def update_tms(
    host: Annotated[str, Query(description="New address under which the TMS is available.")],
    tms_id: Annotated[int, Path(description="TMS to which changes apply.")],
    token_tms_id: int = Depends(verify_tms_token),
    db: AsyncSession = Depends(get_db),
) -> schema.TrixelManagementServer:
    """Update the details of the provided TMS."""
    if token_tms_id != tms_id:
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Can only modify own TMS properties.")

    logger.debug("Updating TMS information")
    api_ping_verification(host)
    return await crud.update_tms(db, id=tms_id, host=host)


@router.get(
    "/{tms_id}/delegations",
    name="Get all delegations for the provided TMS",
    summary="Get all delegations for the provided TMS, including other TMSs which manage excluded trixels.",
    tags=[TAG_TMS],
    responses={
        404: {"content": {"application/json": {"example": {"detail": "TMS with the given ID does not exist."}}}},
    },
)
async def get_tms_delegations(
    tms_id: Annotated[int, Path(description="ID of the desired TMS.")],
    db: AsyncSession = Depends(get_db),
) -> list[schema.TMSDelegation]:
    """Get the delegations and exceptions associated with this TMS."""
    try:
        return await crud.get_tms_delegations(db, tms_id=tms_id)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="TMS with the given ID does not exist.")


@router.get(
    "/{tms_id}/validate_token",
    name="Validate TMS Token",
    summary="Check if a TMS authentication token is valid.",
    tags=[TAG_TMS],
    responses={
        401: {"content": {"application/json": {"example": {"detail": "Invalid TMS authentication token!"}}}},
    },
    status_code=HTTPStatus.OK,
)
async def validate_token_tms(
    tms_id: Annotated[int, Path(description="ID of the TMS.")],
    token_tms_id: int = Depends(verify_tms_token),
) -> None:
    """Endpoint which allows to check if a TMS authentication token is valid."""
    if token_tms_id != tms_id:
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Invalid TMS authentication token!")
