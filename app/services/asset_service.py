from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, asc, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType, AssetStatus
from app.schemas.asset import AssetCreate, AssetUpdate


async def get(db: AsyncSession, asset_id: UUID) -> Asset | None:
    """Fetch a single asset by ID."""
    result = await db.execute(select(Asset).where(Asset.id == asset_id))
    return result.scalars().first()


async def get_multi(
    db: AsyncSession,
    *,
    page: int = 0,
    size: int = 50,
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    sort_by: str = "last_seen",
    sort_order: str = "desc"
) -> tuple[int, list[Asset]]:
    """
    Returns (total_count, page_of_assets).
    Filtering, sorting, and pagination are all applied server-side.
    """
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

    # Compute total count before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    # Apply Sorting
    sort_column = getattr(Asset, sort_by, Asset.last_seen)
    if sort_order.lower() == "asc":
        stmt = stmt.order_by(asc(sort_column))
    else:
        stmt = stmt.order_by(desc(sort_column))

    # Apply Pagination
    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)

    result = await db.execute(stmt)
    assets = list(result.scalars().all())

    return total_count, assets


async def create(db: AsyncSession, *, obj_in: AssetCreate) -> Asset:
    """Create a new asset."""
    db_obj = Asset(
        external_id=obj_in.external_id,
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
