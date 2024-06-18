"""Collection of pydantic schemata related to trixel management servers."""

import base64

from pydantic import BaseModel, ConfigDict, SecretBytes, field_serializer


class TrixelManagementServerBase(BaseModel):
    """Base class for TrixelManagementServer schema."""

    id: int
    active: bool
    host: str


class TrixelManagementServer(TrixelManagementServerBase):
    """TMS detailed response schema."""

    model_config = ConfigDict(from_attributes=True)


class TrixelManagementServerCreate(TrixelManagementServerBase):
    """TMS initialization schema, which contains the authentication token."""

    token: SecretBytes

    @field_serializer("token", when_used="json")
    def reveal_token(self, v):
        """Get a base64 encoded representation of the access token during json conversion."""
        return base64.b64encode(v.get_secret_value())
