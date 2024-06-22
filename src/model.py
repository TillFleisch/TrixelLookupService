"""Database model definitions."""

import enum

from sqlalchemy import (
    CheckConstraint,
    Column,
    Enum,
    ForeignKey,
    Integer,
    UniqueConstraint,
)

from database import Base


class MeasurementType(str, enum.Enum):
    """Supported measurement types."""

    AMBIENT_TEMPERATURE = "ambient_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"


class TrixelMap(Base):
    """Database model for the TrixelMap table which describes the current state (sensor count) of all trixels."""

    __tablename__ = "TrixelMap"

    # Combined primary key from id, type
    id = Column(Integer, ForeignKey("LevelLookup.trixel_id"), primary_key=True, nullable=False)
    type_ = Column(Enum(MeasurementType), primary_key=True, nullable=False)
    sensor_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint(sensor_count >= 0, name="check_non_negative_sensor_count"),
        UniqueConstraint(id, type_, name="unique_constraint_id_type"),
    )


class LevelLookup(Base):
    """Pre-computed level attribute for faster/simpler queries."""

    __tablename__ = "LevelLookup"

    trixel_id = Column(Integer, primary_key=True, nullable=False, unique=True)
    level = Column(Integer, nullable=False)

    __table_args__ = (CheckConstraint(level >= 0, name="check_non_negative_level"),)
