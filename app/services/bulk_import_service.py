from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func
from app.models.asset import Asset, AssetStatus
from app.schemas.asset import AssetCreate


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