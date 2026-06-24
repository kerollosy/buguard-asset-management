from pydantic import BaseModel, Field


class BulkImportError(BaseModel):
    index: int
    external_id: str | None = Field(default=None, description="The provided external ID, if any")
    value: str | None = Field(default=None, description="The provided asset value, if any")
    error: str


class BulkImportResponse(BaseModel):
    """Schema for reporting the results of a bulk import operation."""
    imported: int = Field(description="Number of new assets created")
    updated: int = Field(description="Number of existing assets re-sighted and updated")
    errors: list[BulkImportError] = Field(
        default_factory=list,
        description="Per-record errors; other records in the batch still succeed",
    )