"""Database model definitions related to TMS management."""

from sqlalchemy import (
    BigInteger,
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

    id = Column(Integer, primary_key=True, unique=True, autoincrement=True, nullable=False, index=True)
    host = Column(String(256))
    token_secret = Column(LargeBinary(256))
    active = Column(Boolean, default=False, nullable=False)

    delegations = relationship("TMSDelegation", back_populates="tms")


class TMSDelegation(Base):
    """
    Database model which describes which trixels (and subsequently nested sub-trixels) are delegated to which TMS.

    The exclusion attribute is set when a sub-trixel is excluded (managed by a different TMS).
    """

    __tablename__ = "TMSDelegation"

    tms_id = Column(
        Integer,
        ForeignKey("TrixelManagementServer.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
        index=True,
    )
    trixel_id = Column(BigInteger, ForeignKey("LevelLookup.trixel_id"), primary_key=True, nullable=False, index=True)
    exclude = Column(Boolean, default=False, nullable=False)

    tms = relationship("TrixelManagementServer", back_populates="delegations")

    __table_args__ = (UniqueConstraint("tms_id", "trixel_id", name="unique_constraint_tms_trixel"),)
