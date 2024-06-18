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
    id = Column(Integer, primary_key=True, nullable=False)
    type_ = Column(Enum(MeasurementType), primary_key=True, nullable=False)
    # Pre-computed level attribute for faster/simpler queries
    level = Column(Integer, nullable=False)
    sensor_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint(sensor_count >= 0, name="check_non_negative_sensor_count"),
        CheckConstraint(level >= 0, name="check_non_negative_level"),
    )
