from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy import select, asc, desc, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetRelationship, AssetType, AssetStatus
from app.schemas.asset import AssetCreate, AssetRelationshipBase, AssetUpdate

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

async def bulk_upsert(db: AsyncSession, assets_in: list[AssetCreate]) -> None:
    """
    Idempotent bulk import. Uses PostgreSQL ON CONFLICT to merge metadata, 
    append tags, and update last_seen for existing records.
    """
    if not assets_in:
        return

    # 1. Convert Pydantic models to a list of dicts for bulk insert
    values = []
    now = datetime.now(timezone.utc)
    
    for a in assets_in:
        d = a.model_dump(exclude_unset=True)
        # Handle the Pydantic to SQLAlchemy alias mapping
        if "metadata" in d:
            d["asset_metadata"] = d.pop("metadata")
        
        d["first_seen"] = now
        d["last_seen"] = now
        values.append(d)

    # 2. Build the PostgreSQL-specific INSERT statement
    stmt = insert(Asset).values(values)
    
    # Reference to the row that *would* have been inserted (the new data)
    excluded = stmt.excluded

    # 3. Define the merge strategy on conflict (matching type + value)
    update_dict = {
        "last_seen": now,
        "status": AssetStatus.active, # Re-appearing assets become active again
        
        # PostgreSQL JSONB concatenation || merges dictionaries shallowly
        "metadata": Asset.asset_metadata.op("||")(excluded.metadata),
        
        # PostgreSQL array concatenation
        "tags": func.array_cat(Asset.tags, excluded.tags)
    }

    # 4. Attach the ON CONFLICT clause
    stmt = stmt.on_conflict_do_update(
        index_elements=["type", "value"],
        set_=update_dict
    )

    await db.execute(stmt)
    await db.commit()

async def create_relationship(db: AsyncSession, *, obj_in: AssetRelationshipBase) -> AssetRelationship:
    """Creates a directed link between two assets."""
    if obj_in.source_id == obj_in.target_id:
        raise ValueError("Self-referencing loops are not permitted.")

    db_obj = AssetRelationship(
        source_id=obj_in.source_id,
        target_id=obj_in.target_id,
        relationship_type=obj_in.relationship_type
    )
    db.add(db_obj)
    try:
        await db.commit()
        await db.refresh(db_obj)
        return db_obj
    except IntegrityError as e:
        await db.rollback()
        err_msg = str(e.orig).lower()
        # Handle PostgreSQL exceptions natively without crashing
        if "foreign key constraint" in err_msg or "insert or update on table" in err_msg:
            raise ValueError("One or both associated assets do not exist.")
        raise ValueError("This relationship already exists.")

async def get_asset_graph(db: AsyncSession, asset_id: UUID) -> Asset | None:
    """Fetches an asset and eagerly loads its immediate relationship graph."""
    stmt = (
        select(Asset)
        .where(Asset.id == asset_id)
        # selectinload natively queries the junction table without triggering N+1 query loops
        .options(
            selectinload(Asset.outgoing),
            selectinload(Asset.incoming)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().first()