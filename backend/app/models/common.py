from typing import Generic, TypeVar, Optional, Any, List
from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class StandardResponse(BaseModel, Generic[DataT]):
    success: bool = Field(True, description="Indicates if the request succeeded")
    message: Optional[str] = Field(None, description="Optional informational or error message")
    data: Optional[DataT] = Field(None, description="Payload data")


class PaginationMeta(BaseModel):
    total: int = Field(..., description="Total items matching filter")
    count: int = Field(..., description="Items in current page")
    page: int = Field(1, description="Current page number")
    limit: int = Field(100, description="Items limit per page")
    total_pages: int = Field(1, description="Calculated total pages")


class PaginatedResponse(BaseModel, Generic[DataT]):
    meta: PaginationMeta
    data: List[DataT]
