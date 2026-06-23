from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from app.models.asset import Asset, AssetRelationship
from app.schemas.relationships import AssetRelationshipBase


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