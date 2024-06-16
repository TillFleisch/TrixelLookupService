"""Entry point for the Trixel Lookup Service API."""

import importlib
from http import HTTPStatus
from typing import Annotated, List

import packaging.version
import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy.orm import Session

import crud
import model
import schema
from database import MetaSession, engine
from schema import Ping, Version

TAG_TRIXEL_INFO = "Trixel Information"

api_version = importlib.metadata.version("trixellookupserver")

model.Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Trixel Lookup Service",
    summary="""Manages Trixel Managements Servers (TMS) and their Trixel ID responsibilities.
               Coordinates initial communication to determine the correct TMS for a contributor.""",
    version=api_version,
    root_path=f"/v{packaging.version.Version(api_version).major}",
)


def get_db():
    """Instantiate a temporary session for endpoint invocation."""
    db = MetaSession()
    try:
        yield db
    finally:
        db.close()


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
    "/trixel/{trixel_id}/sensor_count",
    name="Get trixel sensor count",
    summary="Get the sensor count within a trixel per measurement type.",
    tags=[TAG_TRIXEL_INFO],
)
def get_trixel_info(
    trixel_id: int,
    types: Annotated[List[model.MeasurementType], Query()] = None,
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
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id")


@app.put(
    "/trixel/{trixel_id}/sensor_count/{type}",
    name="Update trixel count",
    summary="Update the sensor count for a given trixel and type.",
    tags=[TAG_TRIXEL_INFO],
)
def update_trixel_sensor_count(
    trixel_id: int, type: model.MeasurementType, sensor_count: int, db: Session = Depends(get_db)
) -> schema.TrixelMapUpdate:
    """Update (or insert new) trixel sensor count within the DB."""
    # TODO: requires auth (only allowed from any TMS, or possibly the one who manages the trixel)
    try:
        return crud.upsert_trixel_map(db, trixel_id=trixel_id, type_=type, sensor_count=sensor_count)
    except ValueError:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Invalid trixel id.")


def main() -> None:
    """Entry point for cli module invocations."""
    uvicorn.main("trixellookupserver:app")


if __name__ == "__main__":
    main()
