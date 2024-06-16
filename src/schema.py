"""Collection of global pydantic schemata."""

from pydantic import BaseModel, ConfigDict

from model import MeasurementType


class Ping(BaseModel):
    """Response model for ping requests."""

    ping: str = "pong"


class Version(BaseModel):
    """Response model for version requests."""

    version: str


class TrixelMapBase(BaseModel):
    """Base model for trixel map entries."""

    id: int


class TrixelMap(TrixelMapBase):
    """Model for reading from the trixel map."""

    model_config = ConfigDict(from_attributes=True)

    sensor_counts: dict[MeasurementType, int]


class TrixelMapUpdate(TrixelMapBase):
    """Model for updating the sensor count for a measurement type in a trixel."""

    type_: MeasurementType
    sensor_count: int
