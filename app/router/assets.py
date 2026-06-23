from uuid import UUID
from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.core.database import get_db
from app.schemas.asset import AssetCreate, AssetUpdate, AssetResponse, BulkImportResponse
from app.models.asset import AssetType, AssetStatus
from app.services import asset_service as crud_asset

router = APIRouter()

@router.post("/", response_model=AssetResponse, status_code=status.HTTP_201_CREATED)
async def create_asset(
    asset_in: AssetCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new asset."""
    try:
        asset = await crud_asset.create(db=db, obj_in=asset_in)
        return asset
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An asset with this type and value already exists."
        )

@router.get("/", response_model=list[AssetResponse])
async def list_assets(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    sort_by: str = Query("last_seen", regex="^(first_seen|last_seen|type|value|status)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db)
):
    """Retrieve multiple assets with filtering, sorting, and pagination."""
    assets = await crud_asset.get_multi(
        db,
        skip=skip,
        limit=limit,
        asset_type=asset_type,
        status=status,
        tag=tag,
        value_contains=value_contains,
        sort_by=sort_by,
        sort_order=sort_order
    )
    return assets

@router.get("/{asset_id}", response_model=AssetResponse)
async def get_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific asset by ID."""
    asset = await crud_asset.get(db, asset_id)
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
    asset = await crud_asset.get(db, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    
    asset = await crud_asset.update(db=db, db_obj=asset, obj_in=asset_in)
    return asset

@router.delete("/{asset_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asset(
    asset_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Delete a specific asset."""
    asset = await crud_asset.remove(db, asset_id=asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return None

@router.post("/bulk", response_model=BulkImportResponse, status_code=status.HTTP_200_OK)
async def bulk_import_assets(
    payload: list[dict[str, Any]],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk import assets from a JSON array. 
    Malformed records are skipped and reported; valid records are ingested or merged.
    """
    valid_assets: list[AssetCreate] = []
    errors: list[dict[str, Any]] = []

    # 1. Triage the payload
    for index, item in enumerate(payload):
        try:
            # Manually validate against our strict schema
            asset = AssetCreate.model_validate(item)
            valid_assets.append(asset)
        except ValidationError as e:
            # Catch bad records without failing the entire HTTP request
            errors.append({
                "index": index,
                "value": item.get("value", "unknown"),
                "errors": e.errors()
            })

    # 2. Process valid assets in bulk
    if valid_assets:
        # Note: For payloads > 10,000 records, we would implement chunking here.
        # Given the scope, we process the valid batch in a single transaction.
        await crud_asset.bulk_upsert(db, valid_assets)

    # 3. Return a detailed report
    return BulkImportResponse(
        processed_count=len(valid_assets),
        failed_count=len(errors),
        errors=errors
    )