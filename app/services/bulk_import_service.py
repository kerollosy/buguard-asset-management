from datetime import datetime, timezone

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetStatus
from app.schemas.asset import AssetCreate


async def bulk_upsert(db: AsyncSession, records: list[AssetCreate]) -> tuple[int, int]:
    """
    Idempotent bulk import. Uses PostgreSQL ON CONFLICT to merge metadata, 
    append tags, and update last_seen for existing records.
    """
    if not records:
        return 0, 0

    now = datetime.now(timezone.utc)

    # Map incoming assets by their unique identifier: (type, value)
    values_by_key: dict[tuple[object, str], dict[str, object]] = {}
    
    for a in records:
        row = a.model_dump(exclude_unset=True)

        if "metadata" in row:
            row["asset_metadata"] = row.pop("metadata")
        
        row["first_seen"] = now
        row["last_seen"] = now
        values_by_key[(row["type"], row["value"])] = row

    values = list(values_by_key.values())

    # Find exactly how many already exist to calculate accurate counts
    stmt = select(Asset.type, Asset.value).where(
        tuple_(Asset.type, Asset.value).in_(list(values_by_key.keys()))
    )
    result = await db.execute(stmt)
    
    existing_keys = result.all()
    imported_count = len(values_by_key) - len(existing_keys)
    updated_count = len(existing_keys)

    # Build the PostgreSQL-specific INSERT statement
    stmt = insert(Asset).values(values)
    
    # Reference to the row that *would* have been inserted 
    excluded = stmt.excluded

    # Define the merge strategy on conflict
    update_dict = {
        "last_seen": now,
        "status": AssetStatus.active, # Re-appearing assets become active again
        # PostgreSQL JSONB concatenation || merges dictionaries shallowly
        "metadata": Asset.asset_metadata.op("||")(excluded.metadata),

        # Merge existing tags with incoming (EXCLUDED) tags, and deduplicate them in the DB
        "tags": text("ARRAY(SELECT DISTINCT unnest(assets.tags || EXCLUDED.tags))")
    }

    # Attach the ON CONFLICT clause
    stmt = stmt.on_conflict_do_update(
        index_elements=["type", "value"],
        set_=update_dict
    )

    await db.execute(stmt)
    await db.commit()

    return imported_count, updated_count
