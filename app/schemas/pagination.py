from typing import TypeVar, Generic
from enum import Enum

from pydantic import BaseModel


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated list endpoints."""
    total: int
    page: int
    size: int
    items: list[T]


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class AssetSortField(str, Enum):
    FIRST_SEEN = "first_seen"
    LAST_SEEN = "last_seen"
    TYPE = "type"
    VALUE = "value"
    STATUS = "status"