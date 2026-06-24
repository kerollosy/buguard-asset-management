from pydantic import BaseModel, Field


class BulkImportError(BaseModel):
    index: int = Field(..., description="The array index of the malformed record.")
    external_id: str | None = Field(
        default=None, 
        description="The provided external ID, if any",
        examples=["malformed-asset-01"]
    )
    value: str | None = Field(
        default=None, 
        description="The provided asset value, if any",
        examples=["missing-type.com"]
    )
    error: str = Field(
        ..., 
        description="The validation error message.",
        examples=["type: Input should be 'domain', 'subdomain', etc."]
    )


class BulkImportResponse(BaseModel):
    """Schema for reporting the results of a bulk import operation."""
    imported: int = Field(
        ..., 
        description="Number of newly created assets.",
        examples=[150]
    )
    updated: int = Field(
        ..., 
        description="Number of existing assets re-sighted and updated.",
        examples=[42]
    )
    errors: list[BulkImportError] = Field(
        default_factory=list,
        description="Per-record errors; valid records in the batch will still succeed.",
        examples=[{
            "index": 0,
            "external_id": "malformed-asset-01",
            "value": "missing-type.com",
            "error": "type: Input should be 'domain', 'subdomain', etc."
        }]
    )
