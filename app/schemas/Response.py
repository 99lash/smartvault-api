from typing import Generic, TypeVar, Optional
from pydantic import BaseModel

T = TypeVar("T")

class Response(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    detail: Optional[str] = None