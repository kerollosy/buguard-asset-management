from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core import constants
from app.core.limiter import limiter
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.asset import AddTagsRequest, AssetCreate, AssetGraphResponse, AssetResponse, AssetUpdate
from app.schemas.pagination import AssetSortField, PaginatedResponse, SortOrder
from app.models.asset import AssetType, AssetStatus
from app.services import asset_service

router = APIRouter()

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(get_current_user)])
async def create_asset(
    payload: AssetCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new asset."""
    try:
        asset = await asset_service.create(db, payload)
        return asset
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this type and value already exists."
        )


@router.get("/", response_model=PaginatedResponse[AssetResponse])
@limiter.limit(constants.RATE_LIMIT_STANDARD)
async def list_assets(
    request: Request,
    page: int = Query(1, ge=1),
    size: int = Query(constants.DEFAULT_PAGE_SIZE, ge=1, le=constants.MAX_PAGE_SIZE),
    asset_type: AssetType | None = Query(None, alias="type"),
    status: AssetStatus | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    sort_by: AssetSortField = Query(AssetSortField.LAST_SEEN),
    sort_order: SortOrder = Query(SortOrder.DESC),
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    return asset


@router.patch("/{asset_id}", response_model=AssetResponse, dependencies=[Depends(get_current_user)])
async def update_asset(
    asset_id: UUID,
    payload: AssetUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a specific asset."""
    asset = await asset_service.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    
    asset = await asset_service.update(db, asset, payload)
    return asset


@router.post("/{asset_id}/stale", response_model=AssetResponse, dependencies=[Depends(get_current_user)])
async def mark_asset_stale(
    asset_id: UUID, 
    db: AsyncSession = Depends(get_db)
):
    """
    **Mark Asset as Stale**
    
    Explicitly mark an asset as stale (e.g., if a scanner determines it is no longer responding).
    """
    asset = await asset_service.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    
    # We pass a simple schema into the existing update service
    asset = await asset_service.update(db, asset, AssetUpdate(status=AssetStatus.stale))
    return asset


@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(get_current_user)])
async def delete_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific asset."""
    asset = await asset_service.delete(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found")
    return None


@router.post(
    "/{asset_id}/tags",
    response_model=AssetResponse,
    summary="Add tags to an asset (union merge)",
    dependencies=[Depends(get_current_user)]
)
async def add_tags(asset_id: UUID, body: AddTagsRequest, db: AsyncSession = Depends(get_db)):
    asset = await asset_service.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Asset {asset_id} not found.")

    asset = await asset_service.add_tags(db, asset, body.tags)
    return asset


@router.get("/{asset_id}/graph", response_model=AssetGraphResponse)
async def get_asset_graph(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific asset along with its incoming and outgoing relationships."""
    asset = await asset_service.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset
