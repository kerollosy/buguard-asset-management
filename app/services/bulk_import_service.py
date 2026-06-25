from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetRelationship, AssetStatus
from app.schemas.asset import AssetCreate


async def bulk_upsert(
    db: AsyncSession, records: list[AssetCreate]
) -> tuple[int, int, dict[str, UUID]]:
    """
    Idempotent bulk import. Uses PostgreSQL ON CONFLICT to merge metadata,
    append tags, and update last_seen for existing records.

    Returns:
        (imported_count, updated_count, ext_id_map)
        ext_id_map maps each record's external_id → internal UUID.
        Used by the caller to resolve relationship hints without a second query.
    """
    if not records:
        return 0, 0, {}

    now = datetime.now(timezone.utc)

    # Deduplicate within the batch itself by (type, value) — last record wins
    values_by_key: dict[tuple[str, str], dict] = {}
    for a in records:
        row = a.model_dump(exclude_unset=True)

        if "metadata" in row:
            row["asset_metadata"] = row.pop("metadata")

        row["first_seen"] = now
        row["last_seen"] = now
        values_by_key[(row["type"], row["value"])] = row

    values = list(values_by_key.values())

    # Count pre-existing rows to produce accurate imported vs updated counts
    existing = await db.execute(
        select(Asset.type, Asset.value).where(
            tuple_(Asset.type, Asset.value).in_(list(values_by_key.keys()))
        )
    )
    existing_keys = set(existing.all())
    imported_count = len(values_by_key) - len(existing_keys)
    updated_count = len(existing_keys)

    # Build the upsert statement
    stmt = insert(Asset).values(values)

    # Reference to the row that *would* have been inserted 
    excluded = stmt.excluded

    stmt = stmt.on_conflict_do_update(
        index_elements=["type", "value"],
        set_={
            "last_seen": now,
            # Re-appearing assets become active again
            "status": AssetStatus.active,
            # JSONB || merges dicts shallowly; incoming fields win on conflict
            "metadata": Asset.asset_metadata.op("||")(excluded.metadata),
            # Union-merge tags in the DB, preserving existing ones
            "tags": text(
                "ARRAY(SELECT DISTINCT unnest(assets.tags || EXCLUDED.tags))"
            ),
        },
    # RETURNING lets us get internal UUIDs back without a follow-up SELECT
    ).returning(Asset.id, Asset.external_id)

    result = await db.execute(stmt)
    await db.commit()

    # Build the ext_id → UUID map from the RETURNING rows
    ext_id_map: dict[str, UUID] = {
        row.external_id: row.id
        for row in result.all()
        if row.external_id is not None
    }

    return imported_count, updated_count, ext_id_map


async def resolve_relationship_hints(
    db: AsyncSession,
    records: list[AssetCreate],
    ext_id_map: dict[str, UUID],
) -> int:
    """
    Second pass: walk the validated asset list, read their hint fields
    (parent, covers), and create relationship edges where both endpoints
    are resolvable.

    Runs after bulk_upsert so all assets in the batch are committed and
    forward references within the same batch resolve correctly.

    Returns the number of new edges created.
    """
    # Maps hint field name → the relationship_type label it produces
    HINT_TO_REL_TYPE: list[tuple[str, str]] = [
        ("parent", "subdomain_of"),
        ("covers",  "covers"),
    ]

    created_count = 0

    for record in records:
        if not record.external_id:
            continue

        source_uuid = ext_id_map.get(record.external_id)
        if source_uuid is None:
            continue

        for hint_field, rel_type in HINT_TO_REL_TYPE:
            target_ext_id: str | None = getattr(record, hint_field, None)
            if not target_ext_id:
                continue

            # Fast path: target was in this batch
            target_uuid = ext_id_map.get(target_ext_id)

            # Slow path: target came from a previous import — look it up once
            if target_uuid is None:
                row = await db.execute(
                    select(Asset.id).where(Asset.external_id == target_ext_id)
                )
                target_uuid = row.scalar_one_or_none()

            if target_uuid is None:
                # Target is genuinely unknown — skip silently, don't error the batch
                continue

            # Idempotent: only insert if the edge doesn't already exist
            existing = await db.execute(
                select(AssetRelationship.id).where(
                    AssetRelationship.source_id == source_uuid,
                    AssetRelationship.target_id == target_uuid,
                    AssetRelationship.relationship_type == rel_type,
                )
            )
            if existing.scalar_one_or_none() is not None:
                continue

            db.add(
                AssetRelationship(
                    source_id=source_uuid,
                    target_id=target_uuid,
                    relationship_type=rel_type,
                )
            )
            created_count += 1

    if created_count:
        await db.commit()

    return created_count
