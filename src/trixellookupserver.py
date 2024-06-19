"""Entry point for the Trixel Lookup Service API."""

import importlib
from http import HTTPStatus
from typing import Annotated, List

import packaging.version
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Path, Query
from pydantic import PositiveInt
from sqlalchemy.orm import Session

import crud
import model
import schema
from database import engine, get_db
from schema import Ping, Version
from trixel_management.trixel_management import TAG_TMS
from trixel_management.trixel_management import router as trixel_management_router

TAG_TRIXEL_INFO = "Trixel Information"

openapi_tags = [
    {"name": TAG_TRIXEL_INFO},
    {"name": TAG_TMS},
]

api_version = importlib.metadata.version("trixellookupserver")

model.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Trixel Lookup Service",
    summary="""Manages Trixel Managements Servers (TMS) and their Trixel ID responsibilities.
               Coordinates initial communication to determine the correct TMS for a contributor.""",
    version=api_version,
    root_path=f"/v{packaging.version.Version(api_version).major}",
    openapi_tags=openapi_tags,
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
def get_trixel_list(
    types: Annotated[
        List[model.MeasurementType],
        Query(
            description="List of measurement types which restrict results. If none are provided, all types are used."
        ),
    ] = None,
    limit: PositiveInt = Query(100, description="Limits the number of results."),
    offset: PositiveInt = Query(0, description="Skip the first n results."),
    db: Session = Depends(get_db),
) -> list[int]:
    """Get a list of trixel ids with at least one sensor (filtered by measurement type)."""
    try:
        return crud.get_trixel_ids(db, types=types, limit=limit, offset=offset)
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
def get_sub_trixel_list(
    trixel_id: int = Path(description="Root trixel which makes up the search space for sub-trixels."),
    types: Annotated[
        List[model.MeasurementType],
        Query(
            description="List of measurement types which restrict results. If none are provided, all types are used."
        ),
    ] = None,
    limit: PositiveInt = Query(100, description="Limits the number of results."),
    offset: PositiveInt = Query(0, description="Skip the first n results."),
    db: Session = Depends(get_db),
) -> list[int]:
    """Get a list of sub-trixel ids with at least one sensor (filtered by measurement type)."""
    try:
        return crud.get_trixel_ids(db, trixel_id=trixel_id, types=types, limit=limit, offset=offset)
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
def get_trixel_info(
    trixel_id: int = Path(description="The id of the trixel for which the sensor count is to be determined."),
    types: Annotated[
        List[model.MeasurementType],
        Query(
            description="List of measurement types which restrict results. If none are provided, all types are used."
        ),
    ] = None,
    db: Session = Depends(get_db),
) -> schema.TrixelMap:
    """Get the sensor count for a trixel for different measurement types."""
    try:
        results = crud.get_trixel_map(db, trixel_id, types)

        sensor_counts = dict()
        for trixel_map in results or []:
            sensor_counts[trixel_map.type_] = trixel_map.sensor_count

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
    },
)
def update_trixel_sensor_count(
    trixel_id: int = Path(description="The Trixel id for which the sensor count is updated."),
    type: model.MeasurementType = Path(description="Type of measurement for which the sensor count is updated."),
    sensor_count: int = Query(description="The new number of sensors for the given type within the trixel."),
    db: Session = Depends(get_db),
) -> schema.TrixelMapUpdate:
    """Update (or insert new) trixel sensor count within the DB."""
    # TODO: requires auth (only allowed from any TMS, or possibly the one who manages the trixel)
    # could restrict to only allowed by managing tms (expensive lookup required? caching?)
    try:
        return crud.upsert_trixel_map(db, trixel_id=trixel_id, type_=type, sensor_count=sensor_count)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id!")


def main() -> None:
    """Entry point for cli module invocations."""
    uvicorn.main("trixellookupserver:app")


if __name__ == "__main__":
    main()
