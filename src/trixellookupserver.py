"""Entry point for the Trixel Lookup Service API."""

import importlib
from contextlib import asynccontextmanager
from http import HTTPStatus
from typing import Annotated, List

import packaging.version
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from pydantic import NonNegativeInt
from sqlalchemy.ext.asyncio import AsyncSession

import crud
import model
import schema
from database import engine, get_db
from schema import Ping, Version
from trixel_management.schema import TrixelManagementServer
from trixel_management.trixel_management import TAG_TMS
from trixel_management.trixel_management import router as trixel_management_router
from trixel_management.trixel_management import verify_tms_token

TAG_TRIXEL_INFO = "Trixel Information"

openapi_tags = [
    {"name": TAG_TRIXEL_INFO},
    {"name": TAG_TMS},
]

api_version = importlib.metadata.version("trixellookupserver")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan actions executed before and after FastAPI."""
    async with engine.begin() as conn:
        await conn.run_sync(model.Base.metadata.create_all)
    async for db in get_db():
        await crud.init_measurement_type_enum(db)

    yield


app = FastAPI(
    title="Trixel Lookup Service",
    summary="""Manages Trixel Managements Servers (TMS) and their Trixel ID responsibilities.
               Coordinates initial communication to determine the correct TMS for a contributor.""",
    version=api_version,
    root_path=f"/v{packaging.version.Version(api_version).major}",
    openapi_tags=openapi_tags,
    lifespan=lifespan,
)
app.include_router(trixel_management_router)


@app.get(
    "/ping",
    name="Ping",
    summary="ping ... pong",
)
def ping() -> Ping:
    """Return a basic ping message."""
    return Ping()


@app.get(
    "/version",
    name="Version",
    summary="Get the precise current semantic version.",
)
def get_semantic_version() -> Version:
    """Get the precise version of the currently running API."""
    return Version(version=api_version)


@app.get(
    "/trixel",
    name="Get all trixels which have registered sensors.",
    summary="Retrieve an overview of all trixels, which contain at least one sensors of the specified types.",
    tags=[TAG_TRIXEL_INFO],
    responses={
        400: {"content": {"application/json": {"example": {"detail": "Invalid trixel id!"}}}},
    },
)
async def get_trixel_list(
    types: Annotated[
        List[model.MeasurementTypeEnum],
        Query(
            description="List of measurement types which restrict results. If none are provided, all types are used."
        ),
    ] = None,
    limit: Annotated[NonNegativeInt, Query(description="Limits the number of results.")] = 100,
    offset: Annotated[NonNegativeInt, Query(description="Skip the first n results.")] = 0,
    db: AsyncSession = Depends(get_db),
) -> list[int]:
    """Get a list of trixel ids with at least one sensor (filtered by measurement type)."""
    try:
        return await crud.get_trixel_ids(db, types=types, limit=limit, offset=offset)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


@app.get(
    "/trixel/{trixel_id}",
    name="Get sub-trixels which have registered sensors.",
    summary="Retrieve an overview of sub-trixels which contain at least one sensors of the specified types.",
    tags=[TAG_TRIXEL_INFO],
    responses={
        400: {"content": {"application/json": {"example": {"detail": "Invalid trixel id!"}}}},
    },
)
async def get_sub_trixel_list(
    trixel_id: Annotated[int, Path(description="Root trixel which makes up the search space for sub-trixels.")],
    types: Annotated[
        List[model.MeasurementTypeEnum],
        Query(
            description="List of measurement types which restrict results. If none are provided, all types are used."
        ),
    ] = None,
    limit: Annotated[NonNegativeInt, Query(description="Limits the number of results.")] = 100,
    offset: Annotated[NonNegativeInt, Query(description="Skip the first n results.")] = 0,
    db: AsyncSession = Depends(get_db),
) -> list[int]:
    """Get a list of sub-trixel ids with at least one sensor (filtered by measurement type)."""
    try:
        return await crud.get_trixel_ids(db, trixel_id=trixel_id, types=types, limit=limit, offset=offset)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


@app.get(
    "/trixel/{trixel_id}/sensor_count",
    name="Get trixel sensor count",
    summary="Get the sensor count within a trixel per measurement type.",
    tags=[TAG_TRIXEL_INFO],
    responses={
        400: {"content": {"application/json": {"example": {"detail": "Invalid trixel id!"}}}},
    },
)
async def get_trixel_info(
    trixel_id: Annotated[int, Path(description="The id of the trixel for which the sensor count is to be determined.")],
    types: Annotated[
        List[model.MeasurementTypeEnum],
        Query(
            description="List of measurement types which restrict results. If none are provided, all types are used."
        ),
    ] = None,
    db: AsyncSession = Depends(get_db),
) -> schema.TrixelMap:
    """Get the sensor count for a trixel for different measurement types."""
    try:
        results = await crud.get_trixel_map(db, trixel_id, types)

        sensor_counts = dict()
        for trixel_map in results or []:
            sensor_counts[trixel_map.type_id] = trixel_map.sensor_count

        return schema.TrixelMap(id=trixel_id, sensor_counts=sensor_counts)

    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


@app.put(
    "/trixel/{trixel_id}/sensor_count/{type}",
    name="Update trixel count",
    summary="Update the sensor count for a given trixel and type.",
    tags=[TAG_TRIXEL_INFO],
    responses={
        400: {"content": {"application/json": {"example": {"detail": "Invalid trixel id!"}}}},
        403: {"content": {"application/json": {"example": {"detail": "Can only modify own TMS properties."}}}},
        401: {"content": {"application/json": {"example": {"detail": "Invalid TMS authentication token!"}}}},
    },
)
async def update_trixel_sensor_count(
    trixel_id: Annotated[int, Path(description="The Trixel id for which the sensor count is updated.")],
    type: Annotated[
        model.MeasurementTypeEnum, Path(description="Type of measurement for which the sensor count is updated.")
    ],
    sensor_count: Annotated[int, Query(description="The new number of sensors for the given type within the trixel.")],
    token_tms_id: int = Depends(verify_tms_token),
    db: AsyncSession = Depends(get_db),
) -> schema.TrixelMapUpdate:
    """Update (or insert new) trixel sensor count within the DB."""
    try:
        owner = await crud.get_responsible_tms(db, trixel_id=trixel_id)
        if owner is None or owner.id != token_tms_id:
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Can only modify own TMS properties.")

        return await crud.upsert_trixel_map(db, trixel_id=trixel_id, type_=type, sensor_count=sensor_count)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


@app.put(
    "/trixel/sensor_count/{type}",
    name="Batch update trixel count",
    summary="Update the sensor count for multiple trixels for a given type.",
    tags=[TAG_TRIXEL_INFO],
    responses={
        400: {"content": {"application/json": {"example": {"detail": "Invalid trixel id!"}}}},
        403: {"content": {"application/json": {"example": {"detail": "Can only modify own TMS properties."}}}},
        401: {"content": {"application/json": {"example": {"detail": "Invalid TMS authentication token!"}}}},
    },
)
async def batch_update_trixel_sensor_count(
    type: Annotated[
        model.MeasurementTypeEnum, Path(description="Type of measurement for which the sensor count is updated.")
    ],
    updates: schema.BatchSensorMapUpdate,
    token_tms_id: int = Depends(verify_tms_token),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Update (or insert new) multiple trixel sensor counts within the DB."""
    try:
        if not await crud.does_tms_own_trixels(db, tms_id=token_tms_id, trixel_ids=updates.keys()):
            raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Can only change delegated trixels!")

        await crud.batch_upsert_trixel_map(db, updates=updates, type_=type)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


@app.get(
    "/trixel/{trixel_id}/TMS",
    name="Get TMS which manages the trixel.",
    summary="Get the TMS responsible for a specific trixel.",
    tags=[TAG_TRIXEL_INFO],
    responses={
        400: {"content": {"application/json": {"example": {"detail": "Invalid trixel id!"}}}},
        404: {"content": {"application/json": {"example": {"detail": "No responsible TMS found!"}}}},
    },
)
async def get_responsible_tms(
    trixel_id: Annotated[int, Path(description="The Trixel id for which the TMS is determined.")],
    db: AsyncSession = Depends(get_db),
) -> TrixelManagementServer:
    """Get the TMS responsible for a Trixel."""
    try:
        if (result := await crud.get_responsible_tms(db, trixel_id=trixel_id)) is not None:
            return result
        else:
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="No responsible TMS found!")

    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


def main() -> None:
    """Entry point for cli module invocations."""
    uvicorn.main("trixellookupserver:app")


if __name__ == "__main__":
    main()
