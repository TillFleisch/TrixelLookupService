"""Collection of pydantic schemata related to trixel management servers."""

from pydantic import BaseModel, ConfigDict, SecretStr, field_serializer


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

    token: SecretStr

    @field_serializer("token", when_used="json")
    def reveal_token(self, v):
        """Get the jwt access token during json conversion."""
        return v.get_secret_value()


class TMSDelegation(BaseModel):
    """Schema which describes a TMS trixel delegation."""

    tms_id: int
    trixel_id: int
    exclude: bool = False
