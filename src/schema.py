"""Collection of global pydantic schemata."""

from pydantic import BaseModel, Field, field_validator

from model import MeasurementTypeEnum


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

    sensor_counts: dict[MeasurementTypeEnum, int]

    @field_validator("sensor_counts", mode="before")
    def convert_measurement_type(data: dict[int | str | MeasurementTypeEnum, int]) -> MeasurementTypeEnum | str:
        """Automatically convert int enum (originating from db) into their wrapped enum class."""
        for key in list(data.keys()):
            if isinstance(key, int):
                data[MeasurementTypeEnum.get_from_id(key)] = data[key]
                del data[key]
        return data


class TrixelMapUpdate(TrixelMapBase):
    """Schema for updating the sensor count for a measurement type in a trixel."""

    type_: MeasurementTypeEnum = Field(alias="type_id", serialization_alias="type_")
    sensor_count: int

    @field_validator("type_", mode="before")
    def convert_measurement_type(data: int | str | MeasurementTypeEnum) -> MeasurementTypeEnum | str:
        """Automatically convert int enum (originating from db) into their wrapped enum class."""
        if isinstance(data, int):
            return MeasurementTypeEnum.get_from_id(data)
        return data
