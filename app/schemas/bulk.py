from pydantic import BaseModel, Field
from typing import Any


class BulkImportResponse(BaseModel):
    """Schema for reporting the results of a bulk import operation."""
    processed_count: int
    failed_count: int
    errors: list[dict[str, Any]] = Field(default_factory=list)
