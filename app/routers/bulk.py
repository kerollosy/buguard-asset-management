from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core import constants
from app.core.limiter import limiter
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.asset import AssetCreate
from app.schemas.bulk import BulkImportError, BulkImportResponse
from app.services import bulk_import_service


router = APIRouter()


@router.post("/bulk", response_model=BulkImportResponse, status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)])
@limiter.limit(constants.RATE_LIMIT_BULK)
async def bulk_import_assets(
    request: Request,
    payload: list[dict[str, Any]],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk import assets from a JSON array. 
    Malformed records are skipped and reported; valid records are ingested or merged.
    """
    valid_assets: list[AssetCreate] = []
    errors: list[BulkImportError] = []

    # 1. Triage the payload
    for index, item in enumerate(payload):
        try:
            # Manually validate against our strict schema
            asset = AssetCreate.model_validate(item)
            valid_assets.append(asset)
        except ValidationError as e:
            external_id = item.get("id") or item.get("external_id")
            errors.append(
                BulkImportError(
                    index=index,
                    external_id=external_id,
                    value=item.get("value"),
                    error="; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in e.errors())
                )
            )

    # 2. Process valid assets in bulk
    imported_count = 0
    updated_count = 0
    relationships_created = 0

    if valid_assets:
        # 2. Upsert assets — now also returns the ext_id → UUID map
        imported_count, updated_count, ext_id_map = await bulk_import_service.bulk_upsert(db, valid_assets)

        # 3. Second pass: resolve relationship hints using that map
        relationships_created = await bulk_import_service.resolve_relationship_hints(
            db, valid_assets, ext_id_map
        )

    # 4. Return a detailed report
    return BulkImportResponse(
        imported=imported_count,
        updated=updated_count,
        relationships_created=relationships_created,
        errors=errors
    )
