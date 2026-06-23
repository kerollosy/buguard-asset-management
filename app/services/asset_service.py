from uuid import UUID
from datetime import datetime, timezone

from sqlalchemy import select, asc, desc, func, delete as delete_stmt
from sqlalchemy.ext.asyncio import AsyncSession 
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetRelationship, AssetType, AssetStatus
from app.schemas.asset import AssetCreate, AssetUpdate


async def get(db: AsyncSession, asset_id: UUID) -> Asset | None:
    result = await db.execute(
        select(Asset)
        .where(Asset.id == asset_id)
        .options(
            selectinload(Asset.outgoing).selectinload(AssetRelationship.target_asset),
            selectinload(Asset.incoming).selectinload(AssetRelationship.source_asset),
        )
    )
    return result.scalar_one_or_none()


async def get_multi(
    db: AsyncSession,
    *,
    page: int = 1,
    size: int = 50,
    asset_type: AssetType | None = None,
    status: AssetStatus | None = None,
    tag: str | None = None,
    value_contains: str | None = None,
    type: AssetType | None = None,
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
        stmt = stmt.where(Asset.tags.contains([tag]))
    if value_contains:
        stmt = stmt.where(Asset.value.icontains(value_contains))
    if type:
        stmt = stmt.where(Asset.type == type)

    # Compute total count before pagination
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_count = (await db.execute(count_stmt)).scalar_one()

    # Apply Sorting
    ALLOWED_SORT_COLUMNS = {
        "last_seen": Asset.last_seen,
        "first_seen": Asset.first_seen,
        "value": Asset.value,
        "type": Asset.type,
        "status": Asset.status,
    }
    sort_column = ALLOWED_SORT_COLUMNS.get(sort_by, Asset.last_seen)
    stmt = stmt.order_by(asc(sort_column) if sort_order.lower() == "asc" else desc(sort_column))

    # Apply Pagination
    offset = (page - 1) * size
    stmt = stmt.offset(offset).limit(size)

    result = await db.execute(stmt)
    assets = list(result.scalars().all())

    return total_count, assets


async def create(db: AsyncSession, payload: AssetCreate) -> Asset:
    """Create a new asset."""
    asset = Asset(
        external_id=payload.external_id,
        type=payload.type,
        value=payload.value,
        status=payload.status,
        source=payload.source,
        tags=payload.tags,
        asset_metadata=payload.asset_metadata,
        first_seen=datetime.now(timezone.utc),
        last_seen=datetime.now(timezone.utc)
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


async def update(db: AsyncSession, asset: Asset, payload: AssetUpdate) -> Asset:
    """Update an existing asset."""
    update_data = payload.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(asset, field, value)

    # Always update last_seen on modification
    asset.last_seen = datetime.now(timezone.utc)
    
    await db.commit()
    await db.refresh(asset)
    return asset


async def delete(db: AsyncSession, asset_id: UUID) -> Asset | None:
    """Delete an asset by ID."""
    stmt = delete_stmt(Asset).where(Asset.id == asset_id).returning(Asset)
    
    result = await db.execute(stmt)
    await db.commit()
    
    return result.scalar_one_or_none()


async def add_tags(
    db: AsyncSession, asset: Asset, new_tags: list[str]
) -> Asset:
    """Union-merge new_tags into the asset's existing tag list."""
    merged = sorted(set(asset.tags or []) | {t.strip().lower() for t in new_tags if t.strip()})
    asset.tags = merged
    asset.last_seen = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(asset)
    return asset
