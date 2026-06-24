from typing import TypeVar, Generic
from enum import Enum

from pydantic import BaseModel, Field

T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated list endpoints."""
    total: int = Field(
        ..., 
        description="Total number of items matching the query across all pages.",
        examples=[142]
    )
    page: int = Field(
        ..., 
        description="The current page number being returned.",
        examples=[1]
    )
    size: int = Field(
        ..., 
        description="The maximum number of items returned per page.",
        examples=[20]
    )
    items: list[T] = Field(
        ..., 
        description="The array of items for the current page."
    )


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class AssetSortField(str, Enum):
    FIRST_SEEN = "first_seen"
    LAST_SEEN = "last_seen"
    TYPE = "type"
    VALUE = "value"
    STATUS = "status"