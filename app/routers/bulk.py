
from typing import Any

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core.limiter import limiter
from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.asset import AssetCreate
from app.schemas.bulk import BulkImportError, BulkImportResponse
from app.services import bulk_import_service


router = APIRouter()


@router.post("/bulk", response_model=BulkImportResponse, status_code=status.HTTP_200_OK, dependencies=[Depends(get_current_user)])
@limiter.limit("10/minute")
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
            # Catch bad records without failing the entire HTTP request
            external_id = item.get("id", None)
            value = item.get("value", None)
            if external_id is None:
                external_id = item.get("external_id", None)
            
            errors.append(
                BulkImportError(
                    index=index,
                    external_id=external_id,
                    value=value,
                    error="; ".join(f"{err['loc'][-1]}: {err['msg']}" for err in e.errors())
                )
            )

    # 2. Process valid assets in bulk
    imported_count = 0
    updated_count = 0
    if valid_assets:
        # Note: For payloads > 10,000 records, we would implement chunking here.
        # Given the scope, we process the valid batch in a single transaction.
        imported_count, updated_count = await bulk_import_service.bulk_upsert(db, valid_assets)

    # 3. Return a detailed report
    return BulkImportResponse(
        imported=imported_count,
        updated=updated_count,
        errors=errors
    )
