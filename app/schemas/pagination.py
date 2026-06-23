from typing import TypeVar, Generic
from pydantic import BaseModel


T = TypeVar('T')


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic wrapper for paginated list endpoints."""
    total: int
    page: int
    size: int
    items: list[T]