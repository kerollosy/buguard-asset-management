
from typing import Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import ValidationError

from app.core.database import get_db
from app.schemas.asset import AssetCreate
from app.schemas.bulk import BulkImportResponse
from app.services import bulk_import_service


router = APIRouter()


@router.post("/bulk", response_model=BulkImportResponse, status_code=status.HTTP_200_OK)
async def bulk_import_assets(
    payload: list[dict[str, Any]],
    db: AsyncSession = Depends(get_db)
):
    """
    Bulk import assets from a JSON array. 
    Malformed records are skipped and reported; valid records are ingested or merged.
    """
    valid_assets: list[AssetCreate] = []
    errors: list[dict[str, Any]] = []

    # 1. Triage the payload
    for index, item in enumerate(payload):
        try:
            # Manually validate against our strict schema
            asset = AssetCreate.model_validate(item)
            valid_assets.append(asset)
        except ValidationError as e:
            # Catch bad records without failing the entire HTTP request
            errors.append({
                "index": index,
                "value": item.get("value", "unknown"),
                "errors": e.errors()
            })

    # 2. Process valid assets in bulk
    if valid_assets:
        # Note: For payloads > 10,000 records, we would implement chunking here.
        # Given the scope, we process the valid batch in a single transaction.
        await bulk_import_service.bulk_upsert(db, valid_assets)

    # 3. Return a detailed report
    return BulkImportResponse(
        processed_count=len(valid_assets),
        failed_count=len(errors),
        errors=errors
    )