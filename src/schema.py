"""Collection of global pydantic schemata."""

from pydantic import BaseModel, ConfigDict

from model import MeasurementType


class Ping(BaseModel):
    """Response schema for ping requests."""

    ping: str = "pong"


class Version(BaseModel):
    """Response schema for version requests."""

    version: str


class TrixelMapBase(BaseModel):
    """Base Schema for trixel map entries."""

    id: int


class TrixelMap(TrixelMapBase):
    """Schema for reading from the trixel map."""

    model_config = ConfigDict(from_attributes=True)

    sensor_counts: dict[MeasurementType, int]


class TrixelMapUpdate(TrixelMapBase):
    """Schema for updating the sensor count for a measurement type in a trixel."""

    type_: MeasurementType
    sensor_count: int
