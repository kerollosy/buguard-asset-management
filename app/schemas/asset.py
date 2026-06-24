from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from app.core import constants
from app.models.asset import AssetType, AssetStatus
from app.schemas.relationships import AssetRelationshipResponse


class AssetBase(BaseModel):
    type: AssetType
    value: str = Field(..., min_length=1, max_length=constants.MAX_ASSET_VALUE_LENGTH)
    status: AssetStatus = AssetStatus.active
    source: str
    tags: list[str] = Field(default_factory=list)
    # Alias matches the DB column name, but maps to the SQLAlchemy property name
    asset_metadata: dict[str, Any] = Field(
        default_factory=dict, 
        validation_alias=AliasChoices("asset_metadata", "metadata"),
        serialization_alias="metadata"
    )

    @field_validator("value")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str]) -> list[str]:
        return sorted({t.strip().lower() for t in v if t.strip()})


class AssetCreate(AssetBase):
    """Schema for ingesting a new asset."""
    external_id: str | None = Field(
        default=None,
        # Looks for "id" or "external_id" in the incoming JSON payload
        validation_alias=AliasChoices("id", "external_id")
    )


class AssetUpdate(BaseModel):
    """Schema for updating an existing asset."""
    status: AssetStatus | None = None
    tags: list[str] | None = None
    asset_metadata: dict[str, Any] | None = Field(
        None,
        validation_alias=AliasChoices("asset_metadata", "metadata"),
        serialization_alias="metadata",
    )

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        return sorted({t.strip().lower() for t in v if t.strip()})


class AssetResponse(AssetBase):
    """Schema for returning an asset in API responses."""
    id: UUID
    external_id: str | None
    first_seen: datetime
    last_seen: datetime

    model_config = ConfigDict(from_attributes=True)


class AssetGraphResponse(AssetResponse):
    """Schema for returning an asset with its immediate relationship graph."""
    outgoing: list[AssetRelationshipResponse] = Field(default_factory=list)
    incoming: list[AssetRelationshipResponse] = Field(default_factory=list)


class AddTagsRequest(BaseModel):
    tags: list[str]
