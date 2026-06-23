from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.relationships import AssetRelationshipBase, AssetRelationshipResponse
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


@router.get("/relationships", response_model=list[AssetRelationshipResponse])
async def list_relationships(
    source_id: UUID | None = Query(None),
    target_id: UUID | None = Query(None),
    db: AsyncSession = Depends(get_db)
):
    rels = await relationship_service.list_relationships(
        db, source_id=source_id, target_id=target_id
    )
    return [AssetRelationshipResponse.model_validate(r) for r in rels]


@router.delete("/relationships/{rel_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_asset_relationship(
    rel_id: UUID, db: AsyncSession = Depends(get_db)
):
    """Delete a specific relationship between two assets."""
    deleted = await relationship_service.delete_relationship(db, rel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Relationship {rel_id} not found")
