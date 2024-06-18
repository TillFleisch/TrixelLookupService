"""Database model definitions related to TMS management."""

from sqlalchemy import BINARY, Boolean, Column, Integer, String

from database import Base


class TrixelManagementServer(Base):
    """Database model which describes trixel management servers."""

    __tablename__ = "TrixelManagementServer"

    id = Column(Integer, primary_key=True, autoincrement=True, nullable=False)
    host = Column(String)
    token = Column(BINARY(32), unique=True)
    active = Column(Boolean, default=False, nullable=False)
