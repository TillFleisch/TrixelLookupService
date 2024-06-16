"""Database model definitions."""

import enum

from sqlalchemy import CheckConstraint, Column, Enum, Integer

from database import Base


class MeasurementType(str, enum.Enum):
    """Supported measurement types."""

    AMBIENT_TEMPERATURE = "ambient_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"


class TrixelMap(Base):
    """Database model for the TrixelMap table which describes the current state (sensor count) of all trixels."""

    __tablename__ = "TrixelMap"

    # Combined primary key from id, type
    id = Column(Integer, primary_key=True)
    type_ = Column(Enum(MeasurementType), primary_key=True)
    sensor_count = Column(Integer, default=0)

    __table_args__ = (CheckConstraint(sensor_count >= 0, name="check_non_negative_sensor_count"), {})
