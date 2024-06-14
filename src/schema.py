"""Collection of global pydantic schemata."""

from pydantic import BaseModel


class Ping(BaseModel):
    """Response model for ping requests."""

    ping: str = "pong"


class Version(BaseModel):
    """Response model for version requests."""

    version: str
