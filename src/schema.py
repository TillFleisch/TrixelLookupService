"""Collection of global pydantic schemata."""

from typing import Annotated

from pydantic import (
    AfterValidator,
    BaseModel,
    Field,
    NonNegativeInt,
    PositiveInt,
    field_validator,
)
from pynyhtm import HTM

from model import MeasurementTypeEnum


def validate_trixel_id(value: int) -> int:
    """Validate that the TrixelId is valid."""
    try:
        HTM.get_level(value)
        return value
    except Exception:
        raise ValueError(f"Invalid trixel id: {value}!")


TrixelID = Annotated[
    PositiveInt,
    AfterValidator(validate_trixel_id),
    Field(description="A valid Trixel ID.", examples={8, 9, 15, 35}, serialization_alias="trixel_id"),
]


class Ping(BaseModel):
    """Response schema for ping requests."""

    ping: str = "pong"


class Version(BaseModel):
    """Response schema for version requests."""

    version: str


class TrixelMapBase(BaseModel):
    """Base Schema for trixel map entries."""

    id: TrixelID


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


BatchSensorMapUpdate = Annotated[
    dict[
        Annotated[TrixelID, Field(description="A valid trixel identifier.")],
        Annotated[NonNegativeInt, Field(description="The new sensor count for the given trixel.")],
    ],
    Field(description="A map which contains the new sensors count for multiple trixels."),
]
