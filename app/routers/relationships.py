from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.relationships import AssetRelationshipBase, AssetRelationshipResponse, AssetGraphResponse
from app.services import relationship_service


router = APIRouter()


@router.post("/relationships", response_model=AssetRelationshipResponse, status_code=status.HTTP_201_CREATED)
async def create_asset_relationship(
    relationship_in: AssetRelationshipBase,
    db: AsyncSession = Depends(get_db)
):
    """Create a relationship edge between two assets."""
    try:
        rel = await relationship_service.create_relationship(db=db, obj_in=relationship_in)
        return rel
    except ValueError as e:
        error_detail = str(e)
        if "already exists" in error_detail:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=error_detail)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_detail)


@router.get("/{asset_id}/graph", response_model=AssetGraphResponse)
async def get_asset_graph(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific asset along with its incoming and outgoing relationships."""
    asset = await relationship_service.get_asset_graph(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset