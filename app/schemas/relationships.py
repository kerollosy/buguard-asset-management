from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AssetRelationshipBase(BaseModel):
    source_id: UUID = Field(
        ..., 
        description="The UUID of the origin asset.",
        examples=["123e4567-e89b-12d3-a456-426614174000"]
    )
    target_id: UUID = Field(
        ..., 
        description="The UUID of the destination asset.",
        examples=["987fcdeb-51a2-43d7-9012-345678901234"]
    )
    relationship_type: str = Field(
        ..., 
        description="The nature of the connection (e.g., resolves_to, covers, runs_on).",
        examples=["resolves_to"]
    )


class AssetRelationshipResponse(AssetRelationshipBase):
    """
    Serializes the edge (the relationship link). 
    Critically, it does NOT include the nested Asset objects to prevent 
    infinite recursion during Pydantic serialization (Asset -> Rel -> Asset...).
    """
    id: UUID = Field(..., examples=["550e8400-e29b-41d4-a716-446655440000"])
    created_at: datetime = Field(..., examples=["2023-01-01T00:00:00Z"])
    model_config = ConfigDict(from_attributes=True)
