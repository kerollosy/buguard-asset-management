from typing import Sequence
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, asc, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.asset import Asset, AssetType, AssetStatus
from app.schemas.asset import AssetCreate, AssetUpdate

async def get(db: AsyncSession, asset_id: UUID) -> Asset | None:
    """Fetch a single asset by ID."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalars().first()

async def get_multi(
    db: AsyncSession,
    *,
    skip: int = 0,
    limit: int = 50,
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    sort_by: str = "last_seen",
    sort_order: str = "desc"
) -> Sequence[Asset]:
    """Fetch multiple assets with filtering, sorting, and pagination."""
    # Hard cap limit to prevent memory exhaustion
    actual_limit = min(limit, 1000)
    
    stmt = select(Asset)

    # Apply Filters
    if asset_type:
        stmt = stmt.where(Asset.type == asset_type)
    if status:
        stmt = stmt.where(Asset.status == status)
    if tag:
        # PostgreSQL specific array operation
        stmt = stmt.where(Asset.tags.any(tag))
    if value_contains:
        stmt = stmt.where(Asset.value.icontains(value_contains))

    # Apply Sorting
    sort_column = getattr(Asset, sort_by, Asset.last_seen)
    if sort_order.lower() == "asc":
        stmt = stmt.order_by(asc(sort_column))
    else:
        stmt = stmt.order_by(desc(sort_column))

    # Apply Pagination
    stmt = stmt.offset(skip).limit(actual_limit)

    result = await db.execute(stmt)
    return result.scalars().all()

async def create(db: AsyncSession, *, obj_in: AssetCreate) -> Asset:
    """Create a new asset."""
    db_obj = Asset(
        type=obj_in.type,
        value=obj_in.value,
        status=obj_in.status,
        source=obj_in.source,
        tags=obj_in.tags,
        asset_metadata=obj_in.asset_metadata,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc)
    )
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def update(db: AsyncSession, *, db_obj: Asset, obj_in: AssetUpdate) -> Asset:
    """Update an existing asset."""
    update_data = obj_in.model_dump(exclude_unset=True)
    
    # Map Pydantic 'metadata' alias to DB 'asset_metadata'
    if "metadata" in update_data:
        update_data["asset_metadata"] = update_data.pop("metadata")

    for field, value in update_data.items():
        setattr(db_obj, field, value)

    # Always update last_seen on modification
    db_obj.last_seen = datetime.now(timezone.utc)
    
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def remove(db: AsyncSession, *, asset_id: UUID) -> Asset | None:
    """Delete an asset by ID."""
    obj = await get(db, asset_id)
    if not obj:
        return None
    await db.delete(obj)
    await db.commit()
    return obj