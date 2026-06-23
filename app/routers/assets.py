from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.schemas.asset import AssetCreate, AssetResponse, AssetUpdate
from app.schemas.pagination import PaginatedResponse
from app.models.asset import AssetType, AssetStatus
from app.services import asset_service

router = APIRouter()

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_in: AssetCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new asset."""
    try:
        asset = await asset_service.create(db=db, obj_in=asset_in)
        return asset
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this type and value already exists."
        )


@router.get("/", response_model=PaginatedResponse[AssetResponse])
async def list_assets(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    sort_by: str = Query("last_seen", pattern="^(first_seen|last_seen|type|value|status)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve multiple assets with filtering, sorting, and pagination."""
    total, assets = await asset_service.get_multi(
        db,
        page=page,
        size=size,
        asset_type=asset_type,
        status=status,
        tag=tag,
        value_contains=value_contains,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": assets
    }


@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific asset by ID."""
    asset = await asset_service.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


@router.put("/{asset_id}", response_model=AssetResponse)
async def update_asset(
    asset_id: UUID,
    asset_in: AssetUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a specific asset."""
    asset = await asset_service.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    asset = await asset_service.update(db=db, db_obj=asset, obj_in=asset_in)
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific asset."""
    asset = await asset_service.remove(db, asset_id=asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return None
