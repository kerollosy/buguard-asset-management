from uuid import UUID
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator
from app.models.asset import AssetType, AssetStatus


class AssetBase(BaseModel):
    type: AssetType
    value: str = Field(..., min_length=1, max_length=512)
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
    pass


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

    # Computed convenience field for certificate assets
    @property
    def is_expired(self) -> bool | None:
        if self.type != AssetType.certificate:
            return None
        expires = self.asset_metadata.get("expires")
        if not expires:
            return None
        from datetime import timezone
        try:
            exp = datetime.fromisoformat(str(expires))
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            return exp < datetime.now(timezone.utc)
        except ValueError:
            return None

    model_config = ConfigDict(from_attributes=True)


class AssetRelationshipBase(BaseModel):
    source_asset_id: UUID
    target_asset_id: UUID
    relationship_type: str

class AssetRelationshipResponse(AssetRelationshipBase):
    model_config = ConfigDict(from_attributes=True)

class BulkImportResponse(BaseModel):
    """Schema for reporting the results of a bulk import operation."""
    processed_count: int
    failed_count: int
    errors: list[dict[str, Any]] = Field(default_factory=list)