"""Database model definitions."""

import enum

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)

from database import Base


class MeasurementTypeEnum(str, enum.Enum):
    """Supported measurement types."""

    # A string enum is used, so that the value can be used in urls.
    # Within the DB the "id" is used but the enum name can also be retrieved via the relation
    AMBIENT_TEMPERATURE = "ambient_temperature"
    RELATIVE_HUMIDITY = "relative_humidity"

    def get_id(self):
        """Get the index of the measurement type instance within this enum."""
        return [x for x in MeasurementTypeEnum].index(self) + 1

    def get_from_id(id_: int):
        """
        Get an enum instance from this enum which has the given id.

        :param id_: target enum index
        :return: enum which has index id_
        """
        return [x for x in MeasurementTypeEnum][id_ - 1]


class MeasurementType(Base):
    """Enum-like table which contains all available measurement types."""

    __tablename__ = "MeasurementType"

    id = Column(Integer, unique=True, primary_key=True, nullable=False, index=True)
    name = Column(String(32), unique=True, nullable=False)


class TrixelMap(Base):
    """Database model for the TrixelMap table which describes the current state (sensor count) of all trixels."""

    __tablename__ = "TrixelMap"

    # Combined primary key from id, type
    id = Column(BigInteger, ForeignKey("LevelLookup.trixel_id"), primary_key=True, nullable=False, index=True)
    type_id = Column(Integer, ForeignKey("MeasurementType.id", ondelete="CASCADE"), primary_key=True, nullable=False)
    sensor_count = Column(Integer, default=0, nullable=False)

    __table_args__ = (
        CheckConstraint(sensor_count >= 0, name="check_non_negative_sensor_count"),
        UniqueConstraint(id, type_id, name="unique_constraint_id_type"),
    )


class LevelLookup(Base):
    """Pre-computed level attribute for faster/simpler queries."""

    __tablename__ = "LevelLookup"

    trixel_id = Column(BigInteger, primary_key=True, nullable=False, unique=True, index=True)
    level = Column(Integer, nullable=False)

    __table_args__ = (CheckConstraint(level >= 0, name="check_non_negative_level"),)
