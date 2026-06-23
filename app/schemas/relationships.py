from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.asset import AssetResponse


class AssetRelationshipBase(BaseModel):
    source_id: UUID
    target_id: UUID
    relationship_type: str


class AssetRelationshipResponse(AssetRelationshipBase):
    """
    Serializes the edge (the relationship link). 
    Critically, it does NOT include the nested Asset objects to prevent 
    infinite recursion during Pydantic serialization (Asset -> Rel -> Asset...).
    """
    id: UUID
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class AssetGraphResponse(AssetResponse):
    """Schema for returning an asset with its immediate relationship graph."""
    outgoing: list[AssetRelationshipResponse] = Field(default_factory=list)
    incoming: list[AssetRelationshipResponse] = Field(default_factory=list)
