"""Database model definitions related to TMS management."""

from sqlalchemy import (
    Boolean,
    Column,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


class TrixelManagementServer(Base):
    """Database model which describes trixel management servers."""

    __tablename__ = "TrixelManagementServer"

    id = Column(Integer, primary_key=True, unique=True, autoincrement=True, nullable=False)
    host = Column(String(255))
    token = Column(LargeBinary(32))  # TODO: uniqueness should be enforced if the token is used for identification
    active = Column(Boolean, default=False, nullable=False)

    delegations = relationship("TMSDelegation", back_populates="tms")


class TMSDelegation(Base):
    """
    Database model which describes which trixels (and subsequently nested sub-trixels) are delegated to which TMS.

    The exclusion attribute is set when a sub-trixel is excluded (managed by a different TMS).
    """

    __tablename__ = "TMSDelegation"

    tms_id = Column(Integer, ForeignKey("TrixelManagementServer.id"), primary_key=True, nullable=False)
    trixel_id = Column(Integer, ForeignKey("LevelLookup.trixel_id"), primary_key=True, nullable=False)
    exclude = Column(Boolean, default=False, nullable=False)

    tms = relationship("TrixelManagementServer", back_populates="delegations")

    __table_args__ = (UniqueConstraint("tms_id", "trixel_id", name="unique_constraint_tms_trixel"),)
